"""Explicit XC GPW/GAPW profiles and checked basis/potential selections.

Multiwfn organization informed the XC branches; see recorded provenance.
No build detection, automatic q changes or runtime validation.
"""
from pathlib import Path

from .data_catalog import BASIS_ROWS, POTENTIAL_ROWS, catalog_rows as _rows
from .errors import KitError
from .structure import ELEMENTS, ELEMENT_ORDER
from .hybrid import resolve_functional
from .basis_registry import basis_option, parse_basis
from .basis_resolution import BasisResolver, alternatives
from .functional_registry import (FUNCTIONAL_PROFILES, FUNCTIONALS, HYBRID_POTENTIAL_FAMILIES,
                                  FunctionalProfile, potential_tag)

LEGACY_BASES = ('SZV-MOLOPT-SR-GTH', 'DZVP-MOLOPT-SR-GTH', 'DZVP-MOLOPT-GTH',
                'TZVP-MOLOPT-GTH', 'TZV2P-MOLOPT-GTH')
# Import-compatible legacy inventory, NOT the numbered/complete selection registry.
BASES = (*LEGACY_BASES, 'TZVP-MOLOPT-SR-GTH', 'TZV2P-MOLOPT-SR-GTH', 'TZV2PX-MOLOPT-GTH')


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


def electron_model(settings, elements, pseudo_valences):
    """Select the explicitly requested model before spin/electron validation."""
    selected = dict(normalize_basis_overrides(settings.basis_overrides, elements))
    types = {basis_option(selected.get(el, settings.basis)).kind_type for el in elements}
    if len(types) != 1:
        raise KitError('Mixed all-electron/pseudopotential KINDs are not enabled; choose one electron model explicitly')
    all_electron = types == {'all-electron'}
    counts = {el: i for i, el in enumerate(ELEMENT_ORDER, 1)} if all_electron else pseudo_valences
    unsupported = set(elements)-counts.keys()
    if unsupported:
        raise KitError('No verified basis/potential preset for: '+', '.join(sorted(unsupported)))
    if all_electron:
        if settings.cp2k_version != '2026.2':
            raise KitError('All-electron GAPW profiles require target CP2K 2026.2')
        if settings.run_type == 'CELL_OPT' or settings.kpoints != (1, 1, 1):
            raise KitError('All-electron GAPW currently supports Gamma ENERGY/ENERGY_FORCE/GEO_OPT, not CELL_OPT/non-Gamma')
        if settings.dft_plus_u:
            raise KitError('All-electron GAPW DFT+U projector suitability is not enabled/validated')
        if settings.electron_density or settings.spin_density:
            raise KitError('GAPW density CUBE hard/soft contributions are not enabled; GPW valence-density semantics cannot be reused')
    return all_electron, counts


def resolve_method(settings, elements, valences, kind_specs=None):
    profile = resolve_functional(settings)
    all_electron, valences = electron_model(settings, elements, valences)
    if settings.dispersion not in profile.dispersion:
        raise KitError(f'No checked {settings.dispersion} combination for {settings.functional}; '
                       'required nonlocal correlation is intrinsic, not an extra pair correction')
    if profile.hybrid:
        if (all_electron or settings.kpoints != (1, 1, 1) or settings.run_type == 'CELL_OPT'
                or settings.dft_plus_u or settings.smearing is not None):
            raise KitError(f'{settings.functional} direct HFX currently supports GPW Gamma '
                           'ENERGY/ENERGY_FORCE/GEO_OPT without DFT+U or smearing; '
                           'GAPW, non-Gamma, CELL_OPT and +U require separate validation')
        selected = dict(normalize_basis_overrides(settings.basis_overrides, elements))
        if any(basis_option(selected.get(el, settings.basis)).protocol != 'classic' for el in elements):
            raise KitError('Initial direct HFX profiles require classic MOLOPT/UCL orbital bases; '
                           'UZH-PBE0, custom orbital bases and RI-HFX are not enabled; '
                           'ADMM uses the same classic ORB gate with separate AUX_FIT checks')
    if profile.restricted:
        if all_electron or settings.kpoints != (1, 1, 1) or settings.run_type == 'CELL_OPT' or settings.dft_plus_u:
            raise KitError(f'{settings.functional} currently supports GPW Gamma ENERGY/ENERGY_FORCE/GEO_OPT '
                           'without DFT+U; GAPW, non-Gamma, CELL_OPT and +U require separate validation. '
                           'This is a generator scope limit, not a universal CP2K limitation')
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
                    family = HYBRID_POTENTIAL_FAMILIES.get(potential_functional)
                    if family is not None:
                        if not resolver.potential_available(option, el, q, family, POTENTIAL_CATALOG):
                            raise KitError(f'No verified family GTH-{family}-q{q} preset for {el} with {settings.functional}; '
                                           'no cross-family or valence fallback is applied')
                        potential_functional = family
                    else:
                        if potential_functional in {'PBE', 'BLYP'}:
                            raise KitError(f'No verified GTH-{potential_functional}-q{q} preset for {el}')
                        if not settings.allow_pbe_potential:
                            raise KitError(f'No matched GTH-{potential_tag(potential_functional)}-q{q} preset for {el}; explicitly approve the GTH-PBE approximation with --allow-pbe-potential (menu 114), or change the functional')
                        if not resolver.potential_available(option, el, q, 'PBE', POTENTIAL_CATALOG):
                            raise KitError(f'No verified GTH-PBE-q{q} approximation for {el}')
                        potential_functional = 'PBE'
            records[el], extra_warnings = resolver.resolve(option, el, q, potential_functional)
            warnings.extend(extra_warnings)
        except KitError as exc:
            if exc.code != 2:
                raise
            candidates = ', '.join(alternatives(el, q, settings.functional, option.kind_type)) or 'none in pinned catalog'
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
        raise KitError(f'{settings.functional} requires a Libxc-enabled target CP2K build; explicitly assert '
                       '--libxc-available (menu 113). Build support is not detected by cp2kkit')
    approximate = [el for el, r in records.items() if r['potential_approximation']]
    if approximate:
        family = HYBRID_POTENTIAL_FAMILIES.get(settings.functional)
        if family is not None:
            warnings.append(f'Standard family GTH-{family} pseudopotential for {settings.functional}: '+', '.join(approximate)+
                            '. This is a semilocal-family potential, not an exact hybrid-functional potential; validate the target property.')
        else:
            warnings.append(f'User-approved GTH-PBE pseudopotential approximation for {settings.functional}: '+', '.join(approximate)+'. This is not a matched-functional potential; validate the target property.')
    if profile.libxc:
        definition = ('uses Libxc '+ ' + '.join(profile.components)) if profile.components else 'uses a native shortcut requiring Libxc internally (LDA_C_PW)'
        warnings.append(f'{settings.functional} {definition}. '
                        'Libxc build support is user-asserted, not probed or runtime-validated.')
    if profile.kinetic_energy_density:
        warnings.append('Meta-GGA uses kinetic-energy density. Independently converge XC/grid and SCF thresholds, '
                        'including low-density regions; the retained 400/55 Ry defaults are not convergence evidence.')
    if profile.nonlocal_type:
        warnings.append(f'{settings.functional} includes required {profile.nonlocal_type} nonlocal correlation; '
                        'dispersion=none means no additional pair correction, not removal of intrinsic correlation. '
                        'Kernel contents/grid convergence and runtime acceptance remain unverified.')
    if any(r['basis_kind_type'] == 'all-electron' for r in records.values()):
        warnings.append('All-electron GAPW/ALL: electron counts include core electrons. Atomic grids, '
                        'GAPW hard/soft tolerances and cutoff/basis convergence need independent checks; '
                        'the selected numerical profile is a starting setup, not claimed converged. No relativistic/ECP model is inferred.')
    if overrides:
        warnings.append('Explicit element-specific basis overrides are applied to every split KIND of that element; no missing-entry fallback or q change is performed.')
    return profile, overrides, records, warnings


def xc_lines(functional, profile=None):
    profile = profile or FUNCTIONAL_PROFILES[functional]
    if profile.hybrid and profile.exact_exchange_fraction is None:
        raise KitError('PBEH XC rendering requires an explicit resolved fraction')
    if profile.xc_parameters:
        return ['      &XC_FUNCTIONAL',
                *(line for component, parameters in profile.xc_parameters
                  for line in (f'        &{component}',
                               *(f'          {key} {value}' for key, value in parameters),
                               f'        &END {component}')),
                '      &END XC_FUNCTIONAL']
    if profile.parametrization:
        return ['      &XC_FUNCTIONAL', '        &PBE',
                f'          PARAMETRIZATION {profile.parametrization}',
                '        &END PBE', '      &END XC_FUNCTIONAL']
    if profile.components:
        return ['      &XC_FUNCTIONAL',
                *(line for component in profile.components
                  for line in (f'        &{component}', f'        &END {component}')),
                '      &END XC_FUNCTIONAL']
    return [f'      &XC_FUNCTIONAL {profile.native or functional}', '      &END XC_FUNCTIONAL']
