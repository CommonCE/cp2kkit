"""Synthetic keyword/round-trip tests only; U values and moments are not recommendations."""
import io
import json
import shlex
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import main, build_parser
from cp2kkit.errors import KitError
from cp2kkit.input_editor import FIELD_IDS
from cp2kkit.input_tui import run_interactive, command_arguments
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.spin_settings import parse_dft_plus_u, parse_magnetism, format_dft_plus_u, format_magnetism
from cp2kkit.structure import read_structure, read_restart
from tests.test_input_tui import TTY
from tests.synthetic_cp2k_data import basis_entry, potential_entry


class HubbardMagnetismTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.dir/'fe2o2.xyz'
        self.source.write_text('4\nsynthetic\nFe 0 0 0\nFe 2 0 0\nO 0 2 0\nO 2 2 0\n')
        self.structure = read_structure(self.source)
        self.settings = InputSettings(periodic='NONE')
        self.out = self.dir/'new.inp'

    def generate(self, **kwargs):
        return generate_input(self.structure, replace(self.settings, **kwargs))

    def session(self, lines, **kwargs):
        log = TTY()
        code = run_interactive(str(self.source), -1, str(self.out), replace(self.settings, **kwargs),
                               stdin=TTY(lines), stdout=log, plain=True)
        return code, log.getvalue()

    def test_slot_replacement_and_cli_only_legacy_controls(self):
        self.assertEqual(dict(FIELD_IDS)[124], 'dft_plus_u')
        self.assertEqual(dict(FIELD_IDS)[125], 'magnetism')
        _, log = self.session('-10\n')
        self.assertIn('124. DFT+U [eV]: off', log)
        self.assertIn('125. Magnetic initialization: auto', log)
        self.assertNotIn('Cell override A B C', log)
        self.assertNotIn('CP2K data directory:', log)
        args = build_parser().parse_args(['generate-input', '--cell', '10', '11', '12', '--data-dir', 'data'])
        self.assertEqual(args.cell, [10., 11., 12.])
        self.assertEqual(args.data_dir, 'data')

    def test_parser_roundtrip_and_explicit_zero(self):
        for raw in ('Fe:2:4.25', 'Fe:2:0; O:1:3', 'off'):
            value = parse_dft_plus_u(raw)
            self.assertEqual(parse_dft_plus_u(format_dft_plus_u(value)), value)
        for raw in ('uks', 'auto', 'Fe=4; @2=-4; O=0', '@1=0'):
            value = parse_magnetism(raw)
            self.assertEqual(parse_magnetism(format_magnetism(value)), value)
        self.assertEqual(parse_magnetism('@1=0'), (('@1', 0.),))

    def test_invalid_lexical_input(self):
        for raw in ('Fe:2:nan', 'Fe:2:inf', 'Fe:2:-1', 'Fe:4:4', 'Fe:2.0:4',
                    'Fe:2:4; Fe:1:3', 'Fe:2', 'Fe\n&END:2:4', 'fe:2:4', ''):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_dft_plus_u(raw)
        for raw in ('Fe=nan', '@0=4', '@-1=4', '@1.5=4', 'Fe=1; Fe=2', 'Fe=inf', 'Fe_m1=4', ''):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_magnetism(raw)

    def test_hubbard_keyword_nesting_method_units_and_no_inferred_spin(self):
        text, manifest = self.generate(dft_plus_u=(('Fe', 2, 4.25),))
        self.assertIn('    PLUS_U_METHOD MULLIKEN\n', text)
        self.assertLess(text.index('PLUS_U_METHOD'), text.index('&QS'))
        self.assertIn('&KIND Fe\n', text)
        self.assertIn('      &DFT_PLUS_U ON\n        L 2\n        U_MINUS_J [eV] 4.25\n      &END DFT_PLUS_U', text)
        self.assertEqual(text.count('&DFT_PLUS_U ON'), 1)
        self.assertIn('UKS F', text)
        self.assertEqual(manifest['kinds']['Fe']['dft_plus_u']['unit'], 'eV')
        self.assertFalse(manifest['electronic_extensions']['runtime_validated'])
        text, _ = self.generate(dft_plus_u=(('Fe', 2, 4.), ('O', 1, 0.)))
        self.assertEqual(text.count('&DFT_PLUS_U ON'), 2)
        self.assertIn('U_MINUS_J [eV] 0\n', text)

    def test_afm_split_same_element_and_inherit_hubbard_for_both_kinds(self):
        settings = replace(self.settings, dft_plus_u=(('Fe', 2, 4.),),
                           magnetism=parse_magnetism('Fe=4; @2=-4; O=0'))
        before = self.source.read_bytes()
        text, manifest = generate_input(self.structure, settings)
        self.assertIn('MULTIPLICITY 1\n    UKS T', text)
        self.assertIn('&KIND Fe_m1', text)
        self.assertIn('&KIND Fe_m2', text)
        self.assertIn('MAGNETIZATION 4\n', text)
        self.assertIn('MAGNETIZATION -4\n', text)
        self.assertEqual(text.count('&DFT_PLUS_U ON'), 2)
        self.assertEqual(manifest['electronic_extensions']['atom_kinds'], ['Fe_m1', 'Fe_m2', 'O_m1', 'O_m1'])
        self.assertEqual(manifest['settings']['charge'], 0)
        self.assertEqual(manifest['settings']['multiplicity'], 1)
        output, sidecar, _ = write_input(self.structure, settings, self.out)
        parsed = read_restart(output)
        self.assertEqual(parsed.symbols, self.structure.symbols)
        self.assertEqual(parsed.positions, manifest['generated_structure']['positions'])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(json.loads(sidecar.read_text())['electronic_extensions']['atom_index_base'], 1)
        self.assertEqual((text, manifest), generate_input(self.structure, settings))

    def test_atom_override_zero_and_unassigned_kinds(self):
        _, manifest = self.generate(magnetism=parse_magnetism('@1=0; @2=-3'))
        self.assertEqual(manifest['electronic_extensions']['atom_kinds'], ['Fe_m1', 'Fe_m2', 'O', 'O'])
        self.assertEqual(manifest['kinds']['Fe_m1']['initial_magnetization'], 0.)
        self.assertIsNone(manifest['kinds']['O']['initial_magnetization'])
        self.assertTrue(any('MULTIPLICITY-1' in warning for warning in manifest['warnings']))

    def test_uks_singlet_density_and_two_spin_empty_orbitals(self):
        text, manifest = self.generate(magnetism=(), spin_density=True, scf='diag', smearing=300)
        self.assertIn('MULTIPLICITY 1\n    UKS T', text)
        self.assertIn('ADDED_MOS 30 30', text)
        self.assertTrue(manifest['density_output']['spin_density'])
        self.assertNotIn('MAGNETIZATION', text)

    def test_auto_and_off_do_not_force_nonmagnetic_high_spin(self):
        for raw in ('auto', 'off'):
            text, _ = self.generate(magnetism=parse_magnetism(raw), multiplicity=3)
            self.assertIn('UKS T', text)
            self.assertNotIn('MAGNETIZATION', text)
        text, manifest = self.generate()
        self.assertNotIn('DFT_PLUS_U', text)
        self.assertNotIn('MAGNETIZATION', text)
        self.assertIn('UKS F', text)
        self.assertNotIn('electronic_extensions', manifest)

    def test_invalid_api_requests_and_missing_atoms(self):
        cases = [dict(dft_plus_u=(('Co', 2, 4.),)), dict(dft_plus_u=(('Fe', True, 4.),)),
                 dict(dft_plus_u=({'element': 'Fe', 'L': 2, 'U': 4},)),
                 dict(dft_plus_u=(('Fe', 2, -1.),)), dict(dft_plus_u='Fe:2:4'),
                 dict(magnetism=(('@5', 4.),)), dict(magnetism=(('Co', 4.),)),
                 dict(magnetism=(('@1', 99.),)), dict(magnetism=(('Fe', float('nan')),)),
                 dict(magnetism=(('Fe', True),)), dict(magnetism='uks'),
                 dict(magnetism=({'selector': 'Fe', 'moment': 4},))]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(KitError):
                self.generate(**kwargs)

    def test_charge_spin_and_version_conflicts_never_auto_repaired(self):
        for kwargs in (dict(magnetism=(), charge=1), dict(magnetism=(), multiplicity=2),
                       dict(magnetism=(), cp2k_version='2024.1'),
                       dict(dft_plus_u=(('Fe', 2, 4.),), cp2k_version='2025.2')):
            with self.subTest(kwargs=kwargs), self.assertRaises(KitError):
                self.generate(**kwargs)

    def test_data_directory_checks_elements_not_generated_labels(self):
        (self.dir/'BASIS_MOLOPT').write_text(basis_entry('Fe', 'DZVP-MOLOPT-SR-GTH-q16') + basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6'))
        (self.dir/'GTH_POTENTIALS').write_text(potential_entry('Fe', 16, 'GTH-PBE-q16') + potential_entry('O', 6, 'GTH-PBE-q6'))
        _, manifest = self.generate(data_dir=str(self.dir), magnetism=parse_magnetism('@1=4; @2=-4'))
        self.assertIn('basis', manifest['data_sources'])
        self.assertEqual(manifest['kinds']['Fe_m1']['element'], 'Fe')

    def test_replay_and_cli_seed_equivalence(self):
        settings = replace(self.settings, dft_plus_u=parse_dft_plus_u('Fe:2:4'),
                           magnetism=parse_magnetism('Fe=4; @2=-4'))
        argv = command_arguments(self.source, -1, self.out, settings)
        self.assertEqual(shlex.split(shlex.join(argv)), argv)
        args = build_parser().parse_args(argv[3:])
        self.assertEqual(args.dft_plus_u, settings.dft_plus_u)
        self.assertEqual(args.magnetism, settings.magnetism)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(argv[3:]), 0)
        self.assertEqual(self.out.read_text(), generate_input(self.structure, settings)[0])
        argv = command_arguments(self.source, -1, self.out, replace(settings, magnetism=()))
        self.assertEqual(build_parser().parse_args(argv[3:]).magnetism, ())
        # Canonical ordering also makes JSON-shaped API requests replay identically.
        api = replace(settings, dft_plus_u=[['O', 1, 3.], ['Fe', 2, 4.]],
                      magnetism=[['Fe', 4.], ['@2', -4.]])
        parsed = build_parser().parse_args(command_arguments(self.source, -1, self.out, api)[3:])
        replay = replace(api, dft_plus_u=parsed.dft_plus_u, magnetism=parsed.magnetism)
        self.assertEqual(generate_input(self.structure, api), generate_input(self.structure, replay))

    def test_interactive_edit_retry_review_and_write(self):
        _, log = self.session('124\nFe:2:nan\nFe:2:4\n125\nFe=4; @2=-4\n0\ny\n\n')
        self.assertIn('Invalid input:', log)
        self.assertIn('@2: Fe', log)
        self.assertIn('Initial MAGNETIZATION: -4', log)
        self.assertIn('DFT+U [eV]: Fe:2:4', log)
        self.assertIn('UKS: True', log)
        settings = replace(self.settings, dft_plus_u=(('Fe', 2, 4.),),
                           magnetism=parse_magnetism('Fe=4; @2=-4'))
        self.assertEqual(self.out.read_text(), generate_input(self.structure, settings)[0])

    def test_clear_and_cancel_never_write(self):
        _, log = self.session('124\noff\n125\nauto\np\n\n-10\n',
                              dft_plus_u=(('Fe', 2, 4.),), magnetism=())
        preview = log.split('--- Input preview (not written) ---')[1]
        self.assertNotIn('&DFT_PLUS_U', preview)
        self.assertIn('UKS F', preview)
        self.assertFalse(self.out.exists())
        with patch('cp2kkit.input_editor.write_input') as writer:
            self.session('125\nFe=4; @2=-4\ncancel\n')
            writer.assert_not_called()

    def test_magnetic_output_collisions_are_protected(self):
        for target in (self.out, Path(str(self.out)+'.json')):
            target.write_text('existing')
            with self.assertRaises(KitError):
                write_input(self.structure, replace(self.settings, magnetism=()), self.out)
            self.assertEqual(target.read_text(), 'existing')
            target.unlink()
