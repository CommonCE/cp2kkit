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
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from pathlib import Path

from . import __version__
from .errors import KitError
from .io import json_text, new_file, read_text
from .models import SCHEMA_VERSION
from .structure import Structure, check_cell
from .spin_settings import atomic_kinds, validate_requests

MULTIWFN_CITATIONS = (
    "Tian Lu, Feiwu Chen, J. Comput. Chem. 33, 580-592 (2012). DOI: 10.1002/jcc.22885",
    "Tian Lu, J. Chem. Phys. 161, 082503 (2024). DOI: 10.1063/5.0216272",
)
CP2K_VERSIONS = ("2024.1", "2024.2", "2024.3", "2025.1", "2025.2", "2026.1", "2026.2")
# Exact source bytes inspected for the common density-output keyword contract.
DENSITY_DEFINITION_HASHES = {
    "2024.1": "2d2156115ed139b1f59e2b9e9db4c5c27909603093aa8ebfd153f89020023887",
    "2024.2": "6a1bdf398bd1f56321ec6eca18be7e1661651b8848f7723367e6e636e9551b22",
    "2024.3": "6a1bdf398bd1f56321ec6eca18be7e1661651b8848f7723367e6e636e9551b22",
    "2025.1": "d85973f39a0a326adb25e75779dd09cccdfc23ab1f469e73ee6d2d3d9180995e",
    "2025.2": "0156c7c6d0afbd5dcd14d2b9d513b249cbd274e3300be16369a521e15d439650",
    "2026.1": "e41fc1ae1c574eddf0faed59cede0e29208f460867bcc6bc89457f54d3c9fd7a",
    "2026.2": "2cef0bc8e85f0ec6c291a5c5101da55fea0658440c15647d42220f530c0aa2bc",
}
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
    project: str | None = None
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
    cutoff: float = 400.0  # Ry
    rel_cutoff: float = 55.0  # Ry
    eps_scf: float | None = None
    max_scf: int | None = None  # auto: OT inner 25, diagonalization 128
    max_outer_scf: int = 20
    kpoints: tuple[int, int, int] = (1, 1, 1)
    smearing: float | None = None  # kelvin
    added_mos: int | None = None  # auto: smearing max(30, NINT(natoms/2)), otherwise 0
    optimizer: str = "BFGS"
    max_iter: int = 400
    pressure: float = 1.01325  # bar
    data_dir: str | None = None
    cp2k_version: str = "2026.2"
    electron_density: bool = False
    spin_density: bool = False
    cube_stride: tuple[int, int, int] | None = None
    dft_plus_u: tuple[tuple[str, int, float], ...] = ()  # element, L, Ueff [eV]
    magnetism: tuple[tuple[str, float], ...] | None = None  # None: auto; (): UKS; element/@atom seeds


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise KitError(f"{name} must be finite and positive")


def data_header_exists(text, element, name):
    return any(len(p) > 1 and p[0] == element and name in p[1:]
               for line in text.splitlines() if (p := line.split()) and not line.lstrip().startswith("#"))


def scientific_number(value):
    """Readable uppercase scientific notation without losing user precision."""
    mantissa, exponent = format(Decimal(str(value)), 'E').split('E')
    if '.' in mantissa:
        mantissa = mantissa.rstrip('0').rstrip('.')
    if '.' not in mantissa:
        mantissa += '.0'
    return f'{mantissa}E{int(exponent):+03d}'


def geometry_number(value):
    """Numeric value actually serialized at eight decimal places, without -0."""
    rounded = float(format(value, '.8f'))
    return 0.0 if rounded == 0.0 else rounded


def generate_input(structure: Structure, settings: InputSettings):
    """Return (complete input text, deterministic provenance/settings manifest)."""
    project = settings.project
    if project is None:
        if not structure.source.get('path'):
            raise KitError("Automatic project name requires a source path; specify project explicitly")
        project = Path(structure.source['path']).stem
    s = replace(settings,
                project=project,
                max_scf=settings.max_scf if settings.max_scf is not None else (25 if settings.scf == 'ot' else 128),
                added_mos=settings.added_mos if settings.added_mos is not None else
                (max(30, (len(structure.symbols)+1)//2) if settings.scf == 'diag' and settings.smearing is not None else 0))
    if s.cp2k_version not in CP2K_VERSIONS:
        raise KitError("CP2K target version must be one of the checked 2024.1–2026.2 profiles")
    if not isinstance(s.project, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", s.project):
        raise KitError("Project must be a safe name (letters, digits, _, ., -); no paths or directives")
    for value, choices, name in ((s.run_type, RUN_TYPES, "run type"), (s.functional, FUNCTIONALS, "functional"),
                                 (s.basis, BASES, "basis"), (s.dispersion, ("none", "d3", "d3bj"), "dispersion"),
                                 (s.scf, ("ot", "diag"), "SCF"), (s.optimizer, ("BFGS", "LBFGS", "CG"), "optimizer")):
        if value not in choices:
            raise KitError(f"Unsupported {name}: {value}")
    for value, name, minimum in ((s.charge, "charge", None), (s.multiplicity, "multiplicity", 1),
                                 (s.max_scf, "max_scf", 1), (s.max_outer_scf, "max_outer_scf", 1),
                                 (s.max_iter, "max_iter", 1),
                                 (s.added_mos, "added_mos", 0)):
        if type(value) is not int or (minimum is not None and value < minimum):
            raise KitError(f"Invalid integer {name}: {value}")
    for value, name in ((s.cutoff, "cutoff"), (s.rel_cutoff, "rel_cutoff"), (s.vacuum, "vacuum")):
        positive(value, name)
    if not math.isfinite(s.pressure):
        raise KitError("Pressure must be finite (bar)")
    eps = s.eps_scf if s.eps_scf is not None else (5e-6 if s.run_type == "ENERGY" else 1e-6)
    positive(eps, "eps_scf")
    uks = s.multiplicity > 1 or s.magnetism is not None
    density_enabled = s.electron_density or s.spin_density
    if s.spin_density and not uks:
        raise KitError("Spin density requires UKS; select multiplicity > 1 or explicit magnetism/UKS")
    if s.cube_stride is not None:
        if len(s.cube_stride) != 3 or any(type(v) is not int or v < 1 for v in s.cube_stride):
            raise KitError("cube_stride requires three positive integers")
        if not density_enabled:
            raise KitError("cube_stride requires --electron-density or --spin-density")
    stride = s.cube_stride if s.cube_stride is not None else (1, 1, 1)
    density_each = {"QS_SCF": 0, "JUST_ENERGY": 1, "GEO_OPT": 0, "CELL_OPT": 0}
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
    hubbard, magnetism = validate_requests(s.dft_plus_u, s.magnetism, structure.symbols, VALENCE)
    s = replace(s, dft_plus_u=hubbard, magnetism=magnetism)
    if (hubbard or magnetism is not None) and s.cp2k_version != '2026.2':
        raise KitError('DFT+U and explicit magnetic settings are currently keyword-checked only for CP2K 2026.2')
    atom_labels, kind_specs = atomic_kinds(structure.symbols, magnetism)
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
    if s.scf == "ot" and s.added_mos != 0:
        raise KitError("OT does not support added_mos; use diagonalization or --added-mos 0")
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
    # Manifest must describe the geometry in the generated text, not the
    # unrounded values. Original coordinates/cell remain in source_structure.
    cell = [[geometry_number(v) for v in row] for row in cell]
    positions = [[geometry_number(v) for v in row] for row in positions]
    check_cell(cell)  # Rounding must not turn a valid tiny cell into a singular one.
    solver = "PERIODIC" if periodic == "XYZ" else "WAVELET" if periodic == "NONE" else "ANALYTIC"
    warnings = ["Generated template is not CP2K-runtime validated; converge basis, cutoff and kpoints for the target property.",
                "Only geometry/cell/PBC are read from the source; charge, spin, method and per-kind settings are NOT inherited."]
    if periodic == "NONE":
        warnings.append("WAVELET requires electronic density to vanish at cell faces; verify box size and molecular placement.")
    elif periodic != "XYZ":
        warnings.append("Low-dimensional ANALYTIC Poisson solver converges slowly; check vacuum and electrostatic convergence.")
    if s.scf == "ot":
        warnings.append("OT without smearing is intended for gapped systems, not metals.")
    if s.scf == 'diag' and s.smearing is not None and settings.added_mos is None:
        warnings.append("Automatic ADDED_MOS = max(30, NINT(atom_count/2)) follows Multiwfn's smearing heuristic (usually for 300 K); verify enough unoccupied states for this system/temperature.")
    if structure.source.get('selective_dynamics') and any('F' in flags for flags in structure.source['selective_dynamics']):
        warnings.append("POSCAR selective-dynamics constraints are recorded in source metadata but NOT inherited in this new CP2K input.")
    if density_enabled:
        warnings.append("GPW/GTH cube contains pseudopotential valence electron density, not all-electron/core density; stride and grid need convergence checks.")
        if uks:
            warnings.append("CP2K E_DENSITY_CUBE prints both electron and alpha-minus-beta spin densities for UKS; these cannot be independently suppressed here.")
        if s.run_type in {"GEO_OPT", "CELL_OPT"}:
            warnings.append("ADD_LAST prints the last identified optimization step, not proof of convergence; verify output and use a final fixed-geometry ENERGY calculation for comparable fragment grids.")
    if hubbard:
        warnings.append('DFT+U uses explicit Ueff=U-J [eV] with MULLIKEN projectors; justify U, orbital L and basis for the target property. No U values are inferred.')
    if magnetism is not None:
        warnings.append('Explicit magnetism enables collinear UKS without changing total charge/multiplicity. MAGNETIZATION is only an atomic initial guess, not a fixed local moment or guaranteed magnetic state.')
        initial_sum = sum(kind_specs[label][1] or 0. for label in atom_labels)
        if magnetism and not math.isclose(initial_sum, s.multiplicity-1, abs_tol=1e-10):
            warnings.append(f'Requested initial atomic moments sum to {initial_sum:g}, while MULTIPLICITY-1 is {s.multiplicity-1}; check the intended magnetic state. Neither value is adjusted automatically.')
    kinds = {}
    u_by_element = {el: (angular, energy) for el, angular, energy in hubbard}
    for label, (el, moment) in sorted(kind_specs.items()):
        kind = {"basis": f"{s.basis}-q{VALENCE[el]}",
                "potential": f"GTH-{s.functional}-q{VALENCE[el]}", "valence_electrons": VALENCE[el]}
        if hubbard or magnetism is not None:
            kind['element'] = el
            kind['initial_magnetization'] = moment
            if el in u_by_element:
                angular, energy = u_by_element[el]
                kind['dft_plus_u'] = {'L': angular, 'U_minus_J': energy, 'unit': 'eV', 'method': 'MULLIKEN'}
        kinds[label] = kind
    data_sources = {}
    files = {"basis": "BASIS_MOLOPT", "potential": "GTH_POTENTIALS", "dispersion": "dftd3.dat"}
    if s.data_dir is not None:
        for key in ("basis", "potential") + (("dispersion",) if s.dispersion != "none" else ()):
            text, source = read_text(Path(s.data_dir) / files[key])
            data_sources[key] = source
            if key != "dispersion":
                for label, kind in kinds.items():
                    el = kind.get('element', label)
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
             "# CELL vectors and COORD Cartesian coordinates are in angstrom (CP2K default units).",
             "# Multiwfn references:", *("# " + citation for citation in MULTIWFN_CITATIONS),
             "&GLOBAL", f"  PROJECT {s.project}", f"  RUN_TYPE {s.run_type}", "  PRINT_LEVEL LOW", "&END GLOBAL",
             "&FORCE_EVAL", "  METHOD Quickstep"]
    if s.run_type == "CELL_OPT":
        lines.append("  STRESS_TENSOR ANALYTICAL")
    lines += ["  &DFT", f'    BASIS_SET_FILE_NAME "{files["basis"]}"',
              f'    POTENTIAL_FILE_NAME "{files["potential"]}"', f"    CHARGE {s.charge}",
              f"    MULTIPLICITY {s.multiplicity}", f"    UKS {'T' if uks else 'F'}",
              "    &QS", "      METHOD GPW", f"      EPS_DEFAULT {scientific_number(1e-11 if s.run_type == 'ENERGY' else 1e-12)}", "    &END QS",
              "    &MGRID", f"      CUTOFF [Ry] {num(s.cutoff)}", f"      REL_CUTOFF [Ry] {num(s.rel_cutoff)}",
              f"      NGRIDS {5 if '-SR-' not in s.basis else 4}", "    &END MGRID",
              "    &POISSON", f"      PERIODIC {periodic}", f"      POISSON_SOLVER {solver}", "    &END POISSON",
              "    &SCF", "      SCF_GUESS ATOMIC", f"      EPS_SCF {scientific_number(eps)}", f"      MAX_SCF {s.max_scf}"]
    if hubbard:
        # PLUS_U_METHOD belongs in DFT, not SCF; insert before &QS.
        lines.insert(lines.index('    &QS'), '    PLUS_U_METHOD MULLIKEN')
    if s.scf == "ot":
        lines += ["      &OT", "        PRECONDITIONER FULL_ALL", "        MINIMIZER DIIS", "      &END OT",
                  "      &OUTER_SCF", f"        EPS_SCF {scientific_number(eps)}", f"        MAX_SCF {s.max_outer_scf}", "      &END OUTER_SCF"]
    else:
        added_mos = ' '.join([str(s.added_mos)] * (2 if uks else 1))
        lines += [f"      ADDED_MOS {added_mos}", "      &DIAGONALIZATION", "        ALGORITHM STANDARD", "      &END DIAGONALIZATION",
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
    if density_enabled:
        lines += ["    &PRINT", "      &E_DENSITY_CUBE ON",
                  "        STRIDE " + " ".join(map(str, stride)),
                  "        APPEND F", "        ADD_LAST NUMERIC", "        &EACH"]
        lines += [f"          {key} {value}" for key, value in density_each.items()]
        lines += ["        &END EACH", "      &END E_DENSITY_CUBE", "    &END PRINT"]
    lines += ["  &END DFT", "  &SUBSYS", "    &CELL"]
    lines += [f"      {axis}" + "".join(f" {v:14.8f}" for v in row) for axis, row in zip("ABC", cell)]
    lines += [f"      PERIODIC {periodic} #Direction(s) of applied PBC (geometry aspect)",
              "    &END CELL", "    &COORD"]
    lines += [f"      {el:<8}" + "".join(f" {v:13.8f}" for v in row)
              for el, row in zip(atom_labels, positions)]
    lines += ["    &END COORD"]
    for label, kind in kinds.items():
        el = kind.get('element', label)
        lines += [f"    &KIND {label}", f"      ELEMENT {el}", f"      BASIS_SET {kind['basis']}",
                  f"      POTENTIAL {kind['potential']}"]
        if kind.get('initial_magnetization') is not None:
            lines.append(f"      MAGNETIZATION {num(kind['initial_magnetization'])}")
        if el in u_by_element:
            angular, energy = u_by_element[el]
            lines += ['      &DFT_PLUS_U ON', f'        L {angular}',
                      f'        U_MINUS_J [eV] {num(energy)}', '      &END DFT_PLUS_U']
        lines.append('    &END KIND')
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
                "target_software": "CP2K", "target_version": s.cp2k_version,
                "runtime_version": None, "runtime_validated": False,
                "references": {"Multiwfn": list(MULTIWFN_CITATIONS),
                               "terms_url": "http://sobereva.com/multiwfn/download.html",
                               "notice": "THIRD_PARTY_NOTICES.md"},
                "settings": asdict(s), "effective_eps_scf": eps, "poisson_solver": solver,
                "density_output": {"enabled": bool(density_enabled),
                                   "electron_density": bool(density_enabled),
                                   "spin_density": bool(density_enabled and uks),
                                   "stride": list(stride) if density_enabled else None,
                                   "each": density_each if density_enabled else None,
                                   "add_last": "NUMERIC" if density_enabled else None,
                                   "append": False, "filename_override": None,
                                   "density_meaning": "GPW pseudopotential valence electron density",
                                   "spin_convention": "alpha minus beta", "spatial_unit": "bohr",
                                   "scalar_unit": "e/bohr^3", "stride_unit": "grid index increment",
                                   "reference_version": "CP2K " + s.cp2k_version, "syntax_reference_checked": True,
                                   "runtime_validated": False,
                                   "source": f"https://raw.githubusercontent.com/cp2k/cp2k/v{s.cp2k_version}/src/" +
                                             ("input_cp2k_dft.F" if s.cp2k_version == "2024.1" else "input_cp2k_print_dft.F"),
                                   "definition_sha256": DENSITY_DEFINITION_HASHES[s.cp2k_version],
                                   "manual_source": None if s.cp2k_version == "2024.3" else
                                       f"https://manual.cp2k.org/cp2k-{s.cp2k_version.replace('.', '_')}-branch/CP2K_INPUT/FORCE_EVAL/DFT/PRINT/E_DENSITY_CUBE.html"},
                "units": {"coordinates": "angstrom", "cell": "angstrom", "vacuum": "angstrom",
                          "cutoff": "Ry", "rel_cutoff": "Ry", "smearing": "K", "pressure": "bar",
                          "max_dr": "bohr", "rms_dr": "bohr", "max_force": "hartree/bohr", "rms_force": "hartree/bohr"},
                "valence_electron_count": electrons, "kinds": kinds, "data_sources": data_sources,
                "source_structure": structure.to_dict(), "generated_structure": effective.to_dict(),
                "coordinates_translated": translated, "warnings": warnings,
                "input_text": text, "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    if hubbard or magnetism is not None:
        manifest['electronic_extensions'] = {
            'uks': uks, 'atom_kinds': atom_labels, 'atom_index_base': 1,
            'initial_magnetization_convention': 'alpha minus beta electron number; initial guess only',
            'dft_plus_u_unit': 'eV', 'plus_u_method': 'MULLIKEN' if hubbard else None,
            'keyword_reference_version': '2026.2', 'runtime_validated': False,
            'references': [
                'https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND/DFT_PLUS_U.html',
                'https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND.html',
                'https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT.html']}
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
