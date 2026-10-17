"""Single numbered generation menu with inspected Multiwfn main-menu IDs."""
import sys
from dataclasses import asdict
from pathlib import Path

from .errors import KitError
from .input_tui import Cancelled, SessionExit, Menu, GROUPS, field_display, visible_fields
from .inputgen import InputSettings, generate_input, write_input
from .presentation import require_terminal
from .structure import read_structure

FIELDS = {field.name: field for _, fields in GROUPS for field in fields}
# Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp, main menu at lines 200-365.
# Only corresponding implemented fields get upstream main-menu IDs. 100+ are
# explicit local extensions, not flattened/reassigned upstream submenu numbers.
FIELD_IDS = (
    (-7, 'periodic'), (-3, 'electron_density'), (-1, 'run_type'),
    (1, 'functional'), (2, 'basis'), (3, 'dispersion'), (4, 'scf'),
    (6, 'smearing'), (8, 'kpoints'), (10, 'optimizer'), (12, 'pressure'),
    (101, 'charge'), (102, 'multiplicity'), (105, 'cutoff'), (106, 'rel_cutoff'),
    (107, 'vacuum'), (112, 'added_mos'), (120, 'eps_scf'), (121, 'max_scf'),
    (122, 'max_outer_scf'), (123, 'max_iter'), (124, 'dft_plus_u'), (125, 'magnetism'),
    (126, 'spin_density'), (127, 'cube_stride'), (128, 'basis_overrides'),
    (129, 'allow_pbe_potential'), (130, 'libxc_available'),
)
NUMBERED_FIELDS = tuple((number, FIELDS[name]) for number, name in FIELD_IDS)
LABELS = {
    'periodic': 'Periodicity', 'electron_density': 'Electron density cube',
    'run_type': 'Run type', 'functional': 'Functional (GPW/GTH)', 'basis': 'Basis set',
    'dispersion': 'Dispersion', 'scf': 'SCF algorithm', 'smearing': 'Smearing [K]',
    'kpoints': 'k-points NX NY NZ', 'optimizer': 'Optimizer', 'pressure': 'CELL_OPT pressure [bar]',
    'charge': 'Total charge [e]', 'multiplicity': 'Spin multiplicity', 'cutoff': 'CUTOFF [Ry]',
    'rel_cutoff': 'REL_CUTOFF [Ry]', 'vacuum': 'Isolated box padding [angstrom]',
    'added_mos': 'ADDED_MOS', 'eps_scf': 'EPS_SCF', 'max_scf': 'Maximum inner/diag SCF steps',
    'max_outer_scf': 'Maximum outer SCF steps', 'max_iter': 'Maximum optimization steps',
    'dft_plus_u': 'DFT+U [eV]', 'magnetism': 'Magnetic initialization',
    'spin_density': 'Spin density', 'cube_stride': 'Cube stride NX NY NZ',
    'basis_overrides': 'Element basis overrides', 'allow_pbe_potential': 'Allow GTH-PBE approximation',
    'libxc_available': 'Target CP2K has Libxc (user assertion)',
}


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


def show_settings(menu, values):
    visible = set(visible_fields(tuple(field for _, field in NUMBERED_FIELDS), values))
    selectable = {number: field for number, field in NUMBERED_FIELDS if field in visible}
    if values['run_type'] not in {'GEO_OPT', 'CELL_OPT'}:
        selectable = {n: f for n, f in selectable.items() if f.name not in {'optimizer', 'max_iter'}}
    menu.heading('\n=== CP2K input generation: all settings ===')
    menu.show(f"Structure: {values['path'] or 'No structure loaded'}; frame: {values['frame']}")
    menu.show('s: Load/change structure; f: Change XYZ frame')
    menu.show(' -10. Back / cancel generation')
    for number, field in NUMBERED_FIELDS:
        if number == 1:
            menu.show('   0. Review & generate input file')
        if number == 101:
            menu.heading('Additional settings (100+ are cp2kkit extensions)')
        if number not in selectable:
            continue
        origin = 'user edit' if field.name in values['_edited'] else values['_origins'][field.name]
        menu.show(f' {number:3}. {LABELS[field.name]}: {field_display(field, values)} [{origin}]')
    menu.show('  r. Review effective settings\n  p. Preview full input and replay command\n'
              '  w. Review & write files (alias for 0)')
    return selectable


def review(menu, values, full=False):
    try:
        if not values['path']:
            raise KitError('Structure path is required; use s to load a structure')
        return menu.review(values, full=full)
    except (KitError, OSError) as exc:
        menu.show(f'Error: Validation failed (no files written): {exc}. Fix the draft before writing files.')
        return None


def edit_source(menu, values, name):
    """Source controls live in the structure header, not the numbered settings."""
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
        values['output'] = Path(new).stem+'.inp'
    compatibility(menu, values)


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
    try:
        menu.show('Creates new files only; no calculations. Source supplies geometry, not charge/spin/method.')
        menu.show('Implemented main-menu IDs follow Multiwfn 2026.10.1; 100+ are local extensions. '
                  'Inapplicable fields are hidden, not reset.')
        menu.show('Parameter Enter keeps; back abandons an edit; literal 0 is a value (basis chooser: 0 returns). '
                  'Menu 0 generates after confirmation; -10/back/cancel returns; q exits.')
        while True:
            selectable = show_settings(menu, values)
            raw = menu.ask('Select a displayed number, s/f, r/p/w; -10/back returns: ').lower()
            if raw in {'-10', 'back'}:
                raise Cancelled
            if raw in {str(number) for number in selectable}:
                field = selectable[int(raw)]
                old = values[field.name]
                if field.name == 'magnetism':
                    try:
                        structure = read_structure(values['path'], values['frame']) if values['path'] else None
                        if structure is not None:
                            menu.show('Atom indices below refer to loaded/expanded geometry, not CIF site labels [angstrom]:')
                            for index, (element, position) in enumerate(zip(structure.symbols, structure.positions), 1):
                                menu.show(f'  @{index}: {element} ' + ' '.join(f'{x:.8f}' for x in position))
                    except (KitError, OSError) as exc:
                        menu.show(f'Warning: Atom list unavailable: {exc}')
                    menu.show('An explicit magnetic request enables UKS. Charge/multiplicity stay unchanged. '
                              'Element seeds apply first; @atom seeds override them. This is an initial guess, not a moment constraint.')
                previous_sources = tuple(values[name] for name in ('data_dir', 'basis_files', 'potential_files',
                                         'custom_basis_file', 'custom_basis_name', 'custom_potential_file', 'custom_potential_name'))
                values[field.name] = menu.edit(field, old, values)
                if values[field.name] != old or previous_sources != tuple(values[name] for name in (
                        'data_dir', 'basis_files', 'potential_files', 'custom_basis_file', 'custom_basis_name',
                        'custom_potential_file', 'custom_potential_name')):
                    values['_edited'].add(field.name)
                    compatibility(menu, values)
            elif raw in {'s', 'f'}:
                edit_source(menu, values, 'path' if raw == 's' else 'frame')
            elif raw in {'r', 'p', 'w', '0'}:
                validated = review(menu, values, full=raw == 'p')
                if validated is None:
                    continue
                if raw in {'r', 'p'}:
                    menu.ask('Enter to return to all settings; q exits: ')
                    continue
                answer = menu.ask('Write these two new files? [y/N]; back returns; cancel cancels; q exits: ').lower()
                if answer not in {'y', 'yes'}:
                    menu.show('Not confirmed; no files written. Returning to all settings.')
                    continue
                try:
                    # Re-read/revalidate; the shared exclusive writer protects both files and rolls back.
                    result = write_input(read_structure(values['path'], values['frame']),
                                         settings_from(values), values['output'])
                except (KitError, OSError) as exc:
                    menu.show(f'Error: {exc}. No unfinished output retained.')
                    # A collision/I/O recovery prompt, not a persistent output-path setting.
                    new = menu.ask('New input path for retry; Enter/back returns to settings; cancel/q: ')
                    if new and new.lower() != 'back':
                        try:
                            from .input_tui import parse_value
                            values['output'] = parse_value(FIELDS['output'], new)
                            values['_auto_output'] = False
                        except ValueError as error:
                            menu.show(f'Error: {error}. Target unchanged.')
                    continue
                menu.show('Success: Input and provenance sidecar generated; no calculation was run.')
                for target in result[:2]:
                    menu.show(f'Generated path: {Path(target).resolve()}')
                menu.show(f"Task: {values['run_type']}; GPW/{values['functional']}; "
                          f"basis: {values['basis']}; dispersion: {values['dispersion']}")
                for warning in result[2]:
                    menu.show(f'Warning: {warning}')
                menu.ask('Enter to return to the menu; q exits: ')
                return 0
            elif not raw:
                menu.show('No files written. Select a field, r/p to inspect, or 0/w to review & write.')
            else:
                menu.show('Error: Invalid menu number or action')
    except (Cancelled, KeyboardInterrupt):
        menu.show('Cancelled; no unfinished files generated. Completed files, if any, are retained.')
        return 0
    except SessionExit:
        if parent_session:
            raise
        menu.show('Exited the session; completed files, if any, are retained.')
        return 0
