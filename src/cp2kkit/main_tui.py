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
    menu.show('\n--- 选择结构文件（当前目录）---')
    for i, path in enumerate(candidates, 1):
        menu.show(f'  {i}. {path.name}')
    raw = menu.ask('输入文件编号或完整/相对路径；回车返回；q 退出: ')
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
            menu.show('\n=== cp2kkit 主菜单 ===')
            if loaded is None:
                menu.show('当前未加载结构；请选择文件。')
            else:
                menu.show(f'已加载: {loaded_path}；原子数: {len(loaded.symbols)}；'
                          f'晶胞: {"有" if loaded.cell else "未知"}；PBC: {loaded.pbc}')
            menu.show('  1. 加载/更换结构文件\n  2. 生成 CP2K 输入文件\n'
                      '  3. 导出结构（extXYZ）\n  4. CP2K 输出质量报告\n  0. 退出')
            raw = menu.ask('选择功能编号；q 退出: ')
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
                        output = menu.ask('新 extXYZ 输出路径（回车返回）: ')
                        if output:
                            execute(build_parser().parse_args(['export-structure', loaded_path, '-o', output]))
                elif raw == '4':
                    from .parser import parse_output
                    from .discovery import resolve_output
                    from .quality import quality_report
                    from .io import json_text
                    output_path = menu.ask('CP2K 输出文件/目录路径（回车返回）: ')
                    if output_path:
                        menu.show(json_text(quality_report(parse_output(resolve_output(output_path)))))
                else:
                    menu.show('无效菜单编号')
            except (KitError, OSError) as exc:
                menu.show(f'操作失败: {exc}；已有文件保持不变。')
    except Cancelled:
        menu.show('已退出主菜单。')
        return 0
    except (EOFError, KeyboardInterrupt) as exc:
        raise KitError('Main menu interrupted; completed files, if any, are retained') from exc
