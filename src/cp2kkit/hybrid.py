"""Bounded direct-HFX setup; no execution, auxiliary basis or solver fallback.

XC/HF composition and periodic radius policy reference Multiwfn outCP2Kinp;
keywords/units are checked against CP2K v2026.2. See feature provenance.
"""
import math
from dataclasses import replace
from pathlib import Path

from .cp2k_data import cp2k_path
from .errors import KitError
from .functional_registry import FUNCTIONAL_PROFILES
from .io import read_text
from .structure import check_cell


HFX_FIELDS = ('hf_eps_schwarz', 'hf_memory', 'hf_cutoff_radius', 'pbeh_fraction')
HFX_SOURCE_HASHES = {
    'xc/xc_libxc.F': '5c7d6d9e1aa6664297e761407530fb1eb5057db87bb38876920f0cedb9ef5e45',
    'xc/xc_libxc_wrap.F': 'fc0eb02140f09001de9ca35c69589ddefe4ffcf2d84f3fe359d97e6deb0ee40b',
    'input_cp2k_check.F': 'e1f26b06bbc6121a31f9c50c4056dbe43f08a328425c46010566b4e6555ccb5d',
    'input_cp2k_xc.F': '332cda33e1d90c5e3002fcc1e965633d009f28caadbc98c188474cd26e314e3b',
    'input_cp2k_hfx.F': '468ef8c01d0285e2341617d9df269dd3eb227c7006da14937f17acad2db7177f',
    'xc/xc_xwpbe.F': '652ef1c975b9533e8c4fe1e1d0e43d39887e715e3c0c9496f871924033261dda',
    'xc/xc_vwn.F': '788ec05f5f5283b70d8e1b9e6bcf50c2d6989b2ccf7a20b70ac34c39d7ef3803',
    'hfx_derivatives.F': '52961d2ffba8baabbe44a05b77a410a1e95f19fb943ec46e8363ac97bc004967',
    'qs_dispersion_utils.F': '587b8b35f0fadba226335ec4b45b5290260ea05c67eb8b77b8ec1511ba4bd337',
}


def finite_real(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def resolve_functional(settings):
    """Resolve PBEh once so XC, HF and metadata use the same explicit fraction."""
    profile = FUNCTIONAL_PROFILES[settings.functional]
    fraction = settings.pbeh_fraction
    if settings.functional != 'PBEH':
        if fraction is not None:
            raise KitError('pbeh_fraction requires PBEH; reset it explicitly for other DFT methods')
        return profile
    if not finite_real(fraction) or not 0 < fraction <= 1:
        raise KitError('PBEH requires explicit pbeh_fraction in (0, 1]; use PBE for zero HF exchange')
    return replace(profile, exact_exchange_fraction=fraction,
                   xc_parameters=(('PBE', (('SCALE_X', format(1-fraction, '.17g')),
                                           ('SCALE_C', '1.0'))),))


def validate_hfx_controls(settings, profile):
    """Reject malformed or inactive explicit requests before any file publication."""
    eps = settings.hf_eps_schwarz
    if not finite_real(eps) or not 0 < eps < 1:
        raise KitError('hf_eps_schwarz must be finite and between 0 and 1 (exclusive)')
    if type(settings.hf_memory) is not int or settings.hf_memory < 1:
        raise KitError('hf_memory must be a positive integer [MiB per MPI process]')
    radius = settings.hf_cutoff_radius
    if radius is not None and (not finite_real(radius) or radius <= 0):
        raise KitError('hf_cutoff_radius must be finite and positive [angstrom], or auto/None')
    if not profile.hybrid and (eps != 1e-6 or settings.hf_memory != 512 or radius is not None):
        raise KitError('Explicit HF controls require a supported hybrid functional; restore defaults explicitly')


def cell_heights(cell):
    """Face-to-face perpendicular spacings, not edge lengths, for skew cells."""
    def cross(a, b):
        return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
    normals = [cross(cell[1], cell[2]), cross(cell[2], cell[0]), cross(cell[0], cell[1])]
    volume = abs(sum(a*b for a, b in zip(cell[0], normals[0])))
    return [volume/math.hypot(*normal) for normal in normals]


def resolve_hfx(settings, profile, periodic, cell, data_root):
    """Return effective metadata and warnings; data checks are read-only byte checks."""
    if not profile.hybrid:
        return None, []
    if profile.exact_exchange_fraction is None:
        raise KitError('PBEH HFX rendering requires an explicit resolved fraction')
    if periodic not in {'NONE', 'XYZ'}:
        raise KitError('Direct HFX currently supports periodic NONE or XYZ only; low-dimensional PBC requires a separate audit')
    warnings = ['Direct four-center HFX requires a suitable Libint-enabled CP2K build; build/runtime support is not probed. '
                'Converge EPS_SCHWARZ, SCF, basis and cell independently. ADMM and RI-HFX are not enabled.',
                f'HFX MAX_MEMORY={settings.hf_memory} MiB per MPI process is not total job memory or a scheduler request; '
                'budget other CP2K arrays and rank/thread counts separately.']
    radius, limit, heights = None, None, None
    table, source = None, None
    if profile.omega is not None:
        operator = 'SHORTRANGE'
        if settings.hf_cutoff_radius is not None:
            raise KitError('HSE06 uses SHORTRANGE OMEGA=0.11; hf_cutoff_radius is only for periodic global hybrids')
        policy = 'CP2K short-range cutoff from OMEGA and EPS_SCHWARZ; CUTOFF_RADIUS omitted'
    elif periodic == 'NONE':
        operator = 'COULOMB'
        if settings.hf_cutoff_radius is not None:
            raise KitError('Isolated global hybrids use full COULOMB; hf_cutoff_radius requires periodic XYZ')
        policy = 'full isolated Coulomb operator; no truncation'
    else:
        operator = 'TRUNCATED'
        # Bound using the cell that will actually be emitted (8 decimal places).
        emitted_cell = [[float(f'{v:.8f}') for v in row] for row in cell]
        check_cell(emitted_cell)
        heights = cell_heights(emitted_cell)
        limit = min(heights)/2
        radius = settings.hf_cutoff_radius
        if radius is None:
            radius = min(6.0, min(heights)/2.01)
            policy = 'auto min(6 angstrom, minimum cell face spacing / 2.01)'
        else:
            policy = 'explicit user radius, bounded by half minimum cell face spacing'
        if not math.isfinite(radius) or not 0 < radius < limit:
            raise KitError(f'hf_cutoff_radius must be below half the minimum cell face spacing ({limit:.12g} angstrom); '
                           'no clipping or cell change is performed')
        table = 't_c_g.dat'
        if data_root is not None:
            table = str((Path(data_root)/table).resolve())
            cp2k_path(table)
            _, source = read_text(table)
        else:
            warnings.append('Truncated HFX data t_c_g.dat have not been checked; CP2K resolves them at runtime.')
        warnings.append(f'Periodic global hybrid uses truncated Coulomb HFX at {radius:.12g} angstrom. '
                        'This finite-cell approximation needs radius/supercell convergence, not just SCF convergence.')
    if settings.functional == 'B3LYP':
        warnings.append('B3LYP uses VWN3 correlation (Gaussian/Multiwfn convention), not VWN5; compare only consistent definitions.')
    return {
        'algorithm': 'direct_four_center', 'fraction': profile.exact_exchange_fraction,
        'interaction_potential': operator, 'omega': profile.omega,
        'omega_unit': 'bohr^-1' if profile.omega is not None else None,
        'cutoff_radius_angstrom': radius, 'cutoff_policy': policy,
        'minimum_cell_face_spacing_angstrom': min(heights) if heights else None,
        'eps_schwarz': settings.hf_eps_schwarz, 'screen_on_initial_p': False,
        'max_memory_mib_per_mpi_process': settings.hf_memory, 'eps_storage_scaling': 0.1,
        'truncated_gamma_file': table, 'truncated_gamma_source': source,
        'data_validation': 'source_bytes_only' if source else 'not_checked' if table else 'not_required',
        'admm': False, 'ri_hfx': False, 'build_verified': False, 'runtime_validated': False,
        'keyword_reference_version': '2026.2',
        'sources': [{'url': 'https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/'+file, 'sha256': sha}
                    for file, sha in HFX_SOURCE_HASHES.items()],
    }, warnings


def hf_lines(hfx):
    if hfx is None:
        return []
    lines = ['      &HF', f"        FRACTION {hfx['fraction']!r}",
             '        &SCREENING', f"          EPS_SCHWARZ {hfx['eps_schwarz']:.17g}",
             '          SCREEN_ON_INITIAL_P F', '        &END SCREENING',
             '        &INTERACTION_POTENTIAL', f"          POTENTIAL_TYPE {hfx['interaction_potential']}"]
    if hfx['omega'] is not None:
        lines.append(f"          OMEGA {hfx['omega']:.12g}")
    if hfx['cutoff_radius_angstrom'] is not None:
        lines += [f"          CUTOFF_RADIUS [angstrom] {hfx['cutoff_radius_angstrom']:.17g}",
                  f"          T_C_G_DATA {cp2k_path(hfx['truncated_gamma_file'])}"]
    lines += ['        &END INTERACTION_POTENTIAL', '        &MEMORY',
              f"          MAX_MEMORY {hfx['max_memory_mib_per_mpi_process']}",
              '          EPS_STORAGE_SCALING 0.1', '        &END MEMORY', '      &END HF']
    return lines
