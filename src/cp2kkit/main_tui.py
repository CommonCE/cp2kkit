"""Application-level numbered menu; batch CLI remains independent."""
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .errors import KitError
from .export import export_structure_files
from .input_tui import Cancelled, SessionExit, Field, Menu, run_interactive
from .inputgen import InputSettings
from .presentation import require_terminal
from .structure import is_structure_path, read_structure


@dataclass(frozen=True)
class Action:
    id: str
    group: str
    label: str
    requires_structure: bool = False


ACTIONS = (
    Action('load', 'Structure', 'Load/change structure file'),
    Action('details', 'Structure', 'Structure details', True),
    Action('export', 'Structure', 'Export structure (extXYZ)', True),
    Action('generate', 'Calculation', 'Generate CP2K input', True),
    Action('quality', 'Analysis', 'CP2K output quality report'),
    Action('cube_check', 'Analysis', 'Check scalar CUBE'),
    Action('cube_diff', 'Analysis', 'Subtract aligned density CUBEs'),
)


def periodicity(structure):
    if structure.pbc is None:
        return 'Unknown'
    return ''.join(a for a, flag in zip('XYZ', structure.pbc) if flag) or 'NONE'


def structure_summary(structure, path):
    counts = Counter(structure.symbols)
    # Hill order when carbon is present; alphabetical order otherwise.
    order = (['C'] + (['H'] if 'H' in counts else []) + sorted(set(counts)-{'C', 'H'})
             if 'C' in counts else sorted(counts))
    formula = ''.join(s + (str(counts[s]) if counts[s] != 1 else '') for s in order)
    lengths, angles = 'Unknown', 'Unknown'
    if structure.cell is not None:
        norms = [math.sqrt(sum(x*x for x in vector)) for vector in structure.cell]
        lengths = ' / '.join(f'{x:.5f}' for x in norms)
        angle_values = []
        for i, j in ((1, 2), (0, 2), (0, 1)):
            cosine = sum(a*b for a, b in zip(structure.cell[i], structure.cell[j])) / (norms[i]*norms[j])
            angle_values.append(math.degrees(math.acos(max(-1., min(1., cosine)))))
        angles = ' / '.join(f'{x:.3f}' for x in angle_values)
    return [('File', Path(path).name), ('Formula', formula), ('Atoms', len(structure.symbols)),
            ('Cell lengths [angstrom]', lengths), ('Angles [degrees]', angles),
            ('Periodicity', periodicity(structure))]


def choose_structure(menu):
    candidates = sorted((p for p in Path.cwd().iterdir() if p.is_file() and
                         is_structure_path(p)),
                        key=lambda p: p.name)
    menu.show('\n--- Select a structure file (current directory) ---')
    for i, path in enumerate(candidates, 1):
        menu.show(f'  {i}. {path.name}')
    menu.show('  0. Back')
    while True:
        raw = menu.ask('File number or path; 0/back/Enter returns; cancel cancels; q exits: ')
        if not raw or raw.lower() in {'0', 'back'}:
            return None
        selected = candidates[int(raw)-1] if raw in {str(i) for i in range(1, len(candidates)+1)} else Path(raw).expanduser()
        try:
            return selected, read_structure(selected)
        except (KitError, OSError) as exc:
            menu.show(f'Error: Cannot load structure: {exc}. Previous structure retained; retry or back.')


def optional_details(menu, report):
    from .io import json_text
    raw = menu.ask('Enter returns to main menu; d shows full details; q exits: ').lower()
    while raw not in {'', '0', 'back'}:
        if raw == 'd':
            menu.show(json_text(report))
        else:
            menu.show('Error: Select d or Enter.')
        raw = menu.ask('Enter returns to main menu; d shows full details; q exits: ').lower()


def required_path(menu, label):
    raw = menu.ask(f'{label}; Enter/0/back returns; cancel cancels; q exits: ')
    if not raw or raw.lower() in {'0', 'back'}:
        raise Cancelled
    return str(Path(raw).expanduser())


def cube_options(menu):
    from .cube import DIALECTS, SCALAR_TYPES, SCALAR_UNITS, CubeOptions
    menu.show('CUBE interpretation: auto uses supported producer evidence; unknown is not electron count.')
    values = ['auto', None, 'auto', 'auto']
    raw = menu.ask('Enter keeps auto interpretation; a edits explicit unit/meaning assertions; q exits: ').lower()
    while raw not in {'', 'a'}:
        if raw in {'0', 'back'}:
            raise Cancelled
        menu.show('Error: Select Enter or a for CUBE interpretation.')
        raw = menu.ask('Enter keeps auto; a edits assertions; 0/back returns; cancel/q: ').lower()
    if raw == 'a':
        fields = (Field('dialect', 'Producer dialect', choices=DIALECTS),
                  Field('length', 'Spatial unit (assertion, not conversion)', choices=('bohr', 'angstrom'), optional=True),
                  Field('scalar', 'Scalar meaning', choices=SCALAR_TYPES),
                  Field('unit', 'Scalar unit', choices=SCALAR_UNITS))
        values = [menu.edit(f, v) for f, v in zip(fields, values)]
    return CubeOptions(*values)


def analysis(menu, action):
    if action == 'quality':
        from .parser import parse_output
        from .discovery import resolve_output
        from .quality import quality_report
        path = required_path(menu, 'CP2K output file/directory path')
        report = quality_report(parse_output(resolve_output(path)))
        menu.show('Success: Output parsed. Parsing success is not calculation convergence.')
        menu.show(f"Source: {report['source']['path']}")
        menu.show(f"Software: {report['software']} {report['software_version']}; project: {report['project']}")
        menu.show(f"{'Success' if report['status'] == 'passed' else 'Warning'}: Text quality status: {report['status']}")
        for segment in report['segments']:
            menu.show(f"Segment {segment['segment']}: {segment['status']}; completed={segment['completed']}; "
                      f"SCF={segment['electronic_converged']}; geometry={segment['geometry_converged']}")
            for key in ('final_energy', 'wall_time'):
                value = segment[key]
                menu.show(f"{key}: {value['value']} {value['unit']}" if value else f'{key}: Unknown')
            for reason in segment['reasons']:
                menu.show(f'Warning: {reason}')
        for warning in report['parser_warnings']:
            menu.show(f'Warning: {warning}')
        menu.show('Passed text checks do not certify physical validity. Missing exit status/forces are not inferred.')
    else:
        from .cube import check_cube, diff_cubes
        first = required_path(menu, 'CUBE path')
        paths = [first]
        output = None
        if action == 'cube_diff':
            while True:
                raw = menu.ask('Fragment CUBE path (one per line); Enter finishes; back/cancel/q: ')
                if not raw:
                    if len(paths) > 1:
                        break
                    menu.show('Error: At least one fragment is required.')
                elif raw.lower() in {'0', 'back'}:
                    raise Cancelled
                else:
                    paths.append(str(Path(raw).expanduser()))
            output = required_path(menu, 'New difference CUBE output path')
        options = cube_options(menu)
        report = check_cube(first, options) if output is None else diff_cubes(paths, output, options)
        menu.show('Success: Scalar CUBE processing completed; reference-state validity is not certified.')
        if output:
            for target in (output, output+'.json'):
                menu.show(f'Generated path: {Path(target).resolve()}')
        else:
            menu.show(f'Source: {Path(first).resolve()}')
        # The summary is bounded; complete format/unit/hash/statistics evidence is optional.
        metadata = report.get('output', report)
        for key in ('shape', 'scalar_type', 'scalar_unit', 'length_unit'):
            if key in metadata:
                menu.show(f'{key}: {metadata[key]}')
        stats = report['statistics']
        menu.show(f"Samples: {stats['value_count']}; min={stats['minimum']}; max={stats['maximum']}")
        for key in ('integral', 'positive_integral', 'negative_integral'):
            quantity = stats[key]
            menu.show(f"{key}: {quantity['value']} {quantity['unit']} ({quantity['quantity']})")
        for warning in report['warnings']:
            menu.show(f'Warning: {warning}')
    optional_details(menu, report)


def export_structure(menu, path):
    output = required_path(menu, 'New extXYZ output path')
    structure = read_structure(path)
    output, sidecar, warnings = export_structure_files(structure, output)
    menu.show('Success: Structure exported; source unchanged.')
    menu.show(f'Atoms: {len(structure.symbols)}; Periodicity: {periodicity(structure)}')
    for target in (output, sidecar):
        menu.show(f'Generated path: {Path(target).resolve()}')
    for warning in warnings:
        menu.show('Warning: '+warning)
    menu.ask('Enter to return to the main menu; q exits: ')


def run_main_menu(path=None, stdin=None, stdout=None, plain=False):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    require_terminal(stdin, stdout, 'Main menu')
    menu = Menu(stdin, stdout, plain)
    loaded, loaded_path = None, None
    if path is not None:
        try:
            loaded_path = str(Path(path).expanduser())
            loaded = read_structure(loaded_path)
        except (KitError, OSError) as exc:
            menu.show(f'Error: Cannot load initial structure: {exc}. Select another file from the menu.')
        except KeyboardInterrupt:
            menu.show('Cancelled initial load; returning to the main menu.')
    try:
        while True:
            menu.presenter.heading('\n=== cp2kkit Main menu ===')
            if loaded is None:
                menu.show('No structure loaded')
            else:
                menu.presenter.rows(structure_summary(loaded, loaded_path))
            group = None
            for i, action in enumerate(ACTIONS, 1):
                if group != action.group:
                    group = action.group
                    menu.presenter.heading(group)
                suffix = ' [Requires a structure]' if action.requires_structure and loaded is None else ''
                menu.show(f'  {i}. {action.label}{suffix}')
            menu.show('  0. Exit')
            # Interrupt at the main prompt exits; interrupts during an operation cancel it.
            raw = menu.ask(f'Select [0-{len(ACTIONS)}]: ')
            if raw == '0':
                return 0
            if raw not in {str(i) for i in range(1, len(ACTIONS)+1)}:
                menu.show('Error: Invalid menu number')
                continue
            action = ACTIONS[int(raw)-1]
            try:
                if action.id == 'load' or action.requires_structure and loaded is None:
                    selected = choose_structure(menu)
                    if selected is None:
                        continue
                    selected_path, structure = selected
                    loaded, loaded_path = structure, str(selected_path)
                    menu.show(f'Success: Structure loaded: {Path(loaded_path).resolve()}')
                    if action.id == 'load':
                        continue
                if action.id == 'details':
                    menu.presenter.rows(structure_summary(loaded, loaded_path))
                    menu.show(f'Full path: {Path(loaded_path).resolve()}')
                    optional_details(menu, loaded.to_dict())
                elif action.id == 'generate':
                    run_interactive(loaded_path, -1, None, InputSettings(),
                                    stdin=stdin, stdout=stdout, plain=plain, parent_session=True)
                elif action.id == 'export':
                    export_structure(menu, loaded_path)
                elif action.group == 'Analysis':
                    analysis(menu, action.id)
            except (Cancelled, KeyboardInterrupt):
                menu.show('Cancelled; returning to the main menu. Completed files, if any, are retained.')
            except (KitError, OSError) as exc:
                menu.show(f'Error: {exc}. Existing files unchanged; no unfinished output retained.')
                try:
                    menu.ask('Enter to return to the main menu; q exits: ')
                except (Cancelled, KeyboardInterrupt):
                    menu.show('Cancelled; returning to the main menu.')
    except (SessionExit, EOFError, KeyboardInterrupt, Cancelled):
        menu.show('Exited the session; completed files, if any, are retained.')
        return 0
