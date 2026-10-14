"""Application-level numbered menu; batch CLI remains independent."""
import sys
from pathlib import Path

from .errors import KitError
from .input_tui import Cancelled, Menu, run_interactive
from .inputgen import InputSettings
from .structure import read_structure

STRUCTURE_SUFFIXES = {'.xyz', '.extxyz', '.restart', '.gjf', '.com', '.cif', '.vasp', '.poscar'}


def choose_structure(menu):
    candidates = sorted((p for p in Path.cwd().iterdir() if p.is_file() and
                         (p.suffix.lower() in STRUCTURE_SUFFIXES or p.name.upper() in {'POSCAR', 'CONTCAR'})),
                        key=lambda p: p.name)
    menu.show('\n--- Select a structure file (current directory)---')
    for i, path in enumerate(candidates, 1):
        menu.show(f'  {i}. {path.name}')
    raw = menu.ask('Enter a file number or absolute/relative path; Enter to return; q to quit: ')
    if not raw:
        return None
    if raw in {str(i) for i in range(1, len(candidates)+1)}:
        return candidates[int(raw)-1]
    return Path(raw).expanduser()


def run_main_menu(path=None, stdin=None, stdout=None):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    if not stdin.isatty():
        raise KitError('Main menu requires a terminal (TTY); use subcommands for scripts')
    menu = Menu(stdin, stdout)
    loaded = read_structure(path) if path is not None else None
    loaded_path = str(path) if path is not None else None
    try:
        while True:
            menu.show('\n=== cp2kkit Main menu ===')
            if loaded is None:
                menu.show('No structure loaded; please select a file.')
            else:
                menu.show(f'Loaded: {loaded_path}; Atoms: {len(loaded.symbols)}; '
                          f'Cell: {"available" if loaded.cell else "unknown"}; PBC: {loaded.pbc}')
            menu.show('  1. Load/change structure file\n  2. Generate CP2K input\n'
                      '  3. Export structure (extXYZ)\n  4. CP2K output quality report\n  0. Exit')
            raw = menu.ask('Select a function number; q to quit: ')
            if raw == '0':
                return 0
            try:
                if raw == '1':
                    selected = choose_structure(menu)
                    if selected is not None:
                        structure = read_structure(selected)
                        loaded, loaded_path = structure, str(selected)
                elif raw in {'2', '3'}:
                    if loaded is None:
                        selected = choose_structure(menu)
                        if selected is None:
                            continue
                        loaded = read_structure(selected)
                        loaded_path = str(selected)
                    if raw == '2':
                        run_interactive(loaded_path, -1, Path(loaded_path).stem+'.inp', InputSettings(),
                                        stdin=stdin, stdout=stdout)
                    else:
                        from .cli import build_parser, execute
                        output = menu.ask('New extXYZ output path (Enter to return): ')
                        if output:
                            execute(build_parser().parse_args(['export-structure', loaded_path, '-o', output]))
                elif raw == '4':
                    from .parser import parse_output
                    from .discovery import resolve_output
                    from .quality import quality_report
                    from .io import json_text
                    output_path = menu.ask('CP2K output file/directory path (Enter to return): ')
                    if output_path:
                        menu.show(json_text(quality_report(parse_output(resolve_output(output_path)))))
                else:
                    menu.show('Invalid menu number')
            except (KitError, OSError) as exc:
                menu.show(f'Operation failed: {exc}; existing files are unchanged.')
    except Cancelled:
        menu.show('Exited the main menu.')
        return 0
    except (EOFError, KeyboardInterrupt) as exc:
        raise KitError('Main menu interrupted; completed files, if any, are retained') from exc
