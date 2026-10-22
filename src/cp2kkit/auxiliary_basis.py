"""AUX_FIT registry v1 and checked Gaussian data; no ORB/RI role substitution.

Names reference CP2K v2026.2 BASIS_ADMM_UZH and Multiwfn outCP2Kinp.
No numerical payload or installed-data assumption is bundled.
"""
from types import MappingProxyType

from .basis_registry import BasisOption, BasisRole, OPTIONS, validate_registry
from .basis_resolution import BasisResolver
from .cp2k_data import cp2k_long_path
from .data_catalog import AUXILIARY_SOURCE
from .errors import KitError

AUXILIARY_REGISTRY_VERSION = 1
AUXILIARY_OPTIONS = (
    BasisOption('admm-dz', 200, 'admm-dz', 'ADMM AUX_FIT', 'admm-dz', ('BASIS_ADMM_UZH',),
                potential_sources=(), role=BasisRole.AUX_FIT, functionals=('PBE0', 'HSE06'), protocol='admm'),
    BasisOption('admm-dzp', 201, 'admm-dzp', 'ADMM AUX_FIT', 'admm-dzp', ('BASIS_ADMM_UZH',),
                potential_sources=(), role=BasisRole.AUX_FIT, functionals=('PBE0', 'HSE06'), protocol='admm'),
    BasisOption('admm-tzp', 202, 'admm-tzp', 'ADMM AUX_FIT', 'admm-tzp', ('BASIS_ADMM_UZH',),
                potential_sources=(), role=BasisRole.AUX_FIT, functionals=('PBE0', 'HSE06'), protocol='admm'),
    BasisOption('admm-tz2p', 203, 'admm-tz2p', 'ADMM AUX_FIT', 'admm-tz2p', ('BASIS_ADMM_UZH',),
                potential_sources=(), role=BasisRole.AUX_FIT, functionals=('PBE0', 'HSE06'), protocol='admm'),
)
validate_registry((*OPTIONS, *AUXILIARY_OPTIONS))
BY_AUXILIARY_ID = MappingProxyType({o.id: o for o in AUXILIARY_OPTIONS})
BY_AUXILIARY_NUMBER = MappingProxyType({o.number: o for o in AUXILIARY_OPTIONS})
DEFAULT_AUXILIARY_BASIS = 'admm-dzp'


def auxiliary_option(value):
    if not isinstance(value, str) or value.strip().lower() not in BY_AUXILIARY_ID:
        raise KitError(f'Unsupported AUX_FIT basis {value!r}; use a stable auxiliary ID, not an ORB/RI ID or numeric setting')
    return BY_AUXILIARY_ID[value.strip().lower()]


def parse_auxiliary_basis(value):
    try:
        return auxiliary_option(value).id
    except KitError as exc:
        raise ValueError(str(exc)) from exc


def numbered_auxiliary_basis(number):
    option = BY_AUXILIARY_NUMBER.get(number)
    if option is None:
        raise ValueError(f'Unallocated AUX_FIT number {number}; no ORB-number interpretation')
    return option.id


def resolve_auxiliary(settings, records):
    """Require real ORB/AUX files and verify aliases across the final file union."""
    option = auxiliary_option(settings.aux_basis)
    resolver = BasisResolver(settings)
    paths = resolver.paths(settings.aux_basis_files, option.sources)
    if not paths:
        raise KitError('ADMM requires actual AUX_FIT data: supply --aux-basis-file or --data-dir/CP2K_DATA_DIR; no catalog-only auxiliary template')
    if any(r['basis_source'] is None for r in records.values()):
        raise KitError('ADMM requires checked orbital basis files as well as AUX_FIT files; supply --basis-file or --data-dir')
    auxiliary = {}
    for element, record in records.items():
        q = record['explicit_electrons']
        names = (f'{option.family}-q{q}',)
        entry, name, actual_q = resolver.libraries.select(paths, 'AUX_FIT', element, names, q, match_q_family=True)
        if actual_q != q:
            raise KitError(f'AUX_FIT q is unknown or mismatched for {element}; required q{q}')
        source = dict(entry.source, entry_line=entry.line, entry_sha256=entry.signature)
        cp2k_long_path(source['path'])
        auxiliary[element] = {'id': option.id, 'number': option.number, 'role': option.role.value,
                              'registry_version': AUXILIARY_REGISTRY_VERSION,
                              'basis': name, 'basis_file': source['path'], 'basis_q': actual_q,
                              'basis_source': source, 'data_validation': 'data_checked',
                              'physical_pairing_validated': False}
    # CP2K searches the whole emitted BASIS_SET_FILE_NAME union for either role.
    # Reparse with the requested Gaussian role; never compare role-dependent hashes.
    files = tuple(sorted({r['basis_file'] for r in records.values()} |
                         {a['basis_file'] for a in auxiliary.values()}))
    for element, record in records.items():
        resolver.libraries.select(files, 'ORB', element, (record['basis'],), record['explicit_electrons'])
        aux = auxiliary[element]
        resolver.libraries.select(files, 'AUX_FIT', element, (aux['basis'],), record['explicit_electrons'])
    return auxiliary
