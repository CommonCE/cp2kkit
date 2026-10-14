"""Synthetic format/default-menu regressions; no quantum chemistry execution."""
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import main
from cp2kkit.errors import KitError, ParseError
from cp2kkit.input_tui import GROUPS, run_interactive, visible_fields
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.main_tui import run_main_menu
from cp2kkit.structure import BOHR_TO_ANGSTROM, read_structure, xyz_text
from tests.test_input_tui import TTY

CIF = """data_synthetic
_cell_length_a 4.0(2)
_cell_length_b 5
_cell_length_c 6
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 60
_space_group_IT_number 1
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
O1 O .25 .5 .75 1
"""
POSCAR = """synthetic
1
4 0 0
1 5 0
0 0 6
O H
1 2
Direct
0 0 0
.25 0 0
0 .2 0
"""
GJF = "%chk=not-read.chk\n#p pbe/sto-3g\n\nSynthetic geometry\n\n1 2\n8 0 0 0\nH .76 0 .58\nH -.76 0 .58\n\n"


class FormatCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def read(self, name, text):
        path = self.dir/name
        path.write_text(text)
        got = read_structure(path)
        self.assertEqual(got.source['sha256'], hashlib.sha256(text.encode()).hexdigest())
        return got


class FormatTests(FormatCase):
    def test_gjf_charge_not_inherited_and_default_project(self):
        got = self.read('water.gjf', GJF)
        self.assertEqual(got.symbols, ['O', 'H', 'H'])
        self.assertEqual(got.pbc, [False]*3)
        self.assertEqual(got.source['gaussian_charge'], 1)
        text, manifest = generate_input(got, InputSettings())
        self.assertIn('PROJECT water', text)
        self.assertEqual(manifest['settings']['charge'], 0)
        self.assertEqual(manifest['settings']['multiplicity'], 1)
        self.assertIn('PROJECT custom', generate_input(got, InputSettings(project='custom'))[0])

    def test_gjf_bohr_tv_and_errors(self):
        got = self.read('water.com', GJF.replace('pbe/sto-3g', 'pbe/sto-3g units=au'))
        self.assertAlmostEqual(got.positions[1][0], .76*BOHR_TO_ANGSTROM)
        got = self.read('periodic.gjf', GJF.replace('H -.76 0 .58\n', 'H -.76 0 .58\nTV 10 0 0\nTV 0 10 0\nTV 0 0 10\n'))
        self.assertEqual(got.pbc, [True]*3)
        for text in (GJF+'--Link1--\n', GJF.replace('H .76 0 .58', 'H 1 R'),
                     GJF.replace('H .76 0 .58', 'Bq 0 0 0'),
                     GJF.replace('pbe/sto-3g', 'pbe/sto-3g units=nm'),
                     GJF.replace('H .76 0 .58', 'H nan 0 0')):
            with self.subTest(text=text), self.assertRaises(ParseError):
                self.read('bad.gjf', text)

    def test_poscar_direct_cartesian_and_scale(self):
        got = self.read('POSCAR', POSCAR)
        self.assertEqual(got.positions, [[0.,0.,0.], [1.,0.,0.], [.2,1.,0.]])
        self.assertEqual(got.pbc, [True]*3)
        self.assertIn('PROJECT POSCAR', generate_input(got, InputSettings())[0])
        got = self.read('box.vasp', POSCAR.replace('\n1\n', '\n2 3 4\n').replace('Direct', 'Cartesian'))
        self.assertEqual(got.cell, [[8.,0.,0.], [2.,15.,0.], [0.,0.,24.]])
        self.assertEqual(got.positions[1], [.5,0.,0.])
        got = self.read('CONTCAR', POSCAR.replace('\n1\n', '\n-960\n'))
        self.assertAlmostEqual(got.cell[0][0], 8.)

    def test_poscar_selective_metadata_and_errors(self):
        selective = POSCAR.replace('Direct', 'Selective dynamics\nDirect').replace('0 0 0\n.25', '0 0 0 F F F\n.25').replace('.25 0 0', '.25 0 0 T T T').replace('0 .2 0', '0 .2 0 T T T')
        got = self.read('POSCAR', selective)
        self.assertEqual(got.source['selective_dynamics'][0], ['F']*3)
        self.assertTrue(any('constraints' in w for w in generate_input(got, InputSettings())[1]['warnings']))
        for text in (POSCAR.replace('O H\n', ''), POSCAR.replace('\n1\n', '\n0\n'),
                     POSCAR.replace('1 2', '1 -2'), POSCAR.rsplit('0 .2 0', 1)[0],
                     POSCAR+'\n0 0 0\n', POSCAR.replace('Direct', 'unknown')):
            with self.subTest(text=text), self.assertRaises(ParseError):
                self.read('POSCAR', text)

    def test_cif_triclinic_symmetry_and_roundtrip(self):
        got = self.read('crystal.cif', CIF)
        self.assertEqual(got.symbols, ['O'])
        self.assertAlmostEqual(got.positions[0][0], 2.25)
        self.assertIn('PROJECT crystal', generate_input(got, InputSettings())[0])
        sym = CIF.replace('_space_group_IT_number 1', "loop_\n_space_group_symop_operation_xyz\n'x,y,z'\n'-x,-y,-z'\n'x,y,z'")
        got = self.read('sym.cif', sym)
        self.assertEqual(got.symbols, ['O', 'O'])
        back = self.read('roundtrip.extxyz', xyz_text(got))
        self.assertEqual(got.cell, back.cell)
        self.assertEqual(got.positions, back.positions)
        special = self.read('special.cif', sym.replace('.25 .5 .75', '0 0 0'))
        self.assertEqual(len(special.symbols), 1)
        shifted = self.read('shift.cif', sym.replace('-x,-y,-z', '-x+1/2,y,z'))
        self.assertEqual(len(shifted.symbols), 1)

    def test_cif_multiline_metadata_and_errors(self):
        self.read('metadata.cif', CIF+"_publ_section_title\n;A title\nwith # comments and 'quotes'\n;\n")
        for text in (CIF.replace('.75 1', '.75 .5'), CIF.replace('number 1', 'number 2'),
                     CIF.replace('_cell_length_a 4.0(2)', '_cell_length_a ?'), CIF+'data_second\n',
                     CIF.replace('.25 .5 .75 1', '.25 .5'), CIF+'\n_title\n;unclosed',
                     CIF.replace('number 1', "number 2\nloop_\n_space_group_symop_operation_xyz\n'x,y,__import__(x)'")):
            with self.subTest(text=text), self.assertRaises(ParseError):
                self.read('bad.cif', text)

    def test_frame_non_xyz_and_unknown_extensions(self):
        self.read('water.gjf', GJF)
        with self.assertRaisesRegex(ParseError, 'only to XYZ'):
            read_structure(self.dir/'water.gjf', 0)
        with self.assertRaises(ParseError):
            read_structure(self.dir/'unknown.pdb')

    def test_defaults_scf_and_atom_based_added_mos(self):
        got = self.read('water.gjf', GJF)
        text, manifest = generate_input(got, InputSettings())
        self.assertIn('CUTOFF [Ry] 400', text)
        self.assertIn('REL_CUTOFF [Ry] 55', text)
        self.assertIn('      MAX_SCF 25', text)
        self.assertIn('        MAX_SCF 20', text)
        self.assertNotIn('ADDED_MOS', text)
        for n, expected in ((3,30), (59,30), (61,31), (65,33), (100,50)):
            structure = replace(got, symbols=['He']*n, positions=[[0.,0.,0.]]*n)
            settings = InputSettings(scf='diag', smearing=300)
            text, m = generate_input(structure, settings)
            self.assertIn('MAX_SCF 128', text)
            self.assertEqual(m['settings']['added_mos'], expected)
            self.assertNotIn('&OUTER_SCF', text)
            explicit = generate_input(structure, replace(settings, added_mos=7))[1]
            self.assertEqual(explicit['settings']['added_mos'], 7)
        self.assertEqual(generate_input(got, InputSettings(scf='diag'))[1]['settings']['added_mos'], 0)
        for s in (InputSettings(added_mos=2), InputSettings(smearing=300), InputSettings(max_outer_scf=0)):
            with self.assertRaises(KitError):
                generate_input(got, s)
        text, _ = generate_input(got, InputSettings(max_scf=12, max_outer_scf=8))
        self.assertIn('MAX_SCF 12', text)
        self.assertIn('MAX_SCF 8', text)

    def test_uks_auto_orbitals_and_cli_override(self):
        got = self.read('water.gjf', GJF)
        text, _ = generate_input(got, InputSettings(scf='diag', smearing=300, charge=1, multiplicity=2))
        self.assertIn('ADDED_MOS 30 30', text)
        with self.assertRaisesRegex(KitError, 'source path'):
            generate_input(replace(got, source={}), InputSettings())
        output = self.dir/'explicit.inp'
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['generate-input', str(self.dir/'water.gjf'), '-o', str(output),
                                   '--scf', 'diag', '--smearing', '300', '--added-mos', '9']), 0)
        self.assertIn('ADDED_MOS 9', output.read_text())
        self.assertIn('PROJECT water', output.read_text())

    def test_tui_smearing_auto_updates_with_structure_size(self):
        self.read('helium.xyz', '65\nsynthetic\n'+'He 0 0 0\n'*65)
        output = self.dir/'helium.inp'
        log = TTY()
        run_interactive(str(self.dir/'helium.xyz'), -1, str(output), InputSettings(periodic='NONE'),
                        stdin=TTY('4\ndiag\n6\n300\n0\ny\n\n'), stdout=log, plain=True)
        self.assertIn('33 (auto)', log.getvalue())
        self.assertIn('ADDED_MOS 33', output.read_text())

    def test_dynamic_visibility_and_actual_auto_values(self):
        got = self.read('crystal.cif', CIF)
        values = {**asdict(InputSettings()), 'path': str(self.dir/'crystal.cif'), 'frame': -1}
        fields = [f for _, fs in GROUPS for f in fs]
        def names():
            return {f.name for f in visible_fields(fields, values)}
        self.assertFalse({'pressure', 'vacuum', 'smearing', 'added_mos'} & names())
        values.update(run_type='CELL_OPT', scf='diag')
        self.assertTrue({'pressure', 'smearing', 'added_mos'} <= names())
        self.assertNotIn('max_outer_scf', names())
        values['periodic'] = 'NONE'
        self.assertIn('vacuum', names())
        log = TTY()
        run_interactive(str(self.dir/'crystal.cif'), -1, str(self.dir/'new.inp'), InputSettings(),
                        stdin=TTY('q\n'), stdout=log, plain=True)
        self.assertNotIn('CELL_OPT pressure', log.getvalue())
        self.assertNotIn('Isolated box padding', log.getvalue())
        self.assertNotIn('Smearing [K]', log.getvalue())
        self.assertNotIn('ADDED_MOS:', log.getvalue())
        self.assertIn('Structure:', log.getvalue())
        self.assertNotIn('Project name:', log.getvalue())


class MainMenuTests(FormatCase):
    def test_default_entry_load_generate_and_return(self):
        self.read('crystal.cif', CIF)
        output = self.dir/'crystal.inp'
        log, err = TTY(), io.StringIO()
        lines = '0\ny\n\n0\n'
        previous = Path.cwd()
        try:
            os.chdir(self.dir)
            with patch('sys.stdin', TTY('4\n'+lines)), redirect_stdout(log), redirect_stderr(err):
                self.assertEqual(main(['--plain', str(self.dir/'crystal.cif')]), 0)
        finally:
            os.chdir(previous)
        self.assertTrue(output.exists())
        self.assertEqual(json.loads(Path(str(output)+'.json').read_text())['settings']['project'], 'crystal')
        self.assertGreaterEqual(log.getvalue().count('cp2kkit Main menu'), 2)

    def test_no_path_load_choice_and_invalid_file_keep_loaded(self):
        self.read('POSCAR', POSCAR)
        log = TTY()
        with patch('pathlib.Path.cwd', return_value=self.dir):
            self.assertEqual(run_main_menu(stdin=TTY('1\n1\n1\nmissing.cif\nback\n0\n'), stdout=log, plain=True), 0)
        self.assertIn('No structure loaded', log.getvalue())
        self.assertIn('Atoms: 3', log.getvalue())
        self.assertIn('Previous structure retained', log.getvalue())

    def test_application_menu_and_prompts_are_english(self):
        self.read('POSCAR', POSCAR)
        log = TTY()
        run_main_menu(str(self.dir/'POSCAR'), stdin=TTY('1\n\n4\ncancel\n5\nmissing.out\n\n3\n\n0\n'),
                      stdout=log, plain=True)
        self.assertTrue(log.getvalue().isascii(), log.getvalue())
        self.assertIn('Select a structure file', log.getvalue())
        self.assertIn('New extXYZ output path', log.getvalue())
        self.assertIn('Error:', log.getvalue())

    def test_cli_bare_cancel_non_tty_and_invalid_initial_path(self):
        with patch('sys.stdin', TTY('0\n')), redirect_stdout(TTY()):
            self.assertEqual(main([]), 0)
        with patch('sys.stdin', io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main([]), 2)
        log = TTY()
        with patch('sys.stdin', TTY('0\n')), redirect_stdout(log):
            self.assertEqual(main(['missing.cif']), 0)
        self.assertIn('Error: Cannot load initial structure', log.getvalue())
        self.assertEqual(run_main_menu(stdin=TTY(''), stdout=TTY(), plain=True), 0)
