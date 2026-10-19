"""Scrolling basis-value editor; fixed public numbers, no category submenu."""
from .basis_registry import OPTIONS, RESERVED_RANGES, basis_option, numbered_basis, parse_basis
from .cp2k_data import cp2k_path, read_library, safe_token
from .errors import KitError


def edit_basis(menu, current, values=None):
    query = ''
    try:
        current_label = basis_option(current, require_selectable=False).id
    except KitError:
        current_label = str(current)+' (invalid retained value; explicit correction/migration required)'
    while True:
        menu.show('Orbital basis registry v1 (immutable numbers; 0/back returns)')
        menu.show('Migration: legacy list positions are NOT registry v1 numbers; saved legacy names remain supported.')
        group = None
        for option in OPTIONS:
            if query and query.lower() not in (option.id+' '+option.name+' '+option.group).lower():
                continue
            if group != option.group:
                group = option.group
                menu.show(f'--- {group} ---')
            status = '' if option.selectable else f' [UNAVAILABLE: {option.restriction}]'
            menu.show(f'  {option.number}. {option.name} [{option.id}]{status}')
            if option.selectable and option.protocol != 'custom':
                menu.show('     Sources: '+', '.join(option.sources)+'; '+option.restriction)
        menu.show('Reserved, not selectable: '+', '.join(f'{a}-{b}' for a,b in RESERVED_RANGES)+'.')
        menu.show('All-electron 50-59 explicitly selects GAPW + ALL, not GPW/GTH. Availability requires per-KIND data checks.')
        menu.show('Enter keeps; /text filters (/ clears), numbers never change; d data directory; b/v explicit basis/potential file.')
        raw = menu.ask(f'Current [{current_label}]: ')
        if not raw or raw.lower() in {'0', 'back'}:
            return current
        if raw.startswith('/'):
            query = raw[1:]
            continue
        try:
            if raw.lower() in {'d', 'b', 'v'}:
                if values is None:
                    raise ValueError('Data-source editing needs a generation draft; use CLI file options')
                key = {'d': 'data_dir', 'b': 'basis_files', 'v': 'potential_files'}[raw.lower()]
                path = menu.ask(f'{key}: literal path; auto clears this override; Enter/back keeps: ')
                if path and path.lower() != 'back':
                    if path.lower() == 'auto':
                        values[key] = None if key == 'data_dir' else ()
                    else:
                        cp2k_path(path)
                        values[key] = path if key == 'data_dir' else (path,)
                continue
            result = numbered_basis(int(raw)) if raw.isdigit() else parse_basis(raw)
            if result == 'custom-orbital':
                if values is None:
                    raise ValueError('Custom 900 needs a generation draft or explicit CLI file/name options')
                draft = {}
                for key, prompt in (('custom_basis_file', 'Custom ORB file'),
                                    ('custom_basis_name', 'Real ORB name/alias'),
                                    ('custom_potential_file', 'Potential file (auto: matched default)'),
                                    ('custom_potential_name', 'Real potential name/alias')):
                    if key == 'custom_potential_name' and draft['custom_potential_file'] is None:
                        draft[key] = None
                        continue
                    value = menu.ask(f'{prompt} [{values.get(key) or "unset"}]; Enter keeps; 0/back returns: ')
                    if value.lower() in {'0', 'back'}:
                        return current
                    value = value or values.get(key)
                    if key == 'custom_potential_file' and value in (None, 'auto'):
                        value = None
                    elif not value:
                        raise ValueError(f'{key} is required')
                    elif key.endswith('_name'):
                        safe_token(value)
                    else:
                        cp2k_path(value)
                    draft[key] = value
                for prefix, role in (('custom_basis', 'ORB'), ('custom_potential', 'POTENTIAL')):
                    if draft[prefix+'_file']:
                        entries, _ = read_library(draft[prefix+'_file'], role)
                        if not any(draft[prefix+'_name'] in entry.names for entry in entries):
                            raise ValueError(f'{draft[prefix+"_file"]} has no real alias {draft[prefix+"_name"]}')
                values.update(draft)  # Transactional: abandoned custom edits leave all old fields intact.
            return result
        except (KitError, ValueError) as exc:
            menu.show(f'Invalid basis selection: {exc}')
