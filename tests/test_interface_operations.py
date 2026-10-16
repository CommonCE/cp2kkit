"""Reader registration, CLI routing and shared export regressions; no calculations."""
import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main, menu_request
from cp2kkit.errors import KitError, OutputExists, ParseError
from cp2kkit.export import export_structure_files
from cp2kkit.input_tui import Menu
from cp2kkit.main_tui import choose_structure, run_main_menu
from cp2kkit.structure import (STRUCTURE_FORMATS, STRUCTURE_SUFFIXES, is_structure_path,
                               read_structure, structure_format)

FIXTURES = Path(__file__).parent/'fixtures'


class TTY(io.StringIO):
    def isatty(self):
        return True


class StructureRegistryTests(unittest.TestCase):
    def test_aliases_and_special_names_select_the_same_readers(self):
        cases = {'.xyz': ('xyz', 'cp2kkit.structure.read_xyz'),
                 '.extxyz': ('xyz', 'cp2kkit.structure.read_xyz'),
                 '.restart': ('restart', 'cp2kkit.structure.read_restart'),
                 '.gjf': ('gjf', 'cp2kkit.structure_formats.read_gjf'),
                 '.com': ('gjf', 'cp2kkit.structure_formats.read_gjf'),
                 '.cif': ('cif', 'cp2kkit.structure_formats.read_cif'),
                 '.vasp': ('poscar', 'cp2kkit.structure_formats.read_poscar'),
                 '.poscar': ('poscar', 'cp2kkit.structure_formats.read_poscar')}
        self.assertEqual(STRUCTURE_SUFFIXES, frozenset(cases))
        for suffix, (fmt, target) in cases.items():
            for ending in (suffix, suffix.upper()):
                path = Path('directory')/('structure'+ending)
                with self.subTest(path=path), patch(target) as reader:
                    self.assertTrue(is_structure_path(path))
                    self.assertEqual(structure_format(path), fmt)
                    self.assertIs(read_structure(path), reader.return_value)
                    reader.assert_called_once_with(path, -1) if fmt == 'xyz' else reader.assert_called_once_with(path)
        for name in ('POSCAR', 'CONTCAR', 'poscar', 'contcar', 'Poscar'):
            with self.subTest(name=name), patch('cp2kkit.structure_formats.read_poscar') as reader:
                self.assertTrue(is_structure_path(name))
                self.assertIs(read_structure(name), reader.return_value)
                reader.assert_called_once_with(name)

    def test_unknown_names_and_non_xyz_frame_contract(self):
        for path in ('unknown', 'structure.inp', 'POSCAR.old', 'structure.cube', '.xyz'):
            with self.subTest(path=path):
                self.assertFalse(is_structure_path(path))
                with self.assertRaisesRegex(ParseError, 'Supported structures'):
                    read_structure(path)
        for path in ('structure.restart', 'structure.cif', 'POSCAR', 'structure.gjf'):
            with self.subTest(path=path), self.assertRaisesRegex(ParseError, '--frame applies only'):
                read_structure(path, frame=0)

    def test_new_alias_drives_menu_and_reader_without_a_second_list(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'a.newgeom'
            source.write_text('1\nsynthetic\nHe 0 0 0\n')
            (root/'z.txt').write_text('not a structure')
            (root/'directory.xyz').mkdir()
            log = TTY()
            with patch.dict(STRUCTURE_FORMATS, {'.newgeom': 'xyz'}), patch('cp2kkit.main_tui.Path.cwd', return_value=root):
                chosen, structure = choose_structure(Menu(TTY('1\n'), log, plain=True))
                self.assertEqual(chosen, source)
                self.assertEqual(structure.symbols, ['He'])
            self.assertIn('1. a.newgeom', log.getvalue())
            self.assertNotIn('z.txt', log.getvalue())
            self.assertNotIn('directory.xyz', log.getvalue())


class CLIRoutingTests(unittest.TestCase):
    def test_menu_invocation_matrix(self):
        commands = build_parser().command_names
        cases = [([], (None, False)), (['--plain'], (None, True)),
                 (['water.xyz'], ('water.xyz', False)),
                 (['--plain', 'water.xyz'], ('water.xyz', True)),
                 (['water.xyz', '--plain'], ('water.xyz', True)),
                 (['unknown-word'], ('unknown-word', False)),
                 (['./-water.xyz'], ('./-water.xyz', False)),
                 (['--', '-water.xyz'], ('-water.xyz', False)),
                 (['--plain', '--', '-water.xyz'], ('-water.xyz', True)),
                 (['--', 'parse'], ('parse', False)),
                 (['--', '--plain'], ('--plain', False)),
                 (['--'], None), (['--version'], None), (['--help'], None),
                 (['-water.xyz'], None), (['--unknown'], None),
                 (['unknown-word', 'extra'], None), (['water.xyz', '--bad'], None),
                 (['parse', '--'], None), (['parse', '--', '-output.out'], None),
                 (['--bad', '--', 'water.xyz'], None), (['--', 'a.xyz', 'b.xyz'], None)]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(menu_request(argv, commands), expected)
        for command in commands:
            self.assertIsNone(menu_request([command], commands))
            self.assertIsNone(menu_request(['--plain', command], commands))

    def test_registered_commands_are_discovered_without_a_manual_name_set(self):
        original = argparse.ArgumentParser.add_subparsers
        def add_subparsers(parser, *args, **kwargs):
            sub = original(parser, *args, **kwargs)
            sub.add_parser('future-command')
            return sub
        with patch.object(argparse.ArgumentParser, 'add_subparsers', add_subparsers):
            parser = build_parser()
        self.assertIn('future-command', parser.command_names)
        self.assertIsNone(menu_request(['future-command'], parser.command_names))

    def test_main_uses_menu_request_without_changing_paths(self):
        for argv, path, plain in (([], None, False), (['--plain', 'water.xyz'], 'water.xyz', True),
                                  (['--', '-water.xyz'], '-water.xyz', False),
                                  (['--plain', '--', 'parse'], 'parse', True)):
            with self.subTest(argv=argv), patch('cp2kkit.main_tui.run_main_menu', return_value=0) as menu:
                self.assertEqual(main(argv), 0)
                menu.assert_called_once_with(path, plain=plain)

    def test_batch_commands_and_invalid_mixed_arguments_do_not_enter_menu(self):
        for argv in (['discover'], ['parse', 'synthetic.out'], ['report', 'synthetic.out', '--strict'],
                     ['--plain', 'generate-input', 'synthetic.xyz', '-o', 'new.inp']):
            with self.subTest(argv=argv), patch('cp2kkit.main_tui.run_main_menu') as menu, patch('cp2kkit.cli.execute', return_value=0) as execute:
                self.assertEqual(main(argv), 0)
                menu.assert_not_called()
                execute.assert_called_once()
        for argv in (['unknown-command', 'extra'], ['--bad'], ['--'], ['water.xyz', '--bad']):
            with self.subTest(argv=argv), patch('cp2kkit.main_tui.run_main_menu') as menu, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(argv)
            self.assertEqual(raised.exception.code, 2)
            menu.assert_not_called()

    def test_explicit_path_menu_still_requires_both_ttys(self):
        with patch('sys.stdin', io.StringIO()), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(['--plain', '--', '-water.xyz']), 2)
        self.assertIn('TTY', err.getvalue())


class SharedStructureExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.dir/'synthetic.xyz'
        self.source.write_text('1\nsynthetic\nHe 0 0 0\n')
        self.structure = read_structure(self.source)
        self.out = self.dir/'new.extxyz'
        self.sidecar = Path(str(self.out)+'.json')

    def test_cli_menu_and_operation_produce_identical_bytes_and_warnings(self):
        direct, sidecar, warnings = export_structure_files(self.structure, self.out)
        cli_out, menu_out = self.dir/'cli.extxyz', self.dir/'menu.extxyz'
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(['export-structure', str(self.source), '-o', str(cli_out)]), 0)
        self.assertEqual(stdout.getvalue(), '')
        log = TTY()
        # The menu must not call back into the CLI composition root or capture stderr.
        with patch('cp2kkit.cli.build_parser', side_effect=AssertionError('menu parsed argv')), patch('cp2kkit.cli.execute', side_effect=AssertionError('menu called CLI')):
            self.assertEqual(run_main_menu(str(self.source), stdin=TTY(f'3\n{menu_out}\n\n0\n'), stdout=log, plain=True), 0)
        for path in (cli_out, menu_out):
            self.assertEqual(path.read_bytes(), direct.read_bytes())
            self.assertEqual(Path(str(path)+'.json').read_bytes(), sidecar.read_bytes())
        for warning in warnings:
            self.assertIn('WARNING: '+warning, err.getvalue())
            self.assertIn('Warning: '+warning, log.getvalue())
        self.assertEqual(self.source.read_text(), '1\nsynthetic\nHe 0 0 0\n')

    def test_known_cell_permissions_and_metadata_are_preserved(self):
        structure = read_structure(FIXTURES/'water.restart')
        before = structure.to_dict()
        with self.assertRaisesRegex(KitError, 'Plain XYZ loses the cell'):
            export_structure_files(structure, self.out, fmt='xyz')
        self.assertFalse(self.out.exists())
        _, sidecar, warnings = export_structure_files(structure, self.out, fmt='xyz', allow_cell_loss=True)
        self.assertTrue(warnings)
        manifest = json.loads(sidecar.read_text())
        self.assertEqual(manifest['cell'], before['cell'])
        self.assertEqual(manifest['pbc'], before['pbc'])
        self.assertEqual(manifest['source'], before['source'])
        self.assertEqual(manifest['export_format'], 'xyz')
        self.assertEqual(structure.to_dict(), before)

    def test_output_and_sidecar_collisions_preserve_existing_files(self):
        for target in (self.out, self.sidecar):
            with self.subTest(target=target):
                target.write_text('valuable existing content')
                with self.assertRaises(OutputExists):
                    export_structure_files(self.structure, self.out)
                self.assertEqual(target.read_text(), 'valuable existing content')
                other = self.sidecar if target == self.out else self.out
                self.assertFalse(other.exists())
                target.unlink()  # This test's synthetic artifact only.

    def test_real_writer_failures_roll_back_both_outputs(self):
        for target in ('cp2kkit.export.xyz_text', 'cp2kkit.export.json_text'):
            with self.subTest(target=target), patch(target, side_effect=OSError('synthetic serialization failure')):
                with self.assertRaises(OSError):
                    export_structure_files(self.structure, self.out)
                self.assertFalse(self.out.exists())
                self.assertFalse(self.sidecar.exists())

    def test_interrupt_rolls_back_and_invalid_format_does_not_create_files(self):
        with patch('cp2kkit.export.json_text', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            export_structure_files(self.structure, self.out)
        self.assertFalse(self.out.exists())
        self.assertFalse(self.sidecar.exists())
        with self.assertRaisesRegex(KitError, 'Unsupported structure export format'):
            export_structure_files(self.structure, self.out, fmt='cif')
        self.assertFalse(self.out.exists())
