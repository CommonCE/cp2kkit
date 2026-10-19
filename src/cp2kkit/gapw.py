"""Versioned AE setup and Multiwfn-style multigrid emission policy.

Starting settings only, not convergence or native-execution evidence.
GAPW tolerances/atomic grids and omitted NGRIDS use CP2K defaults.
"""

from .errors import KitError

GAPW_PROFILES = ('auto', 'native')
# Multiwfn outCP2Kinp ibas 3/4/5; registry IDs, not name substring guesses.
FIVE_GRID_BASES = frozenset(('molopt-tzvp', 'molopt-tzv2p', 'molopt-tzv2px'))


def resolve_ngrids(records):
    """Any effective matching basis requests five grids; otherwise omit NGRIDS."""
    return 5 if any(r['basis_id'] in FIVE_GRID_BASES for r in records.values()) else None


def resolve_gapw(settings, records):
    if settings.gapw_profile not in GAPW_PROFILES:
        raise KitError('gapw_profile must be auto or native')
    # Both legacy profile names retain native tolerances; the latest explicit
    # user policy requires an emitted OT algorithm even for the native profile.
    algorithm = (settings.ot_algorithm or 'IRAC') if settings.scf == 'ot' else None
    derived = [
        {'setting': 'QS/METHOD', 'value': 'GAPW', 'reason': 'All-electron nuclear potentials require GAPW, not GPW.'},
        {'setting': 'KIND/POTENTIAL', 'value': 'ALL', 'reason': 'No pseudopotential core removal in the selected electron model.'},
        {'setting': 'electron_count_model', 'value': 'sum(Z)-charge', 'reason': 'Include core electrons without changing charge or multiplicity.'},
    ]
    if settings.scf == 'ot':
        derived.append({'setting': 'SCF/OT/PRECONDITIONER', 'value': 'FULL_ALL',
                        'reason': 'Retain generator preconditioner; consistent with Multiwfn GAPW guidance.'})
        derived.append({'setting': 'SCF/OT/ALGORITHM', 'value': algorithm,
                        'source': 'user' if settings.ot_algorithm else 'automatic',
                        'reason': ('Explicit user selection overrides the numerical profile.' if settings.ot_algorithm
                                   else 'User-requested explicit IRAC default for all all-electron bases.')})
    return {'profile': settings.gapw_profile, 'profile_version': 4, 'qs': {},
            'kind': {}, 'ngrids': resolve_ngrids(records),
            'cp2k_default_controls': ['EPSFIT', 'EPSRHO0', 'EPSSVD', 'LEBEDEV_GRID', 'RADIAL_GRID', 'NGRIDS'],
            'ot_algorithm': algorithm, 'automatic_settings': derived, 'convergence_verified': False,
            'preserved': ['charge', 'multiplicity', 'magnetism', 'functional', 'dispersion',
                          'cutoff', 'rel_cutoff', 'eps_scf', 'periodic', 'scf', 'kpoints', 'ot_algorithm']}
