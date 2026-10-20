"""Scrolling category/direct-access editor; all routes share semantic state."""
import sys
from dataclasses import asdict
from pathlib import Path

from .errors import KitError
from .input_tui import (Cancelled, SessionExit, Menu, GROUPS, field_display,
                        parse_value, visible_fields)
from .inputgen import InputSettings, generate_input, write_input
from .menu_registry import ENTRIES, BY_TOKEN, CATEGORY_NAMES, MENU_LAYOUT_VERSION
from .presentation import require_terminal
from .structure import read_structure

FIELDS = {field.name: field for _, fields in GROUPS for field in fields}
FIELD_IDS = tuple((entry.number, entry.field) for entry in ENTRIES if entry.field)
NUMBERED_FIELDS = tuple((number, FIELDS[name]) for number, name in FIELD_IDS)
LABELS = {entry.field: entry.label for entry in ENTRIES if entry.field}


def settings_from(values):
    return InputSettings(**{name: values[name] for name in InputSettings.__dataclass_fields__})


def compatibility(menu, values):
    """Recheck changes without repairing physics or preventing further edits."""
    try:
        if not values['path']:
            raise KitError('Structure path is required; use s to load a structure')
        generate_input(read_structure(values['path'], values['frame']), settings_from(values))
    except (KitError, OSError) as exc:
        menu.show(f'Warning: draft needs attention: {exc}. Values retained; no automatic changes.')


def applicable_entries(values):
    visible = {f.name for f in visible_fields(tuple(FIELDS.values()), values)}
    return tuple(e for e in ENTRIES if e.field is None or e.field in visible)


def _show_entry(menu, entry, number, values):
    if entry.field is None:
        menu.show(f' {number:3}. {entry.label}')
        return
    field = FIELDS[entry.field]
    origin = 'user edit' if field.name in values['_edited'] else values['_origins'].get(field.name, 'source/output control')
    value = field_display(field, values)
    if entry.editor in {'custom_basis', 'custom_potential'}:
        value += '; alias='+str(values[entry.editor+'_name'])
    menu.show(f' {number:3}. {entry.label}: {value} [{origin}]')


def show_settings(menu, values, category=None):
    entries = applicable_entries(values)
    categories = {e.category for e in entries if e.category is not None}
    if category is None:
        menu.heading('\n=== CP2K input generation: common settings ===')
        menu.show(f"Structure: {values['path'] or 'No structure loaded'}; frame: {values['frame']}")
        menu.show('s: Load/change structure (201); f: Change XYZ frame (202)')
        menu.show(' -10. Back / cancel generation\n   0. Generate input files directly')
        common = sorted(((e.aliases[0] if e.aliases else e.number, e) for e in entries
                         if e.number == -1 or e.aliases), key=lambda pair: pair[0])
        for number, entry in common:
            _show_entry(menu, entry, number, values)
        menu.heading('Categories (open to browse; full IDs also work directly)')
        for number, label in CATEGORY_NAMES.items():
            if number in categories:
                menu.show(f' {number}. {label}')
        menu.show('  r. Review effective settings\n  p. Preview all inputs and replay command\n'
                  '  w. Review & write files (with confirmation)')
    else:
        menu.heading(f'\n=== {category}. {CATEGORY_NAMES[category]} ===')
        for entry in entries:
            if entry.category == category:
                _show_entry(menu, entry, entry.number, values)
        menu.show('   0. Back to input-generator main menu (no files written)\n'
                  '  r/p. Review / full preview; full IDs can access other categories')
    return entries, categories


def review(menu, values, full=False):
    try:
        if not values['path']:
            raise KitError('Structure path is required; use s to load a structure')
        return menu.review(values, full=full)
    except (KitError, OSError) as exc:
        menu.show(f'Error: Validation failed (no files written): {exc}. Fix the draft before writing files.')
        return None


def automatic_output(values):
    if not values.get('path'):
        return None
    suffix = '-CDD.inp' if values['density_difference'] else '.inp'
    return Path(values['path']).stem + suffix


def edit_source(menu, values, name):
    """Source edits are validated before replacing the loaded geometry selection."""
    new = menu.edit(FIELDS[name], values[name])
    if new == values[name]:
        return
    path = new if name == 'path' else values['path']
    frame = new if name == 'frame' else values['frame']
    try:
        if not path:
            raise KitError('Load a structure with s before selecting its frame')
        read_structure(path, frame)
    except (KitError, OSError) as exc:
        menu.show(f'Error: Cannot load structure/frame: {exc}. Previous source retained.')
        return
    values[name] = new
    if name == 'path' and values['_auto_output']:
        values['output'] = automatic_output(values)
    if values['fixed_atoms'] != 'off':
        menu.show('Warning: Fixed-atom indices were retained, not remapped to the changed structure/frame. '
                  'Review selection 420 / shortcut 9 against the loaded/expanded atom order before generation.')
    if values['fragment_a_indices'] != 'off':
        menu.show('Warning: Fragment atom indices were retained, not remapped to the changed structure/frame. '
                  'Review 602 against the loaded/expanded atom order; fragment charges/spins were not inferred.')


def atom_table(menu, values, magnetic=False, coordinates=True):
    try:
        if not values['path']:
            raise KitError('Load a structure first')
        structure = read_structure(values['path'], values['frame'])
        units = ' [angstrom]' if coordinates else ''
        menu.show(f'Atom indices below refer to loaded/expanded geometry, not CIF site labels{units}:')
        for index, (element, position) in enumerate(zip(structure.symbols, structure.positions), 1):
            label = f'@{index}' if magnetic else str(index)
            suffix = ' ' + ' '.join(f'{x:.8f}' for x in position) if coordinates else ''
            menu.show(f'  {label}: {element}{suffix}')
    except (KitError, OSError) as exc:
        menu.show(f'Warning: Atom list unavailable: {exc}')


def edit_pair(menu, values, prefix):
    """Keep file/alias controls transactional; back never leaves half an edit."""
    draft = {}
    for suffix in ('_file', '_name'):
        name = prefix+suffix
        while True:
            raw = menu.ask(f'{FIELDS[name].label} [{values[name]}]; Enter keeps; auto clears pair; back returns: ')
            if raw.lower() == 'back':
                return
            if raw.lower() == 'auto':
                values.update({prefix+'_file': None, prefix+'_name': None})
                return
            try:
                draft[name] = parse_value(FIELDS[name], raw) if raw else values[name]
                break
            except ValueError as exc:
                menu.show(f'Invalid input: {exc}')
    values.update(draft)


def show_partition(menu, values):
    from .density_workflow import partition
    try:
        if not values['path']:
            raise KitError('Load a structure first')
        structure = read_structure(values['path'], values['frame'])
        _, a, b = partition(values['fragment_a_indices'], len(structure.symbols))
        menu.show(f'Fragment A whole indices: {list(a)}; B complement: {list(b)}')
        for label, indices in (('A', a), ('B', b)):
            for local, index in enumerate(indices, 1):
                menu.show(f'  whole {index} ({structure.symbols[index-1]}) -> {label}:{local}')
    except (KitError, OSError) as exc:
        menu.show(f'Error: Cannot resolve partition: {exc}; selection retained.')


def edit_difference_states(menu, values):
    """Edit all three charge/multiplicity pairs as one transaction."""
    names = ('charge', 'multiplicity', 'fragment_a_charge', 'fragment_a_multiplicity',
             'fragment_b_charge', 'fragment_b_multiplicity')
    while True:
        current = ' '.join(str(values[name]) for name in names)
        raw = menu.ask('Charges/multiplicities: all_Q all_M A_Q A_M B_Q B_M '
                       f'[{current}]; e.g. 0 1 0 1 0 1; Enter keeps; back returns: ')
        if not raw or raw.lower() == 'back':
            return
        try:
            tokens = raw.split()
            if len(tokens) != 6:
                raise ValueError('Enter exactly six integers: all_Q all_M A_Q A_M B_Q B_M')
            # int() deliberately rejects auto/None/floats for explicit states.
            draft = {name: parse_value(FIELDS[name], str(int(token)))
                     for name, token in zip(names, tokens)}
            if draft['charge'] != draft['fragment_a_charge'] + draft['fragment_b_charge']:
                raise ValueError('Whole-system charge must equal A charge + B charge')
        except ValueError as exc:
            menu.show(f'Invalid input: {exc}. All six values unchanged.')
            continue
        values.update(draft)
        return


def edit_cube_output(menu, values):
    """Multiwfn-style cube selector limited to implemented output types."""
    while True:
        menu.heading('\n--- Cube output ---')
        menu.show('0. None\n1. Electron density (also spin density for unrestricted calculations)')
        menu.show('Only implemented output types are listed. CDD (602) requires electron density.')
        raw = menu.ask('Cube output [0/1]; Enter keeps; back returns: ').lower()
        if not raw or raw == 'back':
            return
        if raw not in {'0', '1'}:
            menu.show('Invalid input: select 0 or 1. Settings unchanged.')
            continue
        if raw == '0' and values['density_difference']:
            menu.show('Cannot disable electron density while CDD (602) is enabled; disable CDD first.')
            continue
        values['electron_density'] = raw == '1'
        if raw == '0':
            values['spin_density'] = False
        return


def edit_difference(menu, values):
    """Explicitly local 602 options; no generation or global-number interception."""
    while True:
        menu.heading('\n--- 602. Charge-density difference inputs (local options) ---')
        menu.show(f"1. Enable/disable: {values['density_difference']}\n"
                  f"2. Fragment A whole-system indices: {values['fragment_a_indices']}\n"
                  '3. Review fragment B complement and atom mapping\n'
                  f"4. Charges/spin multiplicities (all A B): all={values['charge']}/{values['multiplicity']}; "
                  f"A={values['fragment_a_charge']}/{values['fragment_a_multiplicity']}; "
                  f"B={values['fragment_b_charge']}/{values['fragment_b_multiplicity']}\n"
                  '5. Review mapping and common settings\n0. Back (no files written)' )
        menu.show('ENERGY/GPW only; density output is enabled for all three inputs. '
                  'B is the complement; charges/spins require explicit values; no independent recentering or ghosts.')
        raw = menu.ask('602 local option [0-5]; back returns; cancel cancels; q exits: ').lower()
        if raw in {'0', 'back'}:
            return
        if raw == '1':
            values['density_difference'] = not values['density_difference']
            if values.get('_auto_output'):
                values['output'] = automatic_output(values)
            if values['density_difference']:
                values['electron_density'] = True
                menu.show('Electron density cube output automatically enabled for whole/A/B.')
        elif raw == '2':
            values['fragment_a_indices'] = menu.edit(FIELDS['fragment_a_indices'], values['fragment_a_indices'], values)
        elif raw == '3':
            show_partition(menu, values)
        elif raw == '4':
            edit_difference_states(menu, values)
        elif raw == '5':
            show_partition(menu, values)
            if values['density_difference']:
                review(menu, values)
            else:
                menu.show('Workflow is disabled; enable it to review validated common geometry/grid and all component states.')
        else:
            menu.show('Error: Invalid local option; global function IDs are not active inside 602.')


def edit_entry(menu, values, entry):
    if entry.editor == 'source':
        edit_source(menu, values, entry.field)
    elif entry.editor in {'custom_basis', 'custom_potential'}:
        edit_pair(menu, values, entry.editor)
    elif entry.editor == 'difference':
        edit_difference(menu, values)
    elif entry.editor == 'cube':
        edit_cube_output(menu, values)
    else:
        field = FIELDS[entry.field]
        if field.name in {'magnetism', 'fixed_atoms'}:
            atom_table(menu, values, magnetic=field.name == 'magnetism')
            if field.name == 'magnetism':
                menu.show('An explicit magnetic request enables UKS. Charge/multiplicity stay unchanged. '
                          'Element seeds apply first; @atom seeds override them. This is an initial guess, not a moment constraint.')
            else:
                menu.show('Fix fractional XYZ components; CELL_OPT can still move atoms with the cell. '
                          'Source constraints are not inherited. Enter keeps; off or 0 clears the selection.')
        old = values[field.name]
        values[field.name] = menu.edit(field, old, values)
        if field.name == 'output' and values[field.name] != old:
            values['_auto_output'] = False


def run_editor(path, frame, output, settings, stdin=None, stdout=None, plain=False,
               parent_session=False):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    require_terminal(stdin, stdout, 'Interactive generation')
    menu = Menu(stdin, stdout, plain)
    defaults = asdict(InputSettings())
    origins = {name: 'generator default' if value == defaults[name] else 'CLI seed'
               for name, value in asdict(settings).items()}
    values = {**asdict(settings), 'path': path, 'frame': frame,
              'output': output or (Path(path).stem+'.inp' if path else None),
              '_edited': set(), '_origins': origins, '_auto_output': output is None}
    if values['_auto_output']:
        values['output'] = automatic_output(values)
    if values['density_difference']:
        values['electron_density'] = True
    category = None
    try:
        menu.show('No calculations. Source supplies geometry, not charge/spin/method; source/data/results stay protected.')
        menu.show(f'Menu layout v{MENU_LAYOUT_VERSION}: common shortcuts plus categories; full IDs work directly. '
                  '0.2.8 extension numbers have migrated; see the numbering guide. '
                  'Basis registry numbers are unchanged. Inapplicable fields are hidden, not reset.')
        menu.show('Parameter Enter keeps; back abandons an edit; literal 0 is a value (basis chooser: 0 returns). '
                  'Main-menu 0 writes input files directly; w reviews and confirms first. '
                  'Category/602 0 returns; -10/back returns; q exits.')
        while True:
            applicable, categories = show_settings(menu, values, category)
            raw = menu.ask('Select shortcut/category/full ID, s/f, r/p/w; -10/back returns: ').lower()
            if raw in {'-10', 'back'} or raw == '0' and category is not None:
                if category is not None:
                    category = None
                    continue
                raise Cancelled
            if raw in {str(n) for n in CATEGORY_NAMES}:
                number = int(raw)
                if number in categories:
                    category = number
                else:
                    menu.show('Error: Category has no applicable implemented entries; draft retained.')
                continue
            direct_generate = raw == '0' and category is None
            entry = BY_TOKEN.get({'s': '201', 'f': '202'}.get(raw, raw))
            if entry is not None:
                if entry not in applicable:
                    menu.show(f'Error: Invalid menu number for this state: {entry.number} ({entry.label}) is not applicable. '
                              'Check task, SCF, method and periodicity. Values retained; no automatic changes.')
                    continue
                if entry.editor == 'review':
                    review(menu, values)
                    menu.ask('Enter to return to the originating menu; q exits: ')
                    continue
                before = {name: values[name] for name in (*InputSettings.__dataclass_fields__, 'path', 'frame', 'output')}
                edit_entry(menu, values, entry)
                changed = {name for name, value in before.items() if values[name] != value}
                if changed:
                    values['_edited'].update(changed)
                    compatibility(menu, values)
                continue
            if raw in {'r', 'p', 'w', '0'}:
                if category is not None and raw == 'w':
                    menu.show('Return to the main menu before generation; category 0/back never writes files.')
                    continue
                validated = review(menu, values, full=raw == 'p') if not direct_generate else True
                if validated is None:
                    continue
                if raw in {'r', 'p'}:
                    menu.ask('Enter to return to the originating menu; q exits: ')
                    continue
                policy = 'new whole/A/B inputs and atom map (all targets exclusive)' if values['density_difference'] else 'input (existing .inp may be replaced)'
                answer = 'yes' if direct_generate else menu.ask('Write '+policy+(' and new JSON' if values['write_json'] else '')+'? [y/N]; back returns; cancel cancels; q exits: ').lower()
                if answer not in {'y', 'yes'}:
                    menu.show('Not confirmed; no files written. Returning to common settings.')
                    continue
                try:
                    result = write_input(read_structure(values['path'], values['frame']), settings_from(values), values['output'])
                except (KitError, OSError) as exc:
                    menu.show(f'Error: {exc}. No unfinished output retained.')
                    new = menu.ask('New input path for retry; Enter/back returns to settings; cancel/q: ')
                    if new and new.lower() != 'back':
                        try:
                            values['output'] = parse_value(FIELDS['output'], new)
                            values['_auto_output'] = False
                        except ValueError as error:
                            menu.show(f'Error: {error}. Target unchanged.')
                    continue
                menu.show('Success: Input'+(' bundle' if values['density_difference'] else '')+
                          (' and provenance sidecar' if result[1] is not None else '')+' generated; no calculation was run.')
                from .density_workflow import bundle_paths
                for target in bundle_paths(settings_from(values), result[0]):
                    menu.show(f'Generated path: {target.resolve()}')
                menu.show(f"Task: {values['run_type']}; functional: {values['functional']}; "
                          f"basis: {values['basis']}; dispersion: {values['dispersion']}")
                for warning in result[2]:
                    menu.show(f'Warning: {warning}')
                return 0
            if not raw:
                menu.show('No files written. Select a field, r/p to inspect, main-menu 0 to write directly, or w to review & write.')
            else:
                menu.show('Error: Invalid menu number or action (unknown/unimplemented; no legacy extension aliases inferred)')
    except (Cancelled, KeyboardInterrupt):
        menu.show('Cancelled; no unfinished files generated. Completed files, if any, are retained.')
        return 0
    except SessionExit:
        if parent_session:
            raise
        menu.show('Exited the session; completed files, if any, are retained.')
        return 0
