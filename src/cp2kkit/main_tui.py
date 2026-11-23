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
    Action('output_analysis', 'Analysis', 'Output analysis'),
    Action('cube_analysis', 'Analysis', 'CUBE analysis'),
    Action('vibration', 'Analysis', 'Vibrational analysis'),
)

ANALYSIS_GROUPS = {
    'output_analysis': ('Output analysis', (('quality', 'Quality report'),
                                            ('parse', 'Parse & export output'),
                                            ('plot', 'Plot energy / SCF convergence'))),
    'cube_analysis': ('CUBE analysis', (('cube_check', 'Check scalar CUBE'),
                                        ('cube_diff', 'Subtract density CUBEs'),
                                        ('cube_planar', 'Planar averages and cumulative integrals'))),
}


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


def analysis_choice(menu, label, choices, default):
    while True:
        raw = menu.ask(f'{label} ({"/".join(choices)}); Enter uses {default}; 0/back/cancel/q: ').lower()
        if raw in {'0', 'back'}:
            raise Cancelled
        if not raw or raw in choices:
            return raw or default
        menu.show(f'Error: Choose {" or ".join(choices)}.')


def read_analysis_output(menu):
    from .discovery import resolve_output
    from .parser import parse_output

    return parse_output(resolve_output(required_path(menu, 'CP2K output file/directory path')))


def parse_analysis(menu):
    from .export import write_csv
    from .io import json_text, new_file
    from .quality import quality_report

    run = read_analysis_output(menu)
    menu.show(f"Source: {run.source['path']}")
    menu.show(f'Software: {run.software}; version: {run.software_version or "Unknown"}; '
              f'project: {run.project or "Unknown"}')
    energies = sum(len(segment.energies) for segment in run.segments)
    scf = sum(len(segment.scf_iterations) for segment in run.segments)
    menu.show(f'Segments: {len(run.segments)}; observed records: energy={energies}, SCF={scf}')
    menu.show(f'Parser warnings: {len(run.parser_warnings)}')
    for warning in run.parser_warnings[:8]:
        menu.show(f'Warning: {warning}')
    if len(run.parser_warnings) > 8:
        menu.show('Additional warnings are available in full details.')
    menu.show('Parsed observations do not establish calculation convergence.')
    while True:
        raw = menu.ask('Enter/0/back returns; d details; j JSON; c CSV; cancel/q: ').lower()
        if raw in {'', '0', 'back'}:
            return
        if raw in {'d', 'j'}:
            output = required_path(menu, 'New parsed output JSON path') if raw == 'j' else None
            details = json_text({**run.to_dict(), 'quality': quality_report(run)})
            if output is None:
                menu.show(details)
                continue
            with new_file(output) as stream:
                stream.write(details)
        elif raw == 'c':
            output = required_path(menu, 'New parsed output CSV path')
            with new_file(output) as stream:
                write_csv(stream, run)
        else:
            menu.show('Error: Select d, j, c or Enter.')
            continue
        menu.show(f'Generated path: {Path(output).resolve()}')


def plot_analysis(menu):
    from .plot import plot_run
    from .quality import quality_report

    run = read_analysis_output(menu)
    kind = analysis_choice(menu, 'Plot kind', ('energy', 'scf'), 'energy')
    output = required_path(menu, 'New plot .png output path')
    for target in plot_run(run, output, kind):
        menu.show(f'Generated path: {target.resolve()}')
    menu.show(f'Text quality status: {quality_report(run)["status"]}. A plot does not certify convergence or physical validity.')
    for warning in run.parser_warnings[:8]:
        menu.show(f'Warning: {warning}')
    if len(run.parser_warnings) > 8:
        menu.show('Additional warnings are available in the plot JSON sidecar.')


def planar_analysis(menu):
    from .cube_profile import write_planar_profile

    path = required_path(menu, 'CUBE path')
    axis = analysis_choice(menu, 'Native grid index axis (not necessarily Cartesian)', ('x', 'y', 'z'), 'z')
    options = cube_options(menu)
    output = Path(required_path(menu, 'New planar profile CSV output path'))
    report = write_planar_profile(path, output, axis, options)
    for target in (output, Path(str(output)+'.json')):
        menu.show(f'Generated path: {target.resolve()}')
    menu.show(f"Native grid axis: {report['axis']}; planes: {len(report['planes'])}; "
              f"perpendicular spacing: {report['plane_spacing_angstrom']:.6g} angstrom")
    menu.show(f"Total integral: {report['total_integral_electrons']:.8g} {report['integral_unit']}")
    for warning in report['warnings']:
        menu.show(f'Warning: {warning}')
    return report


def analysis_group(menu, action):
    title, choices = ANALYSIS_GROUPS[action]
    menu.heading(f'\n--- {title} ---')
    by_number = {}
    for i, (action_id, label) in enumerate(choices, 1):
        menu.show(f'  {i}. {label}')
        by_number[str(i)] = action_id
    menu.show('  0. Back')
    while True:
        raw = menu.ask(f'Select [0-{len(choices)}]; cancel/q: ').lower()
        if raw in {'', '0', 'back'}:
            return
        if raw in by_number:
            analysis(menu, by_number[raw])
            return
        menu.show('Error: Invalid menu number')


def vibration_analysis(menu):
    from .io import json_text
    from .vibration_results import AmbiguousVibration, export_vibration, parse_threshold, parse_vibration

    path = required_path(menu, 'CP2K vibrational output file path')
    raw = menu.ask('Zero threshold [cm^-1]; Enter uses 0; back/cancel/q: ')
    if raw.lower() == 'back':
        raise Cancelled
    threshold = parse_threshold(raw) if raw else 0.0
    try:
        report = parse_vibration(path, zero_threshold_cm_1=threshold)
    except AmbiguousVibration as exc:
        choices = {f'{s}/{b}': (s, b) for s, b, _ in exc.choices}
        menu.show('Multiple normal-mode blocks (segment/block):')
        for s, b, line in exc.choices:
            menu.show(f'  {s}/{b}  heading line {line}')
        while True:
            raw = menu.ask('Segment/block; Enter/0/back returns; cancel/q: ').lower()
            if raw in {'', '0', 'back'}:
                return
            if raw in choices:
                segment, block = choices[raw]
                break
            menu.show('Error: Choose a listed segment/block.')
        report = parse_vibration(path, segment=segment, block=block, zero_threshold_cm_1=threshold)
        if report.source != exc.source:
            raise KitError('Output changed while selecting a block; reopen the report')

    menu.show(f"Source: {report.source['path']}")
    menu.show(f'Segment {report.segment}, block {report.block}: {report.status}; '
              f'program end marker: {"observed" if report.program_end else "not observed"}')
    if report.periodicity is not None or report.displacement_atoms:
        menu.show(f'Periodicity: {report.periodicity or "unknown"}; '
                  f'displacement atoms: {len(report.displacement_atoms)}')
    energy = report.reference_electronic_energy
    if energy is not None:
        menu.show(f'CP2K reference electronic energy: {energy.value:.8f} {energy.unit} '
                  f'(line {energy.source.line}; observation only)')
    counts = report.counts
    menu.show(f"Observed frequencies: {counts['observed']}; raw negatives: {counts['raw_negative']}")
    menu.show(f"Threshold: {threshold:g} cm^-1; negative={counts['negative']}, "
              f"near-zero={counts['near_zero']}, positive={counts['positive']}")
    for mode in report.modes[:10]:
        label = f'Mode {mode.mode_id}' if mode.mode_id is not None else f'Observation {mode.ordinal}'
        menu.show(f'  {label}: {mode.token} cm^-1 ({mode.classification})')
    if len(report.modes) > 10:
        menu.show('Only the first 10 frequencies are shown; use full details for all observations.')
    for warning in report.warnings[:8]:
        menu.show(f'Warning: {warning}')
    if len(report.warnings) > 8:
        menu.show('Additional warnings are available in full details.')
    menu.show('Text observations do not establish convergence, a clean process exit or a stationary point.')
    while True:
        raw = menu.ask('Enter returns; d details; j JSON; c CSV; s Shermo; cancel/q: ').lower()
        if raw in {'', '0', 'back'}:
            return
        if raw == 'd':
            menu.show(json_text(report.to_dict()))
        elif raw in {'j', 'c'}:
            output = required_path(menu, 'New vibration report path')
            export_vibration(output, report, 'json' if raw == 'j' else 'csv')
            menu.show(f'Generated path: {Path(output).resolve()}')
        elif raw == 's':
            shermo_analysis(menu, report)
        else:
            menu.show('Error: Select d, j, c, s or Enter.')


def shermo_analysis(menu, report):
    from .constraints import parse_fixed_atoms
    from .io import write_json
    from .thermochemistry import (THERMO_MODELS, VIBRATIONAL_ONLY_GRIMME_WARNING,
                                  parse_element_masses, run_shermo)

    if not report.strict_passed:
        raise KitError('Shermo requires a strict vibration report')

    class BackToReport(Exception):
        pass

    def ask_setting(label):
        value = menu.ask(f'{label}; back returns: ')
        if value.lower() == 'back':
            raise BackToReport
        return value

    try:
        model_raw = ask_setting('Thermal model: ideal-gas (default, imode=0) or vibrational-only (imode=1)').lower()
        thermo_model = model_raw or 'ideal-gas'
        if thermo_model not in THERMO_MODELS:
            raise KitError('Thermal model must be ideal-gas or vibrational-only')
        if thermo_model == 'vibrational-only':
            raw = ask_setting('CP2K single-point output path (required for vibrational-only)')
            if not raw:
                raise KitError('vibrational-only requires an independent full-system single-point output')
            energy_output = Path(raw).expanduser()
        else:
            raw = menu.ask('CP2K single-point output path; Enter uses the vibration reference energy: ')
            if raw.lower() == 'back':
                return
            energy_output = Path(raw).expanduser() if raw else None
            if energy_output is None and report.reference_electronic_energy is None:
                raise KitError('No unique native vibration reference energy; supply a single-point output')
        executable = required_path(menu, 'Trusted Shermo 2.6.2 executable path')
        geometry = required_path(menu, 'Reference XYZ geometry file')
        energy_segment = (ask_setting('Single-point segment (1-based); Enter requires a unique candidate')
                          if energy_output is not None else '')
        energy_segment = int(energy_segment) if energy_segment else None
        frame = int(ask_setting('Zero-based XYZ frame'))
        if thermo_model == 'vibrational-only':
            raw_active = ask_setting('Active Hessian atoms (1-based indices/ranges in full XYZ, e.g. 181-183)')
            try:
                active_atoms = parse_fixed_atoms(raw_active)
            except ValueError as exc:
                raise KitError(str(exc)) from exc
            if active_atoms == 'off':
                raise KitError('vibrational-only requires at least one active atom')
        else:
            active_atoms = None
        mass_tokens = ask_setting('Atomic masses [amu] in XYZ order, or El=mass pairs (e.g. Ga=69.723 O=15.9994 H=1.0079)').split()
        if mass_tokens and any('=' in token for token in mass_tokens):
            masses_amu, element_masses = None, parse_element_masses(mass_tokens)
        else:
            masses_amu, element_masses = [float(m) for m in mass_tokens], None
        multiplicity = int(ask_setting('Spin multiplicity'))
        temperature = float(ask_setting('Temperature [K]; Enter uses 298.15') or '298.15')
        pressure = (float(ask_setting('Pressure [atm]; Enter uses 1') or '1')
                    if thermo_model == 'ideal-gas' else 1.0)
        scale = float(ask_setting('Shared frequency scale; Enter uses 1') or '1')
        default_low = 'grimme' if thermo_model == 'ideal-gas' else 'harmonic'
        low_prompt = ('Low-frequency treatment: grimme (default) or harmonic' if default_low == 'grimme'
                      else 'Low-frequency treatment: harmonic (default) or grimme')
        low = ask_setting(low_prompt).lower() or default_low
    except BackToReport:
        return
    except ValueError as exc:
        raise KitError('Invalid numeric Shermo setting') from exc
    if thermo_model == 'ideal-gas':
        menu.show(f'Shermo (ideal-gas) will run at {temperature:g} K, {pressure:g} atm, scale {scale:g}, {low}.')
    else:
        menu.show(f'Shermo (vibrational-only, imode=1) will run at {temperature:g} K, scale {scale:g}, {low} '
                  '(pressure unused in imode=1).')
    menu.show(f'Electronic energy source: {energy_output if energy_output is not None else "vibration footer"}')
    if active_atoms is not None:
        menu.show(f'Active Hessian atoms (1-based in full XYZ): {active_atoms}')
    if thermo_model == 'vibrational-only' and low == 'grimme':
        menu.show(f'Warning: {VIBRATIONAL_ONLY_GRIMME_WARNING}')
    if menu.ask('Confirm matching reference geometry and electronic state for all sources, and run Shermo? [y/N]: ').lower() not in {'y', 'yes'}:
        return
    data = run_shermo(report.source['path'], geometry, executable=executable, frame=frame,
                      masses_amu=masses_amu, element_masses=element_masses, multiplicity=multiplicity,
                      confirm_reference=True, temperature=temperature, pressure=pressure, scale=scale,
                      low_frequency=low, segment=report.segment, block=report.block,
                      expected_source_sha256=report.source['sha256'], energy_output=energy_output,
                      energy_segment=energy_segment, thermo_model=thermo_model, active_atoms=active_atoms)
    menu.show(f"Shermo thermochemistry ({data['thermo_model']}, imode={data['imode']}) [hartree]:")
    menu.show(f"  ZPE: {data['zero_point_energy']['value']:.6f}")
    for key, total in data['corrected_totals'].items():
        menu.show(f"  {key}: {total['value']:.7f} (correction {data['thermal_corrections'][key]['value']:+.6f})")
    for warning in data.get('warnings', ()):
        menu.show(f'Warning: {warning}')
    menu.show(data['citation'])
    if menu.ask('Export Shermo result as JSON? [y/N]: ').lower() in {'y', 'yes'}:
        path = required_path(menu, 'New Shermo JSON path')
        write_json(path, data)
        menu.show(f'Generated path: {Path(path).resolve()}')


def analysis(menu, action):
    if action == 'parse':
        return parse_analysis(menu)
    if action == 'plot':
        plot_analysis(menu)
        menu.ask('Enter/0/back returns; cancel/q: ')
        return
    if action == 'cube_planar':
        report = planar_analysis(menu)
    elif action == 'quality':
        from .quality import quality_report
        report = quality_report(read_analysis_output(menu))
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
    elif action in {'cube_check', 'cube_diff'}:
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
            output = Path(required_path(menu, 'New difference CUBE output path'))
        options = cube_options(menu)
        report = check_cube(first, options) if output is None else diff_cubes(paths, output, options)
        menu.show('Success: Scalar CUBE processing completed; reference-state validity is not certified.')
        if output is not None:
            for target in (output, Path(str(output)+'.json')):
                menu.show(f'Generated path: {target.resolve()}')
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
    else:
        raise KitError(f'Unknown analysis action: {action}')
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
                elif action.id in ANALYSIS_GROUPS:
                    analysis_group(menu, action.id)
                elif action.id == 'vibration':
                    vibration_analysis(menu)
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
