"""Immutable public basis numbers, independent of display order and library aliases.

Allocated numbers are never recycled, including unavailable/retired entries.
Names from pre-registry settings are accepted at the boundary, not stored as IDs.
"""
from dataclasses import dataclass
from enum import Enum
import re
from types import MappingProxyType

from .errors import KitError


class BasisRole(str, Enum):
    ORB = 'ORB'
    AUX_FIT = 'AUX_FIT'
    RI_AUX = 'RI_AUX'


@dataclass(frozen=True)
class BasisOption:
    id: str
    number: int
    name: str
    group: str
    family: str
    sources: tuple[str, ...]
    potential_sources: tuple[str, ...] = ('GTH_POTENTIALS',)
    aliases: tuple[str, ...] = ()
    kind_type: str = 'pseudopotential'
    role: BasisRole = BasisRole.ORB
    functionals: tuple[str, ...] = ('PBE', 'BLYP', 'PBESOL', 'REVPBE', 'RPBE')
    protocol: str = 'classic'
    status: str = 'enabled'
    restriction: str = 'Element/electron-model coverage must be checked; no substitution.'

    @property
    def selectable(self):
        return self.status == 'enabled' and self.role == BasisRole.ORB


CLASSIC = 'Classic MOLOPT / UCL extensions'
UZH_PBE = 'UZH-PBE (paired potential protocol)'
UZH_PBE0 = 'UZH-PBE0 (not selectable: no hybrid template)'
ALL_ELECTRON = 'All-electron orbital bases (GAPW + ALL; audited light elements)'
CUSTOM = 'Custom orbital basis'
M = ('BASIS_MOLOPT', 'BASIS_MOLOPT_UCL')
U = ('BASIS_MOLOPT_UZH_2026.2', 'BASIS_MOLOPT_UZH')
UP = ('POTENTIAL_UZH_2026.2', 'POTENTIAL_UZH')
# Explicit numbers and IDs, never enumerate() or a filtered-list position.
OPTIONS = (
    BasisOption('molopt-sr-szv', 1, 'SZV-MOLOPT-SR-GTH', CLASSIC, 'SZV-MOLOPT-SR-GTH', M),
    BasisOption('molopt-sr-dzvp', 2, 'DZVP-MOLOPT-SR-GTH', CLASSIC, 'DZVP-MOLOPT-SR-GTH', M),
    BasisOption('molopt-tzvp', 3, 'TZVP-MOLOPT-GTH', CLASSIC, 'TZVP-MOLOPT-GTH', M),
    BasisOption('molopt-tzv2p', 4, 'TZV2P-MOLOPT-GTH', CLASSIC, 'TZV2P-MOLOPT-GTH', M),
    BasisOption('molopt-tzv2px', 5, 'TZV2PX-MOLOPT-GTH', CLASSIC, 'TZV2PX-MOLOPT-GTH', M),
    BasisOption('molopt-szv', 6, 'SZV-MOLOPT-GTH', CLASSIC, 'SZV-MOLOPT-GTH', M),
    BasisOption('molopt-dzvp', 7, 'DZVP-MOLOPT-GTH', CLASSIC, 'DZVP-MOLOPT-GTH', M),
    BasisOption('molopt-sr-tzvp', 8, 'TZVP-MOLOPT-SR-GTH', CLASSIC, 'TZVP-MOLOPT-SR-GTH', ('BASIS_MOLOPT_UCL',),
                restriction='UCL SR extension: fixed-q coverage excludes H/C/N/O.'),
    BasisOption('molopt-sr-tzv2p', 9, 'TZV2P-MOLOPT-SR-GTH', CLASSIC, 'TZV2P-MOLOPT-SR-GTH', ('BASIS_MOLOPT_UCL',),
                restriction='UCL SR extension: fixed-q coverage excludes H/C/N/O.'),
    BasisOption('uzh-pbe-dzvp', 20, 'DZVP-MOLOPT-PBE-GTH', UZH_PBE, 'DZVP-MOLOPT-PBE-GTH', U, UP,
                ('DZVP-MOLOPT-GGA-GTH',), functionals=('PBE',), protocol='uzh-pbe',
                restriction='PBE only; paired UZH potential; 71 current fixed-q preset elements, not arbitrary q.'),
    BasisOption('uzh-pbe-tzvp', 21, 'TZVP-MOLOPT-PBE-GTH', UZH_PBE, 'TZVP-MOLOPT-PBE-GTH', U, UP,
                ('TZVP-MOLOPT-GGA-GTH',), functionals=('PBE',), protocol='uzh-pbe'),
    BasisOption('uzh-pbe-tzv2p', 22, 'TZV2P-MOLOPT-PBE-GTH', UZH_PBE, 'TZV2P-MOLOPT-PBE-GTH', U, UP,
                ('TZV2P-MOLOPT-GGA-GTH',), functionals=('PBE',), protocol='uzh-pbe'),
    BasisOption('uzh-pbe0-dzvp', 30, 'DZVP-MOLOPT-PBE0-GTH', UZH_PBE0, 'DZVP-MOLOPT-PBE0-GTH', U, UP,
                ('DZVP-MOLOPT-HYB-GTH',), functionals=('PBE0',), protocol='uzh-pbe0', status='unavailable',
                restriction='Data names exist in v2026.2; hybrid/HF/ADMM templates are not implemented.'),
    BasisOption('uzh-pbe0-tzvp', 31, 'TZVP-MOLOPT-PBE0-GTH', UZH_PBE0, 'TZVP-MOLOPT-PBE0-GTH', U, UP,
                ('TZVP-MOLOPT-HYB-GTH',), functionals=('PBE0',), protocol='uzh-pbe0', status='unavailable',
                restriction='Data names exist in v2026.2; hybrid/HF/ADMM templates are not implemented.'),
    BasisOption('uzh-pbe0-tzv2p', 32, 'TZV2P-MOLOPT-PBE0-GTH', UZH_PBE0, 'TZV2P-MOLOPT-PBE0-GTH', U, UP,
                ('TZV2P-MOLOPT-HYB-GTH',), functionals=('PBE0',), protocol='uzh-pbe0', status='unavailable',
                restriction='Data names exist in v2026.2; hybrid/HF/ADMM templates are not implemented.'),
    BasisOption('ae-6-31g-star', 50, '6-31G*', ALL_ELECTRON, '6-31G*', ('EMSL_BASIS_SETS',),
                ('POTENTIAL',), ('6-31Gx',), kind_type='all-electron', protocol='all-electron',
                restriction='GAPW + ALL; audited element coverage only, no ECP substitution.'),
    BasisOption('ae-6-311g-starstar', 51, '6-311G**', ALL_ELECTRON, '6-311G**', ('EMSL_BASIS_SETS',),
                ('POTENTIAL',), ('6-311Gxx',), kind_type='all-electron', protocol='all-electron'),
    BasisOption('ae-def2-tzvp', 52, 'Ahlrichs-def2-TZVP', ALL_ELECTRON, 'Ahlrichs-def2-TZVP', ('EMSL_BASIS_SETS',),
                ('POTENTIAL',), ('def2-TZVP',), kind_type='all-electron', protocol='all-electron'),
    BasisOption('ae-def2-qzvp', 53, 'Ahlrichs-def2-QZVP', ALL_ELECTRON, 'Ahlrichs-def2-QZVP', ('EMSL_BASIS_SETS',),
                ('POTENTIAL',), ('def2-QZVP',), kind_type='all-electron', protocol='all-electron'),
    BasisOption('ae-pob-tzvp', 54, 'pob-TZVP', ALL_ELECTRON, 'pob-TZVP', ('BASIS_pob',),
                ('POTENTIAL',), kind_type='all-electron', protocol='all-electron'),
    BasisOption('ae-pob-dzvp-rev2', 55, 'pob-DZVP-rev2', ALL_ELECTRON, 'pob-DZVP-rev2', ('BASIS_pob',),
                ('POTENTIAL',), kind_type='all-electron', protocol='all-electron'),
    BasisOption('ae-pob-tzvp-rev2', 56, 'pob-TZVP-rev2', ALL_ELECTRON, 'pob-TZVP-rev2', ('BASIS_pob',),
                ('POTENTIAL',), kind_type='all-electron', protocol='all-electron'),
    BasisOption('ae-uzh-svp', 57, 'SVP-MOLOPT-PBE-ae', ALL_ELECTRON, 'SVP-MOLOPT-PBE-ae', U,
                ('POTENTIAL',), ('SVP-MOLOPT-GGA-ae',), kind_type='all-electron', functionals=('PBE',), protocol='all-electron'),
    BasisOption('ae-uzh-tzvpp', 58, 'TZVPP-MOLOPT-PBE-ae', ALL_ELECTRON, 'TZVPP-MOLOPT-PBE-ae', U,
                ('POTENTIAL',), ('TZVPP-MOLOPT-GGA-ae',), kind_type='all-electron', functionals=('PBE',), protocol='all-electron'),
    BasisOption('ae-uzh-qzvpp', 59, 'QZVPP-MOLOPT-PBE-ae', ALL_ELECTRON, 'QZVPP-MOLOPT-PBE-ae', U,
                ('POTENTIAL',), ('QZVPP-MOLOPT-GGA-ae',), kind_type='all-electron', functionals=('PBE',), protocol='all-electron'),
    BasisOption('custom-orbital', 900, 'Custom orbital basis (file + real name)', CUSTOM, '', (),
                protocol='custom', restriction='Explicit pseudopotential ORB request; unknown q is unverified, not inferred.'),
)
RESERVED_RANGES = ((10, 19), (23, 29), (33, 39), (40, 49), (60, 79), (80, 99), (100, 199))


def validate_registry(options=OPTIONS):
    if any(not re.fullmatch(r'[a-z][a-z0-9-]+', o.id) or type(o.number) is not int
           or o.status not in {'enabled', 'reserved', 'unavailable', 'retired'} for o in options):
        raise ValueError('Invalid stable basis ID, integer number or registry status')
    if len({o.id for o in options}) != len(options) or len({o.number for o in options}) != len(options):
        raise ValueError('Duplicate immutable basis ID/number')
    if any(o.number <= 0 or any(a <= o.number <= b for a, b in RESERVED_RANGES) for o in options):
        raise ValueError('Allocated basis number overlaps return/reserved range')


validate_registry()
BY_ID = MappingProxyType({o.id: o for o in OPTIONS})
BY_NUMBER = MappingProxyType({o.number: o for o in OPTIONS})
DEFAULT_BASIS = 'molopt-sr-dzvp'


def basis_option(value, *, require_selectable=True):
    if not isinstance(value, str) or value.strip().isdigit():
        raise KitError('Numeric basis settings require explicit source-version migration; use a stable ID or name')
    value = value.strip()
    option = BY_ID.get(value.lower())
    if option is None:
        option = next((o for o in OPTIONS if value.upper() in tuple(n.upper() for n in (o.name, *o.aliases))), None)
    if option is None:
        raise KitError(f'Unsupported basis: {value}')
    if require_selectable and not option.selectable:
        raise KitError(f'Basis {option.number} ({option.id}) is {option.status}: {option.restriction}')
    return option


def parse_basis(value):
    """Argparse/field boundary: persist a semantic string ID, never a number."""
    try:
        return basis_option(value).id
    except KitError as exc:
        raise ValueError(str(exc)) from exc


def numbered_basis(number):
    option = BY_NUMBER.get(number)
    if option is None or not option.selectable:
        reason = option.restriction if option else 'Reserved or unallocated number'
        raise ValueError(f'Basis {number} is not selectable: {reason}')
    return option.id


# Historical UI positions only; old JSON already used names. No implicit migration.
LEGACY_NUMBERS = MappingProxyType({
    '0.2.4': ('molopt-sr-szv', 'molopt-sr-dzvp', 'molopt-dzvp', 'molopt-tzvp', 'molopt-tzv2p'),
    '0.2.5': ('molopt-sr-szv', 'molopt-sr-dzvp', 'molopt-dzvp', 'molopt-tzvp', 'molopt-tzv2p'),
    '0.2.6': ('molopt-sr-szv', 'molopt-sr-dzvp', 'molopt-dzvp', 'molopt-tzvp', 'molopt-tzv2p',
              'molopt-sr-tzvp', 'molopt-sr-tzv2p', 'molopt-tzv2px'),
})


def migrate_basis(value, source_version=None):
    if type(value) is int or isinstance(value, str) and value.isdigit():
        old = LEGACY_NUMBERS.get(source_version)
        if old is None or not 1 <= int(value) <= len(old):
            raise KitError('Numeric basis migration needs an explicit supported source_version (0.2.4/0.2.5/0.2.6)')
        return old[int(value)-1]
    return basis_option(value).id
