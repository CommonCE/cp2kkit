"""Explicit GPW profiles and header-checked basis/potential selections.

Multiwfn organization informed the XC branches; see recorded provenance.
No physical parameters, build detection, automatic q changes or runtime validation.
"""
from dataclasses import dataclass
from pathlib import Path

from .data_catalog import BASIS_ROWS, POTENTIAL_ROWS, catalog_rows as _rows
from .errors import KitError
from .structure import ELEMENTS
from .basis_registry import basis_option, parse_basis
from .basis_resolution import BasisResolver, alternatives

LEGACY_BASES = ('SZV-MOLOPT-SR-GTH', 'DZVP-MOLOPT-SR-GTH', 'DZVP-MOLOPT-GTH',
                'TZVP-MOLOPT-GTH', 'TZV2P-MOLOPT-GTH')
# Import-compatible legacy inventory, NOT the numbered/complete selection registry.
BASES = (*LEGACY_BASES, 'TZVP-MOLOPT-SR-GTH', 'TZV2P-MOLOPT-SR-GTH', 'TZV2PX-MOLOPT-GTH')


@dataclass(frozen=True)
class FunctionalProfile:
    parametrization: str | None = None
    libxc: bool = False
    dispersion: tuple[str, ...] = ('none', 'd3', 'd3bj')


FUNCTIONAL_PROFILES = {'PBE': FunctionalProfile(), 'BLYP': FunctionalProfile(),
                       'PBESOL': FunctionalProfile('PBESOL'),
                       'REVPBE': FunctionalProfile('REVPBE'),
                       'RPBE': FunctionalProfile(libxc=True)}
FUNCTIONALS = tuple(FUNCTIONAL_PROFILES)


BASIS_CATALOG = {file: {basis: _rows(rows) for basis, rows in families.items()}
                 for file, families in BASIS_ROWS.items()}
POTENTIAL_CATALOG = {functional: _rows(rows) for functional, rows in POTENTIAL_ROWS.items()}


def parse_basis_overrides(raw):
    """Element=basis; Element=basis. Explicit mixed bases, never implicit fallback."""
    if raw.strip().lower() in {'auto', 'none', 'off'}:
        return ()
    result, seen = [], set()
    for entry in raw.split(';'):
        parts = entry.strip().split('=')
        if len(parts) != 2:
            raise ValueError('Use Element=basis entries separated by semicolons, or off')
        element, basis = (p.strip() for p in parts)
        basis = parse_basis(basis)
        if element in seen:
            raise ValueError('Basis overrides require unique elements and supported basis names')
        # Actual structure presence is checked when resolving the draft.
        if element not in ELEMENTS:
            raise ValueError('Basis selector must be an element symbol')
        seen.add(element)
        result.append((element, basis))
    return tuple(sorted(result))


def format_basis_overrides(value):
    return '; '.join(f'{el}={basis}' for el, basis in value) or 'off'


def normalize_basis_overrides(value, elements):
    try:
        if not isinstance(value, (tuple, list)) or any(
                not isinstance(entry, (tuple, list)) or len(entry) != 2
                or any(not isinstance(v, str) for v in entry) for entry in value):
            raise ValueError('basis_overrides must contain (element, basis) pairs')
        for element, basis in value:
            if element not in ELEMENTS:
                raise ValueError('Each API pair must contain one valid element and one supported basis ID/name')
            parse_basis(basis)
        parsed = parse_basis_overrides(format_basis_overrides(value))
        for el, _ in parsed:
            if el not in elements:
                raise ValueError(f'Basis override element {el} is absent from the structure')
        return parsed
    except (ValueError, TypeError) as exc:
        raise KitError(f'Invalid basis overrides: {exc}') from exc


def resolve_method(settings, elements, valences, kind_specs=None):
    profile = FUNCTIONAL_PROFILES[settings.functional]
    if type(settings.allow_pbe_potential) is not bool or type(settings.libxc_available) is not bool:
        raise KitError('Potential approval and Libxc availability assertions must be Boolean')
    overrides = normalize_basis_overrides(settings.basis_overrides, elements)
    selected = dict(overrides)
    records, warnings, missing = {}, [], []
    resolver = BasisResolver(settings)
    for el in elements:
        option = basis_option(selected.get(el, settings.basis))
        q = valences[el]
        potential_functional = settings.functional
        try:
            if option.protocol == 'classic' or option.protocol == 'custom' and not settings.custom_potential_file:
                if not resolver.potential_available(option, el, q, potential_functional, POTENTIAL_CATALOG):
                    if potential_functional in {'PBE', 'BLYP'}:
                        raise KitError(f'No verified GTH-{potential_functional}-q{q} preset for {el}')
                    if not settings.allow_pbe_potential:
                        raise KitError(f'No matched GTH-{potential_functional}-q{q} preset for {el}; explicitly approve the GTH-PBE approximation with --allow-pbe-potential (menu 129), or change the functional')
                    if not resolver.potential_available(option, el, q, 'PBE', POTENTIAL_CATALOG):
                        raise KitError(f'No verified GTH-PBE-q{q} approximation for {el}')
                    potential_functional = 'PBE'
            records[el], extra_warnings = resolver.resolve(option, el, q, potential_functional)
            warnings.extend(extra_warnings)
        except KitError as exc:
            if exc.code != 2:
                raise
            candidates = ', '.join(alternatives(el, q, settings.functional)) or 'none in pinned catalog'
            labels = ', '.join(label for label, (element, _) in (kind_specs or {}).items() if element == el) or el
            missing.append(f'KIND(s) {labels} / element {el} q{q}: {exc} Catalog alternatives (not substitutions; require checks): {candidates}')
    if missing:
        raise KitError('\n'.join(missing))
    resolver.check_emitted_aliases(records)
    extended = (settings.functional not in {'PBE', 'BLYP'} or basis_option(settings.basis).name not in LEGACY_BASES
                or bool(overrides) or any(Path(r['basis_file']).name != 'BASIS_MOLOPT' for r in records.values()))
    if extended and settings.cp2k_version != '2026.2':
        raise KitError('New functional/basis profiles and explicit basis overrides are checked only for CP2K 2026.2')
    if profile.libxc and not settings.libxc_available:
        raise KitError('RPBE requires a Libxc-enabled target CP2K build; explicitly assert --libxc-available (menu 130). Build support is not detected by cp2kkit')
    if settings.dispersion not in profile.dispersion:
        raise KitError(f'No checked {settings.dispersion} combination for {settings.functional}')
    approximate = [el for el, r in records.items() if r['potential_approximation']]
    if approximate:
        warnings.append(f'User-approved GTH-PBE pseudopotential approximation for {settings.functional}: '+', '.join(approximate)+'. This is not a matched-functional potential; validate the target property.')
    if profile.libxc:
        warnings.append('RPBE uses Libxc GGA_X_RPBE + GGA_C_PBE. Libxc build support is user-asserted, not probed or runtime-validated.')
    if overrides:
        warnings.append('Explicit element-specific basis overrides are applied to every split KIND of that element; no missing-entry fallback or q change is performed.')
    return profile, overrides, records, warnings


def xc_lines(functional):
    profile = FUNCTIONAL_PROFILES[functional]
    if profile.parametrization:
        return ['      &XC_FUNCTIONAL', '        &PBE',
                f'          PARAMETRIZATION {profile.parametrization}',
                '        &END PBE', '      &END XC_FUNCTIONAL']
    if profile.libxc:
        return ['      &XC_FUNCTIONAL', '        &GGA_X_RPBE', '        &END GGA_X_RPBE',
                '        &GGA_C_PBE', '        &END GGA_C_PBE', '      &END XC_FUNCTIONAL']
    return [f'      &XC_FUNCTIONAL {functional}', '      &END XC_FUNCTIONAL']
