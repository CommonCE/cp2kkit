"""Versioned automatic numerical setup for explicitly selected all-electron bases.

This is a starting configuration, not convergence or native-execution evidence.
GAPW split tolerances and atom-centered grids are left to CP2K defaults.
Only the grid count and basis-aware OT algorithm are derived. No cutoff/spin repair.
"""

from .errors import KitError

GAPW_PROFILES = ('auto', 'native')
DEFAULT_NGRIDS = 5


def resolve_gapw(settings, records):
    if settings.gapw_profile not in GAPW_PROFILES:
        raise KitError('gapw_profile must be auto or native')
    automatic = settings.gapw_profile == 'auto'
    pob = any(r['basis_id'].startswith('ae-pob-') for r in records.values())
    qs, kind = {}, {}  # Do not emit GAPW tolerances or atom-centered grid overrides.
    algorithm = (settings.ot_algorithm or (('IRAC' if pob else 'STRICT') if automatic else None)) if settings.scf == 'ot' else None
    derived = [
        {'setting': 'QS/METHOD', 'value': 'GAPW', 'reason': 'All-electron nuclear potentials require GAPW, not GPW.'},
        {'setting': 'KIND/POTENTIAL', 'value': 'ALL', 'reason': 'No pseudopotential core removal in the selected electron model.'},
        {'setting': 'electron_count_model', 'value': 'sum(Z)-charge', 'reason': 'Include core electrons without changing charge or multiplicity.'},
        {'setting': 'MGRID/NGRIDS', 'value': DEFAULT_NGRIDS, 'reason': 'User-requested universal five-grid default; convergence remains unverified.'},
    ]
    if settings.scf == 'ot':
        derived.append({'setting': 'SCF/OT/PRECONDITIONER', 'value': 'FULL_ALL',
                        'reason': 'Retain generator preconditioner; consistent with Multiwfn GAPW guidance.'})
    if algorithm:
        derived.append({'setting': 'SCF/OT/ALGORITHM', 'value': algorithm,
                        'source': 'user' if settings.ot_algorithm else 'automatic',
                        'reason': ('Explicit user selection overrides the numerical profile.' if settings.ot_algorithm
                                   else 'Multiwfn uses IRAC for pob orbital bases; otherwise retain native STRICT.')})
    return {'profile': settings.gapw_profile, 'profile_version': 3, 'qs': qs,
            'kind': kind, 'ngrids': DEFAULT_NGRIDS,
            'cp2k_default_controls': ['EPSFIT', 'EPSRHO0', 'EPSSVD', 'LEBEDEV_GRID', 'RADIAL_GRID'], 'ot_algorithm': algorithm,
            'automatic_settings': derived, 'convergence_verified': False,
            'preserved': ['charge', 'multiplicity', 'magnetism', 'functional', 'dispersion',
                          'cutoff', 'rel_cutoff', 'eps_scf', 'periodic', 'scf', 'kpoints', 'ot_algorithm']}
