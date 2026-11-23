"""Bounded molecular and periodic surface partial-Hessian vibrational input policy.

Reference-based assembly: Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp;
see third_party/multiwfn/PROVENANCE.md and the required citations in inputgen.
Keyword and force paths checked against CP2K v2026.2 tagged source.
"""
import math

from .errors import KitError
from .functional_registry import parse_functional
from .basis_registry import basis_option
from .structure import BOHR_TO_ANGSTROM

TASK = 'VIBRATIONAL_ANALYSIS'
DEFAULT_DISPLACEMENT_BOHR = 0.01
DEFAULT_EPS_SCF = 1e-8
EPS_DEFAULT = 1e-14
SOURCE_ROOT = 'https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/'
SOURCES = {
    'motion/input_cp2k_vib.F': 'a7a4fd4b7f427fa3c26f7182e2c1b2a98b4aa201ed60e46b60d5624bab285d8c',
    'motion/vibrational_analysis.F': '4f8f911e5948ac5990b18a472ee0cf84fc8b103b356d62691224313e5b608965',
    'qs_force.F': 'ad1c3faee83409cf39913fd8935dac537e77c02b9799ae22ca1de0fca5a4bff0',
    'replica_methods.F': 'c9ecc2b600f595ff9b21f4eaaf317ff0aa0b31fd092ba4cc27365245d999d7b7',
    'input_cp2k_scf.F': '23f7fdd4abfdf64904f0c95ed6dd672f6ca645c0abb7f91b60347ab6693bacf1',
    'start/cp2k_runs.F': '4f476dbfe499822715ab20cfa1facd866508e9aa5cdf4a6c51e2cef713e82961',
    'input_cp2k_poisson.F': 'cbd8e7446f05723800dd0550842ce966341fedd2cd14eb7e903ca5f73fa400a0',
    'pw/mt_util.F': '33b9978bd6bafda8b03a32806ac2117e0bb0597f983efcecf59e769368774b38',
}


# Additional links in the tagged displaced-force path, only for pair dispersion.
DISPERSION_SOURCES = {
    'f77_interface.F': 'f744057c28f560e73a48077c3cd7f5a9fba26f84771e9c6d87d24401fcdea43a',
    'force_env_methods.F': '82b08e7e477c1fe2f1f0ce82b80202dd93863b0b3ab420fa9ba5fe1f35851ada',
    'qs_energy.F': 'b8a96d8e99938dd822260a92c370b7b2a88068a377fef58db65dafcf62c457ce',
    'qs_energy_init.F': '7b57ace7f2fbc7efb3dfe93eaa10d840a13a3f43827805515e212841ac1939fe',
    'qs_dispersion_pairpot.F': '47ec827a9760fa38ba53e055e22884d2bbe7631b61ea2087a747e8c03bda8889',
    'qs_dispersion_d3.F': '447982f6ff48157367fde23cb24af58d21b0728a5b0c75ec77923544c02c2f66',
    'qs_force_types.F': '9539bc1a9c36194231ccee5b02134bac59e23d4f747e3c0daeb5756423a1e37b',
}


def _positive(value, name):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise KitError(f'{name} must be a finite positive number')


def _check_dx_resolvable(positions, displacement_bohr):
    # Native finite differences divide by 2*DX on double-precision bohr coordinates.
    # Both 2*DX and the +/-DX displaced coordinates must stay finite and distinct.
    if not math.isfinite(2.0 * displacement_bohr):
        raise KitError('Vibrational DX overflows finite-difference 2*DX arithmetic; '
                       'choose a finite representable displacement and converge it independently')
    for row in positions:
        for value in row:
            coord = value / BOHR_TO_ANGSTROM
            plus = coord + displacement_bohr
            minus = coord - displacement_bohr
            if not (math.isfinite(coord) and math.isfinite(plus) and math.isfinite(minus)):
                raise KitError('Vibrational DX overflows displaced bohr coordinates; '
                               'choose a finite representable displacement and converge it independently')
            if plus == coord or minus == coord:
                raise KitError('Vibrational DX is too small to resolve at the generated coordinate precision; '
                               'choose a representable displacement and converge it independently')


def validate_request(settings):
    """Run before method/workflow dispatch so new requests cannot be ignored."""
    dx = settings.vibration_displacement_bohr
    if settings.run_type != TASK:
        if dx is not None:
            raise KitError('vibration_displacement_bohr requires VIBRATIONAL_ANALYSIS; reset it to auto/None')
        return
    if dx is not None:
        _positive(dx, 'vibration_displacement_bohr [bohr]')
    if settings.eps_scf is not None:
        _positive(settings.eps_scf, 'Vibrational EPS_SCF')
        if settings.eps_scf > DEFAULT_EPS_SCF:
            raise KitError('Vibrational EPS_SCF must be <= 1e-8; explicit values are never tightened silently')
    try:
        pbe = parse_functional(settings.functional) == 'PBE'
    except ValueError as exc:
        raise KitError(str(exc)) from exc
    if settings.cp2k_version != '2026.2' or settings.method != 'DFT' or not pbe:
        raise KitError('VIBRATIONAL_ANALYSIS supports only target 2026.2 PBE GPW DFT')
    if settings.kpoints != (1, 1, 1):
        raise KitError('VIBRATIONAL_ANALYSIS currently requires Gamma-only k-points (1 1 1)')
    if settings.scf == 'ot' and settings.ot_algorithm not in (None, 'STRICT'):
        raise KitError('VIBRATIONAL_ANALYSIS OT requires STRICT algorithm; no solver is changed')
    if settings.dft_plus_u or settings.admm or settings.ri_hfx or settings.density_difference:
        raise KitError('VIBRATIONAL_ANALYSIS excludes +U, ADMM/RI and density-difference workflows')
    if (settings.electron_density or settings.spin_density or settings.hartree_potential
            or settings.mo_cubes):
        raise KitError('VIBRATIONAL_ANALYSIS CUBE outputs are outside the initial task scope; reset requests explicitly')


def mt_box(cell, positions, displacement_bohr):
    """Necessary atomic-envelope check only; electronic density is not available.

    This first MT task policy accepts positive axis-aligned orthorhombic cells.
    Never resize, rotate or recenter an explicit/source cell or its coordinates.
    """
    if any(cell[i][j] != 0.0 for i in range(3) for j in range(3) if i != j) or any(cell[i][i] <= 0 for i in range(3)):
        raise KitError('Vibrational MT preset requires a positive axis-aligned orthorhombic cell; no cell is transformed')
    lengths = [cell[j][j] for j in range(3)]
    lower = [min(row[j] for row in positions) for j in range(3)]
    upper = [max(row[j] for row in positions) for j in range(3)]
    _check_dx_resolvable(positions, displacement_bohr)
    delta = displacement_bohr * BOHR_TO_ANGSTROM
    spans = [upper[j] - lower[j] + 2*delta for j in range(3)]
    required = [2*span for span in spans]
    if any(not math.isfinite(v) for v in (*spans, *required)):
        raise KitError('Vibrational MT displaced atomic envelope must be finite')
    if any(lengths[j] <= required[j] for j in range(3)):
        raise KitError('Vibrational MT box must exceed twice the displaced atomic span on every axis; '
                       'increase vacuum or explicitly supply a larger cell. Electronic density needs additional space')
    if any(lower[j] - delta <= 0 or upper[j] + delta >= lengths[j] for j in range(3)):
        raise KitError('Vibrational MT displaced atoms must lie inside the supplied cell; '
                       'place the molecule explicitly, no automatic recentering is performed')
    return {'cell_lengths_angstrom': lengths, 'displaced_atomic_span_angstrom': spans,
            'minimum_lengths_from_atoms_angstrom': required,
            'check_scope': 'necessary atomic-envelope lower bound, not electronic-density containment',
            'density_extent_verified': False}


def resolve(settings, *, periodic, all_electron, elements, cell, positions, fixed_atoms=()):
    """Check resolved geometry, constraints and every selected basis, not only UI state."""
    if settings.run_type != TASK:
        return None
    if all_electron:
        raise KitError('VIBRATIONAL_ANALYSIS requires GPW pseudopotentials; GAPW is outside this scope')
    if periodic not in ('NONE', 'XYZ'):
        raise KitError('VIBRATIONAL_ANALYSIS supports only isolated PERIODIC NONE or periodic partial-Hessian PERIODIC XYZ')
    overrides = dict(settings.basis_overrides)
    if any(basis_option(overrides.get(el, settings.basis)).protocol != 'classic' for el in elements):
        raise KitError('VIBRATIONAL_ANALYSIS requires classic MOLOPT/UCL orbital bases; no UZH/custom/GAPW')
    dx = (DEFAULT_DISPLACEMENT_BOHR if settings.vibration_displacement_bohr is None
          else settings.vibration_displacement_bohr)
    sources = SOURCES if settings.dispersion == 'none' else {**SOURCES, **DISPERSION_SOURCES}
    if periodic == 'NONE':
        if (settings.scf != 'ot' or settings.ot_algorithm not in (None, 'STRICT')
                or settings.smearing is not None or settings.added_mos != 0):
            raise KitError('Molecular VIBRATIONAL_ANALYSIS requires Gamma OT/STRICT without smearing; no solver is changed')
        if len(positions) < 2:
            raise KitError('Molecular VIBRATIONAL_ANALYSIS requires at least two atoms; '
                           'an isolated single atom has no internal vibrational modes')
        return {
            'scope': 'molecular',
            'algorithm': 'central_finite_difference_of_forces',
            'displacement_bohr': dx,
            'displacement_origin': 'native_default_explicit' if settings.vibration_displacement_bohr is None else 'user_explicit',
            'eps_scf': settings.eps_scf if settings.eps_scf is not None else DEFAULT_EPS_SCF,
            'eps_scf_origin': 'task_preset' if settings.eps_scf is None else 'user_explicit',
            'qs_eps_default': EPS_DEFAULT, 'qs_eps_default_origin': 'task_preset',
            'poisson_solver': 'MT', 'poisson_solver_origin': 'task_preset',
            'mt_box': mt_box(cell, positions, dx),
            'nproc_rep': 1, 'nproc_rep_origin': 'native_default_explicit',
            'fully_periodic': False, 'fully_periodic_origin': 'native_default_explicit',
            'intensities': False, 'thermochemistry': False,
            'program_run_info': True, 'program_run_info_origin': 'task_preset',
            'active_atoms': list(range(1, len(positions) + 1)),
            'active_atom_count': len(positions),
            'fixed_atom_count': 0,
            'stationary_point_verified': False, 'runtime_validated': False,
            'sources': [{'url': SOURCE_ROOT + path, 'sha256': digest} for path, digest in sources.items()],
        }

    # Bounded periodic surface partial-Hessian branch (PERIODIC XYZ + whole-atom FIXED_ATOMS).
    if not fixed_atoms:
        raise KitError('Periodic VIBRATIONAL_ANALYSIS requires explicit --fixed-atoms for a partial Hessian '
                       '(at least one fixed and one active atom); full-system periodic Gamma vibrations remain outside this scope')
    if len(fixed_atoms) >= len(positions):
        raise KitError('Periodic partial-Hessian VIBRATIONAL_ANALYSIS requires at least one unfixed (active) atom')
    fixed_set = set(fixed_atoms)
    active_atoms = [i for i in range(1, len(positions) + 1) if i not in fixed_set]
    _check_dx_resolvable([positions[i - 1] for i in active_atoms], dx)
    periodic_sources = {path: digest for path, digest in sources.items() if path != 'pw/mt_util.F'}
    return {
        'scope': 'periodic_partial_hessian',
        'algorithm': 'central_finite_difference_of_forces',
        'displacement_bohr': dx,
        'displacement_origin': 'native_default_explicit' if settings.vibration_displacement_bohr is None else 'user_explicit',
        'eps_scf': settings.eps_scf if settings.eps_scf is not None else DEFAULT_EPS_SCF,
        'eps_scf_origin': 'task_preset' if settings.eps_scf is None else 'user_explicit',
        'qs_eps_default': EPS_DEFAULT, 'qs_eps_default_origin': 'task_preset',
        'poisson_solver': 'PERIODIC', 'poisson_solver_origin': 'task_preset',
        'mt_box': None,
        'nproc_rep': 1, 'nproc_rep_origin': 'native_default_explicit',
        'fully_periodic': True, 'fully_periodic_origin': 'task_preset',
        'intensities': False, 'thermochemistry': False,
        'program_run_info': True, 'program_run_info_origin': 'task_preset',
        'active_atoms': active_atoms,
        'active_atom_count': len(active_atoms),
        'fixed_atom_count': len(fixed_atoms),
        'stationary_point_verified': False, 'runtime_validated': False,
        'sources': [{'url': SOURCE_ROOT + path, 'sha256': digest} for path, digest in periodic_sources.items()],
    }


def input_lines(vibration):
    if vibration is None:
        return []
    periodic_flag = 'T' if vibration['fully_periodic'] else 'F'
    return ['&VIBRATIONAL_ANALYSIS',
            f"  DX [bohr] {vibration['displacement_bohr']:.17g}",
            '  NPROC_REP 1', f'  FULLY_PERIODIC {periodic_flag}', '  INTENSITIES F', '  THERMOCHEMISTRY F',
            '  &PRINT', '    &PROGRAM_RUN_INFO ON', '      FILENAME __STD_OUT__',
            '    &END PROGRAM_RUN_INFO', '  &END PRINT', '&END VIBRATIONAL_ANALYSIS']


UKS_WARNING = ('For UKS vibrational analysis, displaced-geometry SCF solutions are not verified to remain '
               'on the same spin/electronic state.')

SMEARING_WARNING = ('Diagonalization with Fermi-Dirac smearing in periodic vibrational analysis requires '
                    'independent verification of electronic temperature, ADDED_MOS, Gamma supercell size and force convergence.')

WARNINGS = (
    'Vibrational input generation does not establish a stationary point, a minimum, vibrational convergence or physical validity. '
    'Use an explicitly selected tightly optimized geometry; frame numbers and filenames are not convergence evidence.',
    'Converge displacement, SCF, basis, integration grid and isolated box for forces/low frequencies independently. '
    'The 1e-8 EPS_SCF and 1e-14 QS EPS_DEFAULT task presets are not accuracy guarantees; cutoff/rel_cutoff are unchanged.',
    'Vibrational Poisson solver MT is an explicit task preset with PERIODIC NONE, not a switch to periodic electrostatics. '
    'MT requires a cell at least twice the electronic-density extent. Only a necessary displaced-atom envelope is checked; '
    'electronic tails, molecular placement and box convergence remain unverified. No supplied cell or SCF solver is changed.',
    'Vibrational PROGRAM_RUN_INFO is explicitly ON at global LOW verbosity: displaced/reference forces and Hessian '
    'diagnostics go to stdout and may be large. The native label "Minimum Structure" refers to the restored input geometry, '
    'not proof of optimization or stationarity. No output is interpreted by the generator.',
    'NPROC_REP 1 is processors per replica, not total processors or a request to run a single replica. '
    'CP2K distributes finite displacements over replica environments at runtime; resource tuning is not exposed here.',
)

PERIODIC_WARNINGS = (
    'Vibrational input generation does not establish a stationary point, a minimum, vibrational convergence or physical validity. '
    'Use an explicitly selected tightly optimized geometry; frame numbers and filenames are not convergence evidence.',
    'Converge displacement, SCF, basis, integration grid, slab thickness and vacuum for forces/low frequencies independently. '
    'The 1e-8 EPS_SCF and 1e-14 QS EPS_DEFAULT task presets are not accuracy guarantees; cutoff/rel_cutoff are unchanged.',
    'Periodic partial-Hessian vibrational analysis fixes selected atoms in fractional XYZ and sets FULLY_PERIODIC T '
    '(no gas-phase rotational projection), displacing only active atoms to produce 3 * active_atom_count modes. '
    'Frozen-substrate coupling, periodic phonon dispersion and q-point integration are excluded.',
    'Vibrational PROGRAM_RUN_INFO is explicitly ON at global LOW verbosity: displaced/reference forces and Hessian '
    'diagnostics go to stdout and may be large. The native label "Minimum Structure" refers to the restored input geometry, '
    'not proof of optimization or stationarity. No output is interpreted by the generator.',
    'NPROC_REP 1 is processors per replica, not total processors or a request to run a single replica. '
    'CP2K distributes finite displacements over replica environments at runtime; resource tuning is not exposed here.',
)
