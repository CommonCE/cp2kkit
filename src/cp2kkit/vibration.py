"""Bounded molecular finite-difference input policy, not a frequency calculator.

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


def _positive(value, name):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise KitError(f'{name} must be a finite positive number')


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
    if (settings.scf != 'ot' or settings.ot_algorithm not in (None, 'STRICT')
            or settings.smearing is not None or settings.kpoints != (1, 1, 1)):
        raise KitError('VIBRATIONAL_ANALYSIS requires Gamma OT/STRICT without smearing; no solver is changed')
    if settings.magnetism is not None or settings.multiplicity not in (None, 1):
        raise KitError('VIBRATIONAL_ANALYSIS currently requires closed-shell RKS without explicit magnetism')
    if (settings.dispersion != 'none' or settings.dft_plus_u or settings.admm
            or settings.ri_hfx or settings.density_difference):
        raise KitError('VIBRATIONAL_ANALYSIS excludes dispersion, +U, ADMM/RI and density-difference workflows')
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
    # Native finite differences act on double-precision bohr coordinates.
    # A positive DX that rounds away cannot produce a displaced force sample.
    if any(value/BOHR_TO_ANGSTROM + displacement_bohr == value/BOHR_TO_ANGSTROM
           or value/BOHR_TO_ANGSTROM - displacement_bohr == value/BOHR_TO_ANGSTROM
           for row in positions for value in row):
        raise KitError('Vibrational DX is too small to resolve at the generated coordinate precision; '
                       'choose a representable displacement and converge it independently')
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


def resolve(settings, *, periodic, all_electron, uks, elements, cell, positions):
    """Check resolved spin, geometry and every selected basis, not only UI state."""
    if settings.run_type != TASK:
        return None
    if periodic != 'NONE' or all_electron or uks:
        raise KitError('VIBRATIONAL_ANALYSIS requires isolated PERIODIC NONE, GPW and closed-shell RKS')
    if len(positions) < 2:
        raise KitError('Molecular VIBRATIONAL_ANALYSIS requires at least two atoms; '
                       'an isolated single atom has no internal vibrational modes')
    overrides = dict(settings.basis_overrides)
    if any(basis_option(overrides.get(el, settings.basis)).protocol != 'classic' for el in elements):
        raise KitError('VIBRATIONAL_ANALYSIS requires classic MOLOPT/UCL orbital bases; no UZH/custom/GAPW')
    dx = (DEFAULT_DISPLACEMENT_BOHR if settings.vibration_displacement_bohr is None
          else settings.vibration_displacement_bohr)
    return {
        'algorithm': 'central_finite_difference_of_forces',
        'displacement_bohr': dx,
        'displacement_origin': 'native_default_explicit' if settings.vibration_displacement_bohr is None else 'user_explicit',
        'eps_scf': settings.eps_scf if settings.eps_scf is not None else DEFAULT_EPS_SCF,
        'eps_scf_origin': 'task_preset' if settings.eps_scf is None else 'user_explicit',
        'qs_eps_default': EPS_DEFAULT, 'qs_eps_default_origin': 'task_preset',
        'poisson_solver': 'MT', 'poisson_solver_origin': 'task_preset',
        'mt_box': mt_box(cell, positions, dx),
        'nproc_rep': 1, 'nproc_rep_origin': 'native_default_explicit',
        'fully_periodic': False, 'intensities': False, 'thermochemistry': False,
        'program_run_info': True, 'program_run_info_origin': 'task_preset',
        'stationary_point_verified': False, 'runtime_validated': False,
        'sources': [{'url': SOURCE_ROOT + path, 'sha256': digest} for path, digest in SOURCES.items()],
    }


def input_lines(vibration):
    if vibration is None:
        return []
    return ['&VIBRATIONAL_ANALYSIS',
            f"  DX [bohr] {vibration['displacement_bohr']:.17g}",
            '  NPROC_REP 1', '  FULLY_PERIODIC F', '  INTENSITIES F', '  THERMOCHEMISTRY F',
            '  &PRINT', '    &PROGRAM_RUN_INFO ON', '      FILENAME __STD_OUT__',
            '    &END PROGRAM_RUN_INFO', '  &END PRINT', '&END VIBRATIONAL_ANALYSIS']


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
