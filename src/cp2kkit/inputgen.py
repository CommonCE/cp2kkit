"""Conservative GPW and all-electron GAPW input generation.

The original GPW subset was inspired by Multiwfn outCP2Kinp.

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
import os
import re
import stat
import tempfile
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from pathlib import Path

from . import __version__
from .errors import KitError, OutputExists
from .io import json_text, new_file, read_text
from .models import SCHEMA_VERSION
from .structure import Structure, check_cell
from .spin_settings import atomic_kinds, validate_requests
from .method_profiles import BASES, FUNCTIONALS, electron_model, resolve_method, xc_lines
from .all_electron_catalog import AE_SOURCES
from .gapw import GAPW_PROFILES, resolve_gapw, resolve_ngrids
from .data_catalog import CATALOG_SOURCES
from .basis_registry import DEFAULT_BASIS, basis_option, migrate_basis
from .cp2k_data import cp2k_long_path
from .constraints import CONSTRAINT_REFERENCE, resolve_fixed_atoms
from .functional_registry import parse_functional

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
# Legacy import-compatible coverage constants; resolution now uses data_catalog.
DIFFUSE_ELEMENTS = set("H C N O F Si P S Cl".split())
PBE_ONLY_ELEMENTS = set("Nb Tc Cd Sn Hf Ta Re Os Ir Pt Hg Tl Po At Rn".split())
PERIODICITIES = ("NONE", "X", "Y", "Z", "XY", "XZ", "YZ", "XYZ")
TRAJECTORY_FORMATS = ("PDB", "XYZ", "EXTXYZ")


@dataclass(frozen=True)
class InputSettings:
    project: str | None = None
    run_type: str = "ENERGY"
    functional: str = "PBE"
    basis: str = DEFAULT_BASIS
    dispersion: str = "none"
    charge: int = 0
    multiplicity: int | None = None
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
    basis_overrides: tuple[tuple[str, str], ...] = ()
    allow_pbe_potential: bool = False  # Explicit approval, not an automatic fallback.
    libxc_available: bool = False  # User assertion about target build, never probed.
    basis_files: tuple[str, ...] = ()  # Explicit source disambiguation, no search fallback.
    potential_files: tuple[str, ...] = ()
    custom_basis_file: str | None = None
    custom_basis_name: str | None = None
    custom_potential_file: str | None = None
    custom_potential_name: str | None = None
    gapw_profile: str = 'auto'  # Legacy auto/native names; both use native GAPW controls.
    ot_algorithm: str | None = None  # auto: explicit AE IRAC, PP STRICT
    write_json: bool = False  # Optional provenance sidecar; existing JSON is never overwritten.
    trust_radius: float = 0.2  # angstrom; GEO_OPT/CELL_OPT BFGS/LBFGS only
    trajectory_format: str = 'XYZ'  # MOTION position trajectory, optimization only
    fixed_atoms: str = 'off'  # 1-based indices/ranges in loaded geometry; fractional XYZ
    density_difference: bool = False
    fragment_a_indices: str = 'off'
    fragment_a_charge: int | None = None
    fragment_a_multiplicity: int | None = None
    fragment_b_charge: int | None = None
    fragment_b_multiplicity: int | None = None

    @classmethod
    def from_config(cls, values, source_version=None):
        """Load settings or a generator sidecar; numeric legacy choices need a version."""
        values = dict(values)
        if 'settings' in values:
            if values.get('basis_selection', {}).get('registry_version') is not None:
                if values['basis_selection']['registry_version'] != 1:
                    raise KitError('Unsupported basis registry version; no numeric interpretation is inferred')
                # Software 0.2.6 includes both the legacy and registry-v1 editor.
                # Registry-v1 configs must contain string IDs, not legacy positions.
                source_version = None
            else:
                source_version = source_version or values.get('generator', {}).get('version')
            values = dict(values['settings'])
        try:
            values['functional'] = parse_functional(values.get('functional', 'PBE'))
        except ValueError as exc:
            raise KitError(str(exc)) from exc
        values['basis'] = migrate_basis(values.get('basis', DEFAULT_BASIS), source_version)
        if values.get('basis_overrides'):
            values['basis_overrides'] = tuple((el, migrate_basis(basis, source_version))
                                              for el, basis in values['basis_overrides'])
        for name in ('cell', 'kpoints', 'cube_stride', 'basis_files', 'potential_files'):
            if values.get(name) is not None:
                values[name] = tuple(values[name])
        return cls(**values)


def automatic_multiplicity(structure, settings):
    """Minimal parity-compatible default, not a ground-state spin prediction."""
    if type(settings.charge) is not int:
        raise KitError(f'Invalid integer charge: {settings.charge}')
    _, counts = electron_model(settings, sorted(set(structure.symbols)), VALENCE)
    electrons = sum(counts[symbol] for symbol in structure.symbols) - settings.charge
    if electrons <= 0:
        raise KitError('Automatic multiplicity requires a positive electron count')
    return 1 + electrons % 2


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise KitError(f"{name} must be finite and positive")


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


def generate_input(structure: Structure, settings: InputSettings, *, _common_ngrids=None):
    """Return complete input/manifest; optional workflow includes fragment manifests."""
    if type(settings.density_difference) is not bool:
        raise KitError("density_difference must be Boolean")
    if settings.density_difference:
        from .density_workflow import generate_difference
        return generate_difference(structure, settings)
    if _common_ngrids not in (None, 5):
        raise KitError("Invalid internal common-grid lock")
    if type(settings.write_json) is not bool:
        raise KitError('write_json must be Boolean')
    try:
        functional = parse_functional(settings.functional)
    except ValueError as exc:
        raise KitError(str(exc)) from exc
    project = settings.project
    if project is None:
        if not structure.source.get('path'):
            raise KitError("Automatic project name requires a source path; specify project explicitly")
        project = Path(structure.source['path']).stem
    s = replace(settings, functional=functional,
                basis=basis_option(settings.basis).id,
                project=project,
                max_scf=settings.max_scf if settings.max_scf is not None else (25 if settings.scf == 'ot' else 128),
                added_mos=settings.added_mos if settings.added_mos is not None else
                (max(30, (len(structure.symbols)+1)//2) if settings.scf == 'diag' and settings.smearing is not None else 0))
    if s.multiplicity is None:
        s = replace(s, multiplicity=automatic_multiplicity(structure, s))
    if s.cp2k_version not in CP2K_VERSIONS:
        raise KitError("CP2K target version must be one of the checked 2024.1–2026.2 profiles")
    if not isinstance(s.project, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", s.project):
        raise KitError("Project must be a safe name (letters, digits, _, ., -); no paths or directives")
    for value, choices, name in ((s.run_type, RUN_TYPES, "run type"), (s.functional, FUNCTIONALS, "functional"),
                                 (s.dispersion, ("none", "d3", "d3bj"), "dispersion"),
                                 (s.gapw_profile, GAPW_PROFILES, "GAPW profile"),
                                 (s.trajectory_format, TRAJECTORY_FORMATS, "trajectory format"),
                                 (s.ot_algorithm, (None, "IRAC", "STRICT"), "OT algorithm"),
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
    if type(s.trust_radius) not in (int, float):
        raise KitError('trust_radius must be a finite positive number in angstrom')
    try:
        trust_radius = float(s.trust_radius)
    except OverflowError as exc:
        raise KitError('trust_radius must be a finite positive number in angstrom') from exc
    positive(trust_radius, 'trust_radius [angstrom]')
    s = replace(s, trust_radius=trust_radius)
    optimizing = s.run_type in {'GEO_OPT', 'CELL_OPT'}
    if optimizing and s.trajectory_format == 'EXTXYZ' and s.cp2k_version != '2026.2':
        raise KitError('EXTXYZ trajectory output is keyword-checked only for target CP2K 2026.2')
    if not math.isfinite(s.pressure):
        raise KitError("Pressure must be finite (bar)")
    eps = s.eps_scf if s.eps_scf is not None else 1e-6
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
    selection, fixed_atoms = resolve_fixed_atoms(s.fixed_atoms, len(structure.symbols), optimizing, s.cp2k_version)
    s = replace(s, fixed_atoms=selection)
    elements = sorted(set(structure.symbols))
    all_electron, electron_counts = electron_model(s, elements, VALENCE)
    qs_method = 'GAPW' if all_electron else 'GPW'
    hubbard, magnetism = validate_requests(s.dft_plus_u, s.magnetism, structure.symbols, electron_counts)
    s = replace(s, dft_plus_u=hubbard, magnetism=magnetism)
    if (hubbard or magnetism is not None) and s.cp2k_version != '2026.2':
        raise KitError('DFT+U and explicit magnetic settings are currently keyword-checked only for CP2K 2026.2')
    atom_labels, kind_specs = atomic_kinds(structure.symbols, magnetism)
    method_profile, basis_overrides, element_records, method_warnings = resolve_method(s, elements, electron_counts, kind_specs)
    s = replace(s, basis_overrides=basis_overrides)
    gapw = resolve_gapw(s, element_records) if all_electron else None
    ot_algorithm = (gapw['ot_algorithm'] if gapw else (s.ot_algorithm or 'STRICT')) if s.scf == 'ot' else None
    ngrids = _common_ngrids if _common_ngrids is not None else resolve_ngrids(element_records)
    electrons = sum(electron_counts[symbol] for symbol in structure.symbols) - s.charge
    unpaired = s.multiplicity - 1
    if electrons <= 0 or unpaired > electrons or (electrons - unpaired) % 2:
        model = 'all-electron electrons' if all_electron else 'explicit valence electrons'
        raise KitError(f"Charge/multiplicity inconsistent with {electrons} {model}")
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
    warnings.extend(method_warnings)
    warnings.append('SCF/PRINT/RESTART BACKUP_COPIES 0 disables wavefunction restart backups, not restart writing; archive existing wavefunctions before running in a reused directory.')
    if s.fixed_atoms != 'off' and not optimizing:
        warnings.append('Fixed-atom selection is retained but inactive outside GEO_OPT/CELL_OPT.')
    if fixed_atoms and s.run_type == 'CELL_OPT':
        warnings.append('FIXED_ATOMS constrains fractional XYZ coordinates, not absolute Cartesian positions; fixed atoms can move with a changing cell.')
    if fixed_atoms and len(fixed_atoms) == len(structure.symbols):
        warnings.append('All atoms are fixed; no internal atomic degrees of freedom remain. This is not evidence of optimized geometry.')
    if optimizing:
        warnings.append('MOTION/PRINT/RESTART BACKUP_COPIES 0 disables restart backup copies, not restart writing; archive restart files before running in a reused directory.')
        if s.trajectory_format == 'XYZ' and periodic != 'NONE':
            warnings.append('XYZ trajectories do not retain changing cell vectors; choose EXTXYZ or PDB when cell information is needed. PDB has limited coordinate precision.')
    if gapw:
        summary = '; '.join(f"{item['setting']}={item['value']}" for item in gapw['automatic_settings'])
        warnings.append(f"All-electron setup {gapw['profile']} v{gapw['profile_version']}: {summary}. "
                        'Charge/spin, functional, dispersion, cutoff/rel_cutoff and periodicity are preserved; numerical convergence is unverified.')
    if not all_electron and any('-SR-' not in record['basis'] for record in element_records.values()):
        warnings.append('Non-SR MOLOPT functions may increase cost/overlap ill-conditioning; converge basis and grid independently. Increasing CUTOFF does not complete the Gaussian basis.')
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
        kind = dict(element_records[el])
        if hubbard or magnetism is not None:
            kind['element'] = el
            kind['initial_magnetization'] = moment
            if el in u_by_element:
                angular, energy = u_by_element[el]
                kind['dft_plus_u'] = {'L': angular, 'U_minus_J': energy, 'unit': 'eV', 'method': 'MULLIKEN'}
        kinds[label] = kind
    data_sources = {}
    basis_files = sorted({record['basis_file'] for record in element_records.values()})
    potentials = sorted({record['potential_file'] for record in element_records.values()})
    if len(potentials) != 1:
        raise KitError('Mixed potential source files cannot be represented by the single POTENTIAL_FILE_NAME: '
                       + ', '.join(potentials) + '. Choose one explicit, physically appropriate source; no automatic protocol replacement/merge is performed.')
    files = {'potential': potentials[0], 'dispersion': 'dftd3.dat'}
    for i, file in enumerate(basis_files):
        record = next(r for r in element_records.values() if r['basis_file'] == file)
        if record['basis_source']:
            key = 'basis' if i == 0 else 'basis:'+Path(file).name
            if key in data_sources:
                key = 'basis:'+file  # Same basename in different explicitly selected directories.
            data_sources[key] = record['basis_source']
    potential_source = next(iter(element_records.values()))['potential_source']
    if potential_source:
        data_sources['potential'] = potential_source
    data_root = s.data_dir if s.data_dir is not None else os.environ.get('CP2K_DATA_DIR')
    if data_root is not None and s.dispersion != 'none':
        files['dispersion'] = str((Path(data_root)/'dftd3.dat').resolve())
        cp2k_long_path(files['dispersion'])
        _, data_sources['dispersion'] = read_text(files['dispersion'])
    elif s.dispersion != 'none':
        warnings.append('Dispersion data dftd3.dat have not been checked; the file is resolved by CP2K at runtime.')
    nonlocal_xc = {'enabled': method_profile.nonlocal_type is not None,
                   'type': method_profile.nonlocal_type, 'kernel_file': method_profile.kernel_file,
                   'parameters': list(method_profile.nonlocal_parameters) or None,
                   'parameter_names': ['b', 'C'] if method_profile.nonlocal_parameters else None,
                   'parameter_unit': 'dimensionless' if method_profile.nonlocal_parameters else None,
                   'cutoff_Ry': None, 'cutoff_policy': 'CP2K native default; not convergence-validated',
                   'kernel_source': None, 'kernel_validation': 'not_checked', 'runtime_validated': False}
    if method_profile.nonlocal_type:
        if data_root is not None:
            kernel_path = str((Path(data_root)/method_profile.kernel_file).resolve())
            cp2k_long_path(kernel_path)
            _, source = read_text(kernel_path)
            nonlocal_xc.update(kernel_file=kernel_path, kernel_source=source,
                               kernel_validation='source_bytes_only')
            data_sources['xc_kernel'] = source
        else:
            warnings.append(f'Nonlocal kernel {method_profile.kernel_file} has not been checked; '
                            'CP2K resolves it at runtime. Supply --data-dir to record source bytes/hash.')
    data_checked = all(r['data_validation'] == 'data_checked' for r in element_records.values())
    if not data_checked:
        reason = 'actual all-electron basis/nuclear potential files' if all_electron else 'actual basis/potential files or basis q matching'
        warnings.append(f'UNVERIFIED TEMPLATE: {reason} have not all been checked. Supply --data-dir or explicit files; catalog evidence is not an installed-data or runtime validation.')
    def num(v):
        return format(v, ".17g")
    lines = ["# Generated by cp2kkit; subset developed with reference to Multiwfn cp2kmate.f90",
             "# Multiwfn references:", *("# " + citation for citation in MULTIWFN_CITATIONS),
             "&GLOBAL", f"  PROJECT {s.project}", f"  RUN_TYPE {s.run_type}", "  PRINT_LEVEL LOW", "&END GLOBAL",
             "&FORCE_EVAL", "  METHOD Quickstep"]
    if s.run_type == "CELL_OPT":
        lines.append("  STRESS_TENSOR ANALYTICAL")
    restart_filename = s.project+'-RESTART'+('.wfn' if s.kpoints == (1, 1, 1) else '.kp')
    # Portable UZH runtime aliases; resolved source paths/hashes stay in provenance.
    emitted_basis_files = sorted({
        'BASIS_MOLOPT_UZH' if not s.basis_files and
        all(r['basis_protocol'] == 'uzh-pbe' or r['basis_id'].startswith('ae-uzh-')
            for r in element_records.values() if r['basis_file'] == file)
        else file for file in basis_files})
    emitted_potential = ('POTENTIAL_UZH' if not s.potential_files and
                         all(r['basis_protocol'] == 'uzh-pbe' for r in element_records.values())
                         else files['potential'])
    lines += ['  &DFT', *(f'    BASIS_SET_FILE_NAME {cp2k_long_path(file)}' for file in emitted_basis_files),
              f'    POTENTIAL_FILE_NAME {cp2k_long_path(emitted_potential)}', f"    CHARGE {s.charge}",
              f"    MULTIPLICITY {s.multiplicity}", f"    UKS {'T' if uks else 'F'}",
              "    &QS", f"      METHOD {qs_method}", f"      EPS_DEFAULT {scientific_number(1e-11 if s.run_type == 'ENERGY' else 1e-12)}",
              *(f"      {key} {scientific_number(value)}" for key, value in (gapw['qs'] if gapw else {}).items()), "    &END QS",
              "    &MGRID", f"      CUTOFF [Ry] {num(s.cutoff)}", f"      REL_CUTOFF [Ry] {num(s.rel_cutoff)}",
              *([f"      NGRIDS {ngrids}"] if ngrids is not None else []), "    &END MGRID",
              "    &POISSON", f"      PERIODIC {periodic}", f"      POISSON_SOLVER {solver}", "    &END POISSON",
              "    &SCF", f"      EPS_SCF {scientific_number(eps)}", f"      MAX_SCF {s.max_scf}"]
    if hubbard:
        # PLUS_U_METHOD belongs in DFT, not SCF; insert before &QS.
        lines.insert(lines.index('    &QS'), '    PLUS_U_METHOD MULLIKEN')
    if s.scf == "ot":
        lines += ["      &OT", "        PRECONDITIONER FULL_ALL", "        MINIMIZER DIIS",
                  f"        ALGORITHM {ot_algorithm}", "      &END OT",
                  "      &OUTER_SCF", f"        EPS_SCF {scientific_number(eps)}", f"        MAX_SCF {s.max_outer_scf}", "      &END OUTER_SCF"]
    else:
        added_mos = ' '.join([str(s.added_mos)] * (2 if uks else 1))
        lines += [f"      ADDED_MOS {added_mos}", "      &DIAGONALIZATION", "        ALGORITHM STANDARD", "      &END DIAGONALIZATION",
                  "      &MIXING", "        METHOD BROYDEN_MIXING", "        ALPHA 0.4", "        NBROYDEN 8", "      &END MIXING"]
        if s.smearing is not None:
            lines += ["      &SMEAR", "        METHOD FERMI_DIRAC", f"        ELECTRONIC_TEMPERATURE [K] {num(s.smearing)}", "      &END SMEAR"]
    lines += ['      &PRINT', '        &RESTART', '          BACKUP_COPIES 0',
              '        &END RESTART', '      &END PRINT', '    &END SCF', '    &XC', *xc_lines(s.functional)]
    if s.dispersion != "none":
        lines += ["      &VDW_POTENTIAL", "        POTENTIAL_TYPE PAIR_POTENTIAL", "        &PAIR_POTENTIAL",
                  f"          TYPE {'DFTD3' if s.dispersion == 'd3' else 'DFTD3(BJ)'}",
                  f'          PARAMETER_FILE_NAME {cp2k_long_path(files["dispersion"])}', f"          REFERENCE_FUNCTIONAL {s.functional}",
                  "        &END PAIR_POTENTIAL", "      &END VDW_POTENTIAL"]
    if method_profile.nonlocal_type:
        lines += ["      &VDW_POTENTIAL", "        POTENTIAL_TYPE NON_LOCAL", "        &NON_LOCAL",
                  f"          TYPE {method_profile.nonlocal_type}",
                  f"          KERNEL_FILE_NAME {cp2k_long_path(nonlocal_xc['kernel_file'])}"]
        if method_profile.nonlocal_parameters:
            lines.append("          PARAMETERS "+ " ".join(format(v, ".12g") for v in method_profile.nonlocal_parameters))
        lines += ["        &END NON_LOCAL", "      &END VDW_POTENTIAL"]
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
    lines += [f"      PERIODIC {periodic}",
              "    &END CELL", "    &COORD"]
    lines += [f"      {el:<8}" + "".join(f" {v:13.8f}" for v in row)
              for el, row in zip(atom_labels, positions)]
    lines += ["    &END COORD"]
    for label, kind in kinds.items():
        el = kind.get('element', label)
        lines += [f"    &KIND {label}", f"      ELEMENT {el}", f"      BASIS_SET {kind['basis']}",
                  f"      POTENTIAL {kind['potential']}",
                  *(f"      {key} {value}" for key, value in (gapw['kind'] if gapw else {}).items())]
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
        if s.optimizer in {'BFGS', 'LBFGS'}:
            lines += [f"    &{s.optimizer}", f"      TRUST_RADIUS [angstrom] {s.trust_radius}", f"    &END {s.optimizer}"]
        lines.append(f"  &END {s.run_type}")
        if fixed_atoms:
            lines += ["  &CONSTRAINT", "    &FIXED_ATOMS",
                      "      COMPONENTS_TO_FIX XYZ"]
            lines += ["      LIST "+" ".join(map(str, fixed_atoms[i:i+20])) for i in range(0, len(fixed_atoms), 20)]
            lines += ["    &END FIXED_ATOMS", "  &END CONSTRAINT"]
        lines += ["  &PRINT", "    &TRAJECTORY",
                  f"      FORMAT {s.trajectory_format}", "    &END TRAJECTORY", "    &RESTART",
                  "      BACKUP_COPIES 0",
                  "    &END RESTART", "  &END PRINT", "&END MOTION"]
    text = "\n".join(lines) + "\n"
    effective = Structure(structure.symbols.copy(), positions, [row.copy() for row in cell],
                          [axis in periodic for axis in "XYZ"], structure.source, structure.frame)
    from .menu_registry import MENU_LAYOUT_VERSION
    manifest = {"schema_version": SCHEMA_VERSION, "generator": {"name": "cp2kkit", "version": __version__,
                                                              "menu_layout_version": MENU_LAYOUT_VERSION},
                "target_software": "CP2K", "target_version": s.cp2k_version,
                "runtime_version": None, "runtime_validated": False,
                "references": {"Multiwfn": list(MULTIWFN_CITATIONS),
                               "terms_url": "http://sobereva.com/multiwfn/download.html",
                               "notice": "THIRD_PARTY_NOTICES.md"},
                "settings": asdict(s),
                'nonlocal_correlation': nonlocal_xc,
                'basis_selection': {'id': s.basis, 'number': basis_option(s.basis).number, 'registry_version': 1},
                'basis_validation': {'status': 'data_checked' if data_checked else 'unverified_template',
                                     'scope': 'selected-entry structure, aliases, nuclear charges and source bytes only' if all_electron
                                              else 'selected-entry structure, aliases, q and source bytes only',
                                     'runtime_validated': False, 'runnable_verified': False},
                "effective_eps_scf": eps, "poisson_solver": solver,
                "restart_template": {"filename": restart_filename, "scf_guess": "RESTART",
                                     "enabled": False, "emitted": False, "filename_commented": False, "guess_commented": False,
                                     "naming_basis": "PROJECT and Gamma/non-Gamma default restart naming",
                                     "runtime_verified": False},
                "wavefunction_output": {"restart_enabled": True, "restart_backup_copies": 0,
                                        "section": "FORCE_EVAL/DFT/SCF/PRINT/RESTART",
                                        "runtime_validated": False},
                "motion_output": {"enabled": optimizing,
                                  "trajectory_format": s.trajectory_format if optimizing else None,
                                  "restart_backup_copies": 0 if optimizing else None,
                                  "trust_radius_angstrom": s.trust_radius if optimizing and s.optimizer in {'BFGS', 'LBFGS'} else None},
                "constraints": {"enabled": bool(fixed_atoms), "fixed_atoms": list(fixed_atoms),
                                "index_base": 1, "index_reference": "generated_structure atom order after source expansion/frame selection",
                                "components_to_fix": "XYZ" if fixed_atoms else None,
                                "coordinate_space": "fractional" if fixed_atoms else None,
                                "keyword_reference": dict(CONSTRAINT_REFERENCE) if fixed_atoms else None,
                                "runtime_validated": False},
                "density_output": {"enabled": bool(density_enabled),
                                   "electron_density": bool(density_enabled),
                                   "spin_density": bool(density_enabled and uks),
                                   "stride": list(stride) if density_enabled else None,
                                   "each": density_each if density_enabled else None,
                                   "add_last": "NUMERIC" if density_enabled else None,
                                   "append": False, "filename_override": None,
                                   "density_meaning": None if all_electron else "GPW pseudopotential valence electron density",
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
                          "cutoff": "Ry", "rel_cutoff": "Ry", "trust_radius": "angstrom", "smearing": "K", "pressure": "bar",
                          "max_dr": "bohr", "rms_dr": "bohr", "max_force": "hartree/bohr", "rms_force": "hartree/bohr"},
                "valence_electron_count": None if all_electron else electrons,
                'explicit_electron_count': electrons,
                'electron_count_model': 'all_electron' if all_electron else 'pseudopotential_valence',
                "kinds": kinds, "data_sources": data_sources,
                "emitted_data_files": {"basis": emitted_basis_files, "potential": emitted_potential,
                                       "dispersion": files['dispersion'] if s.dispersion != 'none' else None,
                                       "xc_kernel": nonlocal_xc['kernel_file']},
                "source_structure": structure.to_dict(), "generated_structure": effective.to_dict(),
                "coordinates_translated": translated, "warnings": warnings,
                "input_text": text, "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    manifest['method_profile'] = {
        'functional': s.functional, 'qs_method': qs_method, 'gapw': gapw,
        'family': method_profile.family, 'xc_components': list(method_profile.components),
        'native_shortcut': None if method_profile.components or method_profile.parametrization else (method_profile.native or s.functional),
        'pbe_parametrization': method_profile.parametrization,
        'exact_exchange_fraction': 0.0, 'kinetic_energy_density': method_profile.family == 'meta-GGA',
        'generator_scope': 'GPW Gamma ENERGY/ENERGY_FORCE/GEO_OPT without +U' if method_profile.restricted else 'existing GPW/GAPW and task restrictions',
        'ot_algorithm': (ot_algorithm or 'STRICT') if s.scf == 'ot' else None, 'ngrids': ngrids,
        'ngrids_selection': 'whole-system workflow lock' if _common_ngrids is not None else 'effective orbital basis policy',
        'xc_backend': ('Libxc' if method_profile.components else 'CP2K-native + Libxc') if method_profile.libxc else 'CP2K-native',
        'libxc_required': method_profile.libxc, 'libxc_user_asserted': s.libxc_available,
        'build_verified': False, 'dispersion_reference': s.functional if s.dispersion != 'none' else None,
        'basis_files': basis_files, 'potential_file': files['potential'],
        'catalog_reference_version': None if all_electron else '2026.2',
        'catalog_sources': [dict(source) for source in (AE_SOURCES if all_electron else CATALOG_SOURCES)], 'runtime_validated': False,
        'potential_approximations': [el for el, r in element_records.items() if r['potential_approximation']]}
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
    """Stage before publication; only regular .inp targets may be replaced.

    No source/data file, symlink or non-.inp existing output is replaceable.
    Optional JSON keeps exclusive creation. A pre-publication failure leaves
    the old input intact; normal staging failures clean only our own files.
    """
    if settings.density_difference:
        from .density_workflow import write_difference
        return write_difference(structure, settings, output)
    text, manifest = generate_input(structure, settings)
    output = Path(output)
    sidecar = Path(str(output)+".json") if settings.write_json else None
    if output.is_symlink():
        raise OutputExists(f'Refusing to overwrite a symbolic link: {output}')
    sources = [structure.source, *manifest['data_sources'].values()]
    for source in sources:
        if isinstance(source, dict) and source.get('path'):
            path = Path(source['path'])
            if (output.resolve() == path.resolve()
                    or output.exists() and path.exists() and output.samefile(path)):
                raise KitError(f'Refusing to replace a source/data file: {output}')

    def replaceable():
        if not os.path.lexists(output):
            return False
        mode = output.lstat().st_mode
        if output.suffix.lower() != '.inp' or not stat.S_ISREG(mode):
            raise OutputExists(f'Refusing to overwrite non-.inp or non-regular target: {output}')
        return True

    replaceable()
    warnings = list(manifest['warnings'])
    if sidecar is None and os.path.lexists(Path(str(output)+'.json')):
        warnings.append('Existing JSON sidecar was not updated or deleted; it may describe an earlier input.')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=output.parent, prefix=f'.{output.name}.',
                                         suffix='.tmp', delete=False) as inp:
            temporary = Path(inp.name)
            inp.write(text)
            inp.flush()
            os.fsync(inp.fileno())
        with ExitStack() as stack:
            if sidecar is not None:
                log = stack.enter_context(new_file(sidecar))
                log.write(json_text(manifest))
                log.flush()
                os.fsync(log.fileno())
                log.close()  # Finish all JSON writes before replacing input.
            if replaceable():
                os.replace(temporary, output)
            else:
                try:
                    os.link(temporary, output)  # Exclusive for new names, including non-.inp.
                except FileExistsError as exc:
                    raise OutputExists(f'Output appeared during publication; retry: {output}') from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output, sidecar, warnings
