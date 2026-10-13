"""Conservative GPW input generation inspired by Multiwfn outCP2Kinp.

This is a deliberately limited Python implementation, not a full port or a
claim of clean-room development. Reference: Multiwfn 2026.10.1,
cp2kmate.f90, outCP2Kinp. See THIRD_PARTY_NOTICES.md and
third_party/multiwfn/PROVENANCE.md for source/terms.
Multiwfn references (required by its published custom terms):
Tian Lu, Feiwu Chen, J. Comput. Chem. 33, 580-592 (2012), doi:10.1002/jcc.22885.
Tian Lu, J. Chem. Phys. 161, 082503 (2024), doi:10.1063/5.0216272.
No CP2K execution or input preprocessor expansion is performed.
"""
import hashlib
import math
import re
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from pathlib import Path

from . import __version__
from .errors import KitError
from .io import json_text, new_file, read_text
from .models import SCHEMA_VERSION
from .structure import Structure, check_cell

MULTIWFN_CITATIONS = (
    "Tian Lu, Feiwu Chen, J. Comput. Chem. 33, 580-592 (2012). DOI: 10.1002/jcc.22885",
    "Tian Lu, J. Chem. Phys. 161, 082503 (2024). DOI: 10.1063/5.0216272",
)
RUN_TYPES = ("ENERGY", "ENERGY_FORCE", "GEO_OPT", "CELL_OPT")
FUNCTIONALS = ("PBE", "BLYP")
BASES = ("SZV-MOLOPT-SR-GTH", "DZVP-MOLOPT-SR-GTH", "DZVP-MOLOPT-GTH",
         "TZVP-MOLOPT-GTH", "TZV2P-MOLOPT-GTH")
# cp2kmate.f90 Nval, restricted to matching SR basis/GTH-PBE entries
# checked against CP2K data/BASIS_MOLOPT and data/GTH_POTENTIALS.
_SR_ELEMENTS = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn "
                "Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba "
                "Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn").split()
_SR_VALENCES = (1, 2, 3, 4, 3, 4, 5, 6, 7, 8, 9, 10, 3, 4, 5, 6, 7, 8,
                9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 11, 12, 13, 4, 5, 6, 7, 8,
                9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 11, 12, 13, 4, 5, 6, 7, 8, 9, 10,
                12, 13, 14, 15, 16, 17, 18, 11, 12, 13, 4, 5, 6, 7, 8)
VALENCE = dict(zip(_SR_ELEMENTS, _SR_VALENCES))
DIFFUSE_ELEMENTS = set("H C N O F Si P S Cl".split())
PBE_ONLY_ELEMENTS = set("Nb Tc Cd Sn Hf Ta Re Os Ir Pt Hg Tl Po At Rn".split())
PERIODICITIES = ("NONE", "X", "Y", "Z", "XY", "XZ", "YZ", "XYZ")


@dataclass(frozen=True)
class InputSettings:
    project: str = "cp2kkit"
    run_type: str = "ENERGY"
    functional: str = "PBE"
    basis: str = "DZVP-MOLOPT-SR-GTH"
    dispersion: str = "none"
    charge: int = 0
    multiplicity: int = 1
    periodic: str | None = None
    cell: tuple[float, float, float] | None = None  # orthorhombic, angstrom
    vacuum: float = 5.0  # each side, angstrom; only for isolated cell construction
    scf: str = "ot"
    cutoff: float = 350.0  # Ry
    rel_cutoff: float = 50.0  # Ry
    eps_scf: float | None = None
    max_scf: int = 128
    kpoints: tuple[int, int, int] = (1, 1, 1)
    smearing: float | None = None  # kelvin
    added_mos: int = 20
    optimizer: str = "BFGS"
    max_iter: int = 400
    pressure: float = 1.01325  # bar
    data_dir: str | None = None


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise KitError(f"{name} must be finite and positive")


def data_header_exists(text, element, name):
    return any(len(p) > 1 and p[0] == element and name in p[1:]
               for line in text.splitlines() if (p := line.split()) and not line.lstrip().startswith("#"))


def generate_input(structure: Structure, settings: InputSettings):
    """Return (complete input text, deterministic provenance/settings manifest)."""
    s = settings
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", s.project):
        raise KitError("Project must be a safe name (letters, digits, _, ., -); no paths or directives")
    for value, choices, name in ((s.run_type, RUN_TYPES, "run type"), (s.functional, FUNCTIONALS, "functional"),
                                 (s.basis, BASES, "basis"), (s.dispersion, ("none", "d3", "d3bj"), "dispersion"),
                                 (s.scf, ("ot", "diag"), "SCF"), (s.optimizer, ("BFGS", "LBFGS", "CG"), "optimizer")):
        if value not in choices:
            raise KitError(f"Unsupported {name}: {value}")
    for value, name, minimum in ((s.charge, "charge", None), (s.multiplicity, "multiplicity", 1),
                                 (s.max_scf, "max_scf", 1), (s.max_iter, "max_iter", 1),
                                 (s.added_mos, "added_mos", 0)):
        if type(value) is not int or (minimum is not None and value < minimum):
            raise KitError(f"Invalid integer {name}: {value}")
    for value, name in ((s.cutoff, "cutoff"), (s.rel_cutoff, "rel_cutoff"), (s.vacuum, "vacuum")):
        positive(value, name)
    if not math.isfinite(s.pressure):
        raise KitError("Pressure must be finite (bar)")
    eps = s.eps_scf if s.eps_scf is not None else (5e-6 if s.run_type == "ENERGY" else 1e-6)
    positive(eps, "eps_scf")
    if len(s.kpoints) != 3 or any(type(v) is not int or v < 1 for v in s.kpoints):
        raise KitError("kpoints requires three positive integers")
    if not structure.symbols or len(structure.symbols) != len(structure.positions):
        raise KitError("Structure must have matching, nonempty atoms and positions")
    if any(len(row) != 3 or not all(math.isfinite(v) for v in row) for row in structure.positions):
        raise KitError("Coordinates must have three finite angstrom values per atom")
    elements = sorted(set(structure.symbols))
    unsupported = set(elements) - VALENCE.keys()
    if unsupported:
        raise KitError("No verified basis/potential preset for: " + ", ".join(sorted(unsupported)))
    if '-SR-' not in s.basis and set(elements) - DIFFUSE_ELEMENTS:
        raise KitError("Non-SR MOLOPT preset only supports H C N O F Si P S Cl; use an SR basis")
    if s.functional == "BLYP" and set(elements) & PBE_ONLY_ELEMENTS:
        raise KitError("No verified GTH-BLYP preset for: " + ", ".join(sorted(set(elements) & PBE_ONLY_ELEMENTS)))
    electrons = sum(VALENCE[symbol] for symbol in structure.symbols) - s.charge
    unpaired = s.multiplicity - 1
    if electrons <= 0 or unpaired > electrons or (electrons - unpaired) % 2:
        raise KitError(f"Charge/multiplicity inconsistent with {electrons} explicit valence electrons")
    periodic = s.periodic
    if periodic is None and structure.pbc is not None:
        if len(structure.pbc) != 3 or any(type(v) is not bool for v in structure.pbc):
            raise KitError("PBC must contain three boolean flags")
        periodic = "".join(axis for axis, flag in zip("XYZ", structure.pbc) if flag) or "NONE"
    if periodic not in PERIODICITIES:
        raise KitError("Periodicity is unknown: specify --periodic explicitly (NONE for isolated molecules)")
    if s.run_type == "CELL_OPT" and periodic != "XYZ":
        raise KitError("CELL_OPT currently requires full XYZ periodicity")
    if s.kpoints != (1, 1, 1) and (periodic != "XYZ" or s.scf != "diag"):
        raise KitError("Non-Gamma kpoints require XYZ periodicity and diagonalization (--scf diag)")
    if s.smearing is not None:
        positive(s.smearing, "smearing temperature")
        if s.scf != "diag" or s.added_mos < 1:
            raise KitError("Smearing requires diagonalization and positive added_mos")
    positions = [row.copy() for row in structure.positions]
    cell = structure.cell
    translated = False
    if s.cell is not None:
        if len(s.cell) != 3:
            raise KitError("cell requires three lengths in angstrom")
        for value in s.cell:
            positive(value, "cell length")
        cell = [[s.cell[0], 0.0, 0.0], [0.0, s.cell[1], 0.0], [0.0, 0.0, s.cell[2]]]
    if cell is None:
        if periodic != "NONE":
            raise KitError("Periodic calculations require a source cell or explicit --cell A B C")
        lower = [min(row[j] for row in positions) for j in range(3)]
        upper = [max(row[j] for row in positions) for j in range(3)]
        lengths = [upper[j] - lower[j] + 2*s.vacuum for j in range(3)]
        cell = [[lengths[0], 0.0, 0.0], [0.0, lengths[1], 0.0], [0.0, 0.0, lengths[2]]]
        positions = [[row[j] - lower[j] + s.vacuum for j in range(3)] for row in positions]
        translated = True
    if len(cell) != 3 or any(len(row) != 3 or not all(math.isfinite(v) for v in row) for row in cell):
        raise KitError("Cell must contain three finite angstrom vectors")
    check_cell(cell)
    if s.run_type == "CELL_OPT" and any(cell[i][j] != 0.0 for i, j in ((0, 1), (0, 2), (1, 2))):
        raise KitError("CELL_OPT requires a lower-triangular cell: A along X, B in the XY plane")
    solver = "PERIODIC" if periodic == "XYZ" else "WAVELET" if periodic == "NONE" else "ANALYTIC"
    warnings = ["Generated template is not CP2K-runtime validated; converge basis, cutoff and kpoints for the target property.",
                "Only geometry/cell/PBC are read from the source; charge, spin, method and per-kind settings are NOT inherited."]
    if periodic == "NONE":
        warnings.append("WAVELET requires electronic density to vanish at cell faces; verify box size and molecular placement.")
    elif periodic != "XYZ":
        warnings.append("Low-dimensional ANALYTIC Poisson solver converges slowly; check vacuum and electrostatic convergence.")
    if s.scf == "ot":
        warnings.append("OT without smearing is intended for gapped systems, not metals.")
    kinds = {el: {"basis": f"{s.basis}-q{VALENCE[el]}",
                  "potential": f"GTH-{s.functional}-q{VALENCE[el]}", "valence_electrons": VALENCE[el]} for el in elements}
    data_sources = {}
    files = {"basis": "BASIS_MOLOPT", "potential": "GTH_POTENTIALS", "dispersion": "dftd3.dat"}
    if s.data_dir is not None:
        for key in ("basis", "potential") + (("dispersion",) if s.dispersion != "none" else ()):
            text, source = read_text(Path(s.data_dir) / files[key])
            data_sources[key] = source
            if key != "dispersion":
                for el, kind in kinds.items():
                    if not data_header_exists(text, el, kind[key]):
                        raise KitError(f"{files[key]} has no {el} {kind[key]}")
            files[key] = str((Path(s.data_dir) / files[key]).resolve())
            if any(c in files[key] for c in ('"', '\n', '\r', '#', '!', '@', '$')):
                raise KitError("CP2K data paths contain unsupported special characters")
    else:
        warnings.append("Data files resolved through CP2K_DATA_DIR at runtime; supply --data-dir to verify names and record file hashes.")
    def num(v):
        return format(v, ".17g")
    lines = ["# Generated by cp2kkit; subset developed with reference to Multiwfn cp2kmate.f90",
             "# Multiwfn references:", *("# " + citation for citation in MULTIWFN_CITATIONS),
             "&GLOBAL", f"  PROJECT {s.project}", f"  RUN_TYPE {s.run_type}", "  PRINT_LEVEL LOW", "&END GLOBAL",
             "&FORCE_EVAL", "  METHOD Quickstep"]
    if s.run_type == "CELL_OPT":
        lines.append("  STRESS_TENSOR ANALYTICAL")
    lines += ["  &DFT", f'    BASIS_SET_FILE_NAME "{files["basis"]}"',
              f'    POTENTIAL_FILE_NAME "{files["potential"]}"', f"    CHARGE {s.charge}",
              f"    MULTIPLICITY {s.multiplicity}", f"    UKS {'T' if s.multiplicity > 1 else 'F'}",
              "    &QS", "      METHOD GPW", f"      EPS_DEFAULT {num(1e-11 if s.run_type == 'ENERGY' else 1e-12)}", "    &END QS",
              "    &MGRID", f"      CUTOFF [Ry] {num(s.cutoff)}", f"      REL_CUTOFF [Ry] {num(s.rel_cutoff)}",
              f"      NGRIDS {5 if '-SR-' not in s.basis else 4}", "    &END MGRID",
              "    &POISSON", f"      PERIODIC {periodic}", f"      POISSON_SOLVER {solver}", "    &END POISSON",
              "    &SCF", "      SCF_GUESS ATOMIC", f"      EPS_SCF {num(eps)}", f"      MAX_SCF {s.max_scf}"]
    if s.scf == "ot":
        lines += ["      &OT", "        PRECONDITIONER FULL_ALL", "        MINIMIZER DIIS", "      &END OT",
                  "      &OUTER_SCF", f"        EPS_SCF {num(eps)}", "        MAX_SCF 20", "      &END OUTER_SCF"]
    else:
        lines += [f"      ADDED_MOS {s.added_mos}", "      &DIAGONALIZATION", "        ALGORITHM STANDARD", "      &END DIAGONALIZATION",
                  "      &MIXING", "        METHOD BROYDEN_MIXING", "        ALPHA 0.4", "        NBROYDEN 8", "      &END MIXING"]
        if s.smearing is not None:
            lines += ["      &SMEAR", "        METHOD FERMI_DIRAC", f"        ELECTRONIC_TEMPERATURE [K] {num(s.smearing)}", "      &END SMEAR"]
    lines += ["    &END SCF", "    &XC", f"      &XC_FUNCTIONAL {s.functional}", "      &END XC_FUNCTIONAL"]
    if s.dispersion != "none":
        lines += ["      &VDW_POTENTIAL", "        POTENTIAL_TYPE PAIR_POTENTIAL", "        &PAIR_POTENTIAL",
                  f"          TYPE {'DFTD3' if s.dispersion == 'd3' else 'DFTD3(BJ)'}",
                  f'          PARAMETER_FILE_NAME "{files["dispersion"]}"', f"          REFERENCE_FUNCTIONAL {s.functional}",
                  "        &END PAIR_POTENTIAL", "      &END VDW_POTENTIAL"]
    lines += ["    &END XC"]
    if s.kpoints != (1, 1, 1):
        lines += ["    &KPOINTS", "      SCHEME MONKHORST-PACK " + " ".join(map(str, s.kpoints)), "    &END KPOINTS"]
    lines += ["  &END DFT", "  &SUBSYS", "    &CELL"]
    lines += [f"      {axis} [angstrom] " + " ".join(map(num, row)) for axis, row in zip("ABC", cell)]
    lines += [f"      PERIODIC {periodic}", "    &END CELL", "    &COORD", "      UNIT angstrom"]
    lines += ["      " + el + " " + " ".join(map(num, row)) for el, row in zip(structure.symbols, positions)]
    lines += ["    &END COORD"]
    for el, kind in kinds.items():
        lines += [f"    &KIND {el}", f"      ELEMENT {el}", f"      BASIS_SET {kind['basis']}",
                  f"      POTENTIAL {kind['potential']}", "    &END KIND"]
    lines += ["  &END SUBSYS", "&END FORCE_EVAL"]
    if s.run_type in {"GEO_OPT", "CELL_OPT"}:
        lines += ["&MOTION", f"  &{s.run_type}", f"    OPTIMIZER {s.optimizer}", f"    MAX_ITER {s.max_iter}",
                  "    MAX_DR 3E-3", "    RMS_DR 1.5E-3", "    MAX_FORCE 4.5E-4", "    RMS_FORCE 3E-4"]
        if s.run_type == "GEO_OPT":
            lines.append("    TYPE MINIMIZATION")
        else:
            lines += [f"    EXTERNAL_PRESSURE [bar] {num(s.pressure)}", "    PRESSURE_TOLERANCE [bar] 100"]
        lines += [f"  &END {s.run_type}", "&END MOTION"]
    text = "\n".join(lines) + "\n"
    effective = Structure(structure.symbols.copy(), positions, [row.copy() for row in cell],
                          [axis in periodic for axis in "XYZ"], structure.source, structure.frame)
    manifest = {"schema_version": SCHEMA_VERSION, "generator": {"name": "cp2kkit", "version": __version__},
                "target_software": "CP2K", "runtime_version": None, "runtime_validated": False,
                "references": {"Multiwfn": list(MULTIWFN_CITATIONS),
                               "terms_url": "http://sobereva.com/multiwfn/download.html",
                               "notice": "THIRD_PARTY_NOTICES.md"},
                "settings": asdict(s), "effective_eps_scf": eps, "poisson_solver": solver,
                "units": {"coordinates": "angstrom", "cell": "angstrom", "vacuum": "angstrom",
                          "cutoff": "Ry", "rel_cutoff": "Ry", "smearing": "K", "pressure": "bar",
                          "max_dr": "bohr", "rms_dr": "bohr", "max_force": "hartree/bohr", "rms_force": "hartree/bohr"},
                "valence_electron_count": electrons, "kinds": kinds, "data_sources": data_sources,
                "source_structure": structure.to_dict(), "generated_structure": effective.to_dict(),
                "coordinates_translated": translated, "warnings": warnings,
                "input_text": text, "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    return text, manifest


def write_input(structure, settings, output):
    text, manifest = generate_input(structure, settings)
    output = Path(output)
    sidecar = Path(str(output) + ".json")
    with ExitStack() as stack:
        inp = stack.enter_context(new_file(output))
        log = stack.enter_context(new_file(sidecar))
        inp.write(text)
        log.write(json_text(manifest))
    return output, sidecar, manifest["warnings"]
