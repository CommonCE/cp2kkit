"""Two-fragment GPW density input preparation, never calculation or subtraction.

Uses the shared generator and exclusive staged publication. All fragments retain
whole-system geometry/cell; no independent recentering, ghosts, or spin inference.
"""
import csv
import io
import os
from dataclasses import asdict, replace
from pathlib import Path

from .constraints import resolve_atom_indices
from .errors import KitError
from .io import json_text, staged_files
from .structure import Structure


def bundle_paths(settings, output):
    output = Path(output)
    if not settings.density_difference:
        return [output, *([Path(str(output)+'.json')] if settings.write_json else [])]
    if output.suffix.lower() != '.inp':
        raise KitError('Density-difference bundles require an .inp output path')
    paths = [output, output.with_name(output.stem+'-fragment-A.inp'),
             output.with_name(output.stem+'-fragment-B.inp'),
             output.with_name(output.stem+'-atom-map.csv')]
    if settings.write_json:
        paths.append(Path(str(output)+'.json'))
    return paths


def partition(selection, count):
    normalized, a = resolve_atom_indices(selection, count)
    chosen = set(a)
    b = tuple(i for i in range(1, count+1) if i not in chosen)
    if not a or not b:
        raise KitError('Fragment A and its complement B must both contain atoms')
    return normalized, a, b


def _fragment_settings(settings, symbols, indices, charge, multiplicity, project):
    elements = set(symbols)
    local = {whole: index for index, whole in enumerate(indices, 1)}
    magnetism = settings.magnetism
    if magnetism is not None:
        seeds = []
        for selector, moment in magnetism:
            if selector.startswith('@'):
                index = int(selector[1:])
                if index in local:
                    seeds.append((f'@{local[index]}', moment))
            elif selector in elements:
                seeds.append((selector, moment))
        magnetism = tuple(seeds)  # Keep explicit UKS, even without local seeds.
    return replace(settings, project=project, charge=charge, multiplicity=multiplicity,
                   basis_overrides=tuple((el, basis) for el, basis in settings.basis_overrides if el in elements),
                   dft_plus_u=tuple(entry for entry in settings.dft_plus_u if entry[0] in elements),
                   magnetism=magnetism, cell=None)


def generate_difference(structure, settings):
    from .inputgen import generate_input, InputSettings

    if type(settings.density_difference) is not bool or not settings.density_difference:
        raise KitError('density_difference must be enabled as Boolean true')
    if settings.run_type != 'ENERGY':
        raise KitError('Density-difference input generation requires ENERGY; task is not changed automatically')
    for name in ('fragment_a_charge', 'fragment_b_charge', 'fragment_a_multiplicity', 'fragment_b_multiplicity'):
        value = getattr(settings, name)
        if type(value) is not int or ('multiplicity' in name and value < 1):
            raise KitError(f'{name} must be explicitly specified as an integer'+(' >= 1' if 'multiplicity' in name else ''))
    if type(settings.charge) is not int or settings.fragment_a_charge+settings.fragment_b_charge != settings.charge:
        raise KitError('Charge-conserving partition required: total charge must equal fragment A + fragment B charges')
    selection, a, b = partition(settings.fragment_a_indices, len(structure.symbols))
    common = replace(settings, density_difference=False, electron_density=True)
    text, whole = generate_input(structure, common)
    if whole['electron_count_model'] != 'pseudopotential_valence':
        raise KitError('Density-difference inputs currently support GPW pseudopotential valence density only')
    # Freeze derived whole-system numerical defaults, but not raw workflow state.
    resolved = InputSettings.from_config(whole)
    geometry = whole['generated_structure']
    cell = [row.copy() for row in geometry['cell']]
    pbc = geometry['pbc'].copy()
    components = {'whole': whole}
    mapping = []
    for label, indices, charge, multiplicity in (
            ('A', a, settings.fragment_a_charge, settings.fragment_a_multiplicity),
            ('B', b, settings.fragment_b_charge, settings.fragment_b_multiplicity)):
        symbols = [structure.symbols[i-1] for i in indices]
        positions = [geometry['positions'][i-1].copy() for i in indices]
        source = {**structure.source, 'derived_fragment': label, 'whole_atom_indices': list(indices)}
        fragment = Structure(symbols, positions, [row.copy() for row in cell], pbc.copy(), source, structure.frame)
        fragment_settings = _fragment_settings(resolved, symbols, indices, charge, multiplicity,
                                               resolved.project+'-fragment-'+label)
        _, report = generate_input(fragment, fragment_settings, _common_ngrids=whole['method_profile']['ngrids'])
        for name, kind in report['kinds'].items():
            element = kind.get('element', name)
            candidates = [k for name, k in whole['kinds'].items() if k.get('element', name) == element]
            if not candidates:
                raise KitError(f'Cannot match fragment KIND for element {element}')
            for key in ('basis', 'potential', 'basis_file', 'potential_file', 'basis_source', 'potential_source', 'valence_electrons'):
                if kind[key] != candidates[0][key]:
                    raise KitError(f'Fragment {label} changes {element} {key}; provide consistent explicit data sources')
        if report['nonlocal_correlation'] != whole['nonlocal_correlation']:
            raise KitError(f'Fragment {label} changes nonlocal correlation/kernel identity; provide consistent data sources')
        if report['generated_structure']['cell'] != cell or report['generated_structure']['positions'] != positions:
            raise KitError('Fragment generation changed shared geometry/cell')
        components['fragment_'+label.lower()] = report
        for local, whole_index in enumerate(indices, 1):
            mapping.append({'whole_index': whole_index, 'element': structure.symbols[whole_index-1],
                            'fragment': label, 'fragment_index': local,
                            'position_angstrom': geometry['positions'][whole_index-1].copy()})
    if sum(components[key]['explicit_electron_count'] for key in ('fragment_a', 'fragment_b')) != whole['explicit_electron_count']:
        raise KitError('Fragment electron counts do not sum to the whole-system count')
    mapping.sort(key=lambda row: row['whole_index'])
    report = dict(whole)
    report['settings'] = asdict(replace(resolved, density_difference=True,
                                        electron_density=settings.electron_density, fragment_a_indices=selection))
    report['density_difference'] = {
        'enabled': True, 'expression': 'n_whole - n_fragment_A - n_fragment_B',
        'density_meaning': 'GPW pseudopotential electron-number density; not electric charge density',
        'fragment_a_indices': list(a), 'fragment_b_indices': list(b), 'atom_index_base': 1,
        'atom_mapping': mapping, 'components': components,
        'common_grid_policy': 'Whole-system cell, origin convention, cutoff, NGRIDS and stride; verify actual CUBE grids before subtraction',
        'ghost_basis': False, 'charge_conserving': True, 'runtime_validated': False,
        'magnetic_seed_policy': 'Element seeds retained for present elements; @whole indices explicitly mapped to fragment-local indices; explicit UKS retained',
        'cube_grid_match_verified': False,
    }
    report['warnings'] = list(dict.fromkeys(w for component in components.values() for w in component['warnings']))
    report['warnings'] += [
        'Density-difference inputs preserve whole-system geometry; no ghosts or separate fragment relaxation. Converge the chosen fragment-density convention.',
        'Element overrides/U/magnetic seeds follow included atoms; @whole magnetic seeds are explicitly mapped to fragment-local indices. Explicit UKS is retained.',
        'Identical requested cell/grid controls are not proof of matching CUBE grids; check actual outputs before subtraction.',
        'Density-difference bundle publication is exclusive: no existing input, mapping, JSON or result is replaced.',
    ]
    if settings.fragment_a_charge or settings.fragment_b_charge:
        report['warnings'].append('Charged fragments require review of electrostatic boundary/background treatment; no correction or charge repair is inferred.')
    return text, report


def write_difference(structure, settings, output):
    _, manifest = generate_difference(structure, settings)
    paths = bundle_paths(settings, output)
    components = manifest['density_difference']['components']
    data = [components[key]['input_text'] for key in ('whole', 'fragment_a', 'fragment_b')]
    mapping = io.StringIO(newline='')
    writer = csv.writer(mapping, lineterminator='\n')
    writer.writerow(['whole_index', 'element', 'fragment', 'fragment_index', 'x_angstrom', 'y_angstrom', 'z_angstrom'])
    for row in manifest['density_difference']['atom_mapping']:
        writer.writerow([row['whole_index'], row['element'], row['fragment'], row['fragment_index'],
                         *(f'{value:.8f}' for value in row['position_angstrom'])])
    data.append(mapping.getvalue())
    manifest['density_difference']['output_paths'] = [str(path.resolve()) for path in paths]
    if settings.write_json:
        data.append(json_text(manifest))
    for path in paths:
        for component in components.values():
            for source in (component['source_structure']['source'], *component['data_sources'].values()):
                if isinstance(source, dict) and source.get('path'):
                    original = Path(source['path'])
                    if path.resolve() == original.resolve() or path.exists() and original.exists() and path.samefile(original):
                        raise KitError(f'Refusing to replace a source/data file: {path}')
    with staged_files(paths) as streams:
        for stream, content in zip(streams, data):
            stream.write(content)
    warnings = list(manifest['warnings'])
    if not settings.write_json and os.path.lexists(str(output)+'.json'):
        warnings.append('Existing JSON sidecar was not updated or deleted; it may describe an earlier input.')
    return Path(output), paths[-1] if settings.write_json else None, warnings
