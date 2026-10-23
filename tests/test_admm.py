"""Invented Gaussian/potential fixtures only; never execute CP2K or Multiwfn."""
import hashlib
import io
import json
import os
from dataclasses import asdict, replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cp2kkit.auxiliary_basis import (AUXILIARY_OPTIONS, auxiliary_option,
                                    numbered_auxiliary_basis, parse_auxiliary_basis)
from cp2kkit.basis_registry import OPTIONS, basis_option, validate_registry
from cp2kkit.basis_ui import edit_auxiliary_basis
from cp2kkit.cli import build_parser
from cp2kkit.cp2k_data import Libraries, read_library
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_editor import FIELDS, applicable_entries
from cp2kkit.input_tui import Menu, command_arguments, parse_value, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_input_tui import TTY


class ADMMTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-admm-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\ninvented fixture\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.water = read_structure(self.source)
        self.data = self.root/'synthetic data'
        self.data.mkdir()
        self.orb = self.data/'BASIS_MOLOPT'
        self.orb.write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6')+
                            basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1'))
        (self.data/'GTH_POTENTIALS').write_text(potential_entry('O', 6, 'GTH-PBE-q6')+
                                              potential_entry('H', 1, 'GTH-PBE-q1'))
        self.aux = self.data/'BASIS_ADMM_UZH'
        self.aux.write_text(''.join(basis_entry(el, f'{o.family}-q{q}')
                                   for o in AUXILIARY_OPTIONS for el, q in (('H', 1), ('O', 6))))
        # A byte fixture, NOT a genuine truncation table or native runtime check.
        (self.data/'t_c_g.dat').write_text('invented table bytes\n')
        self.settings = InputSettings(functional='PBE0', periodic='NONE', admm=True, data_dir=str(self.data))
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, **changes):
        return generate_input(self.water, replace(self.settings, **changes))

    def test_registry_numbers_roles_and_semantic_ids(self):
        self.assertEqual([(o.number, o.id) for o in AUXILIARY_OPTIONS],
                         [(200, 'admm-dz'), (201, 'admm-dzp'), (202, 'admm-tzp'), (203, 'admm-tz2p')])
        validate_registry((*OPTIONS, *AUXILIARY_OPTIONS))
        for option in AUXILIARY_OPTIONS:
            self.assertEqual(option.role.value, 'AUX_FIT')
            self.assertEqual(numbered_auxiliary_basis(option.number), option.id)
            self.assertEqual(parse_auxiliary_basis(option.id.upper()), option.id)
            self.assertEqual(parse_value(FIELDS['aux_basis'], str(option.number)), option.id)
            with self.assertRaises(KitError):
                basis_option(option.id)
        for bad in ('molopt-sr-dzvp', 'RI_AUX', 'admm-dzp-q6', '201', 201, None, 'bad\n&END'):
            with self.subTest(bad=bad), self.assertRaises(KitError):
                auxiliary_option(bad)
        for number in (0, 1, 122, 204, 900):
            with self.assertRaises(ValueError):
                numbered_auxiliary_basis(number)

    def test_default_off_is_unchanged_direct_hfx(self):
        text, manifest = self.generate(admm=False)
        self.assertNotIn('&AUXILIARY_DENSITY_MATRIX_METHOD', text)
        self.assertNotIn('AUX_FIT', text)
        self.assertNotIn('admm', manifest['method_profile'])
        self.assertFalse(manifest['method_profile']['hfx']['admm'])
        self.assertTrue(all('aux_fit' not in kind for kind in manifest['kinds'].values()))
        self.assertNotIn(str(self.aux), manifest['emitted_data_files']['basis'])

    def test_profiles_tasks_solvers_boundaries_and_auxiliary_sizes(self):
        for functional in ('PBE0', 'HSE06'):
            for run_type in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                for scf in ('ot', 'diag'):
                    for periodic in ('NONE', 'XYZ'):
                        for option in AUXILIARY_OPTIONS:
                            with self.subTest(f=functional, task=run_type, scf=scf, pbc=periodic, aux=option.id):
                                text, m = self.generate(functional=functional, run_type=run_type, scf=scf,
                                                        periodic=periodic, cell=(16., 16., 16.), aux_basis=option.id)
                                a = m['method_profile']['admm']
                                self.assertEqual(a['purification'], 'MO_DIAG' if scf == 'ot' else 'NONE')
                                self.assertEqual(a['method'], 'BASIS_PROJECTION')
                                self.assertEqual(a['exchange_scaling_model'], 'NONE')
                                self.assertEqual(a['exchange_correction_functional'], 'DEFAULT')
                                self.assertIn('      EXCH_CORRECTION_FUNC DEFAULT', text)
                                self.assertEqual(text.count('&AUXILIARY_DENSITY_MATRIX_METHOD\n'), 1)
                                self.assertEqual(text.count('BASIS_SET AUX_FIT '), 2)
                                expected_files = sorted((self.orb.name, self.aux.name))
                                emitted_files = [line.strip().split(None, 1)[1] for line in text.splitlines()
                                                 if line.strip().startswith('BASIS_SET_FILE_NAME ')]
                                self.assertEqual(emitted_files, expected_files)
                                self.assertEqual(m['emitted_data_files']['basis'], expected_files)
                                self.assertIn(f'BASIS_SET AUX_FIT {option.id}-q6', text)
                                self.assertEqual(m['kinds']['O']['aux_fit']['basis_q'], 6)
                                self.assertEqual(m['kinds']['H']['aux_fit']['basis_q'], 1)
                                self.assertTrue(m['method_profile']['hfx']['admm'])
                                self.assertFalse(m['method_profile']['hfx']['ri_hfx'])
                                self.assertFalse(a['runtime_validated'])
                                self.assertFalse(m['runtime_validated'])
                                self.assertEqual(text.index('&AUXILIARY_DENSITY_MATRIX_METHOD') < text.index('    &XC'), True)

    def test_hfx_operator_parameters_unchanged_by_admm(self):
        for functional, periodic in (('PBE0', 'NONE'), ('PBE0', 'XYZ'), ('HSE06', 'NONE'), ('HSE06', 'XYZ')):
            with self.subTest(f=functional, pbc=periodic):
                _, base = self.generate(admm=False, functional=functional, periodic=periodic, cell=(14., 15., 16.))
                _, aux = self.generate(functional=functional, periodic=periodic, cell=(14., 15., 16.))
                expected = dict(base['method_profile']['hfx'], admm=True)
                self.assertEqual(aux['method_profile']['hfx'], expected)
                self.assertEqual(aux['method_profile']['xc_parameters'], base['method_profile']['xc_parameters'])

    def test_explicit_purification_and_solver_not_repaired(self):
        for scf, method in (('ot', 'MO_DIAG'), ('ot', 'NONE'), ('diag', 'NONE')):
            _, m = self.generate(scf=scf, admm_purification=method)
            self.assertEqual(m['settings']['scf'], scf)
            self.assertEqual(m['method_profile']['admm']['purification'], method)
            self.assertEqual(m['method_profile']['admm']['purification_selection'], 'explicit')
        with self.assertRaisesRegex(KitError, 'requires OT'):
            self.generate(scf='diag', admm_purification='MO_DIAG')

    def test_invalid_and_retained_controls_fail(self):
        cases = ({'admm': 1}, {'admm': 'yes'}, {'admm_purification': 'NONE_DM'},
                 {'admm_purification': 'MCWEENY'}, {'admm_purification': 'auto'},
                 {'aux_basis': 'molopt-sr-dzvp'}, {'aux_basis': 'RI_AUX'}, {'aux_basis': 201},
                 {'aux_basis_files': str(self.aux)}, {'aux_basis_files': (None,)},
                 {'admm': False, 'aux_basis': 'admm-dz'},
                 {'admm': False, 'admm_purification': 'NONE'},
                 {'admm': False, 'aux_basis_files': (str(self.aux),)})
        for case in cases:
            with self.subTest(case=case), self.assertRaises(KitError):
                self.generate(**case)

    def test_unsupported_combinations_fail_without_publication(self):
        cases = ({'functional': 'PBE'}, {'functional': 'B3LYP'}, {'functional': 'BHANDHLYP', 'libxc_available': True},
                 {'functional': 'M06-2X', 'libxc_available': True}, {'functional': 'PBEH', 'pbeh_fraction': .4},
                 {'cp2k_version': '2026.1'}, {'basis': 'uzh-pbe0-dzvp'}, {'basis': 'ae-pob-dzvp-rev2'},
                 {'basis': 'custom-orbital'}, {'periodic': 'XY'}, {'run_type': 'CELL_OPT', 'periodic': 'XYZ'},
                 {'kpoints': (2, 2, 2), 'periodic': 'XYZ'}, {'smearing': 300., 'scf': 'diag'},
                 {'dft_plus_u': (('O', 1, 2.),)}, {'method': 'GFN1-xTB'},
                 {'method': 'GFN0-xTB'}, {'method': 'GFN2-xTB', 'tblite_available': True})
        out = self.root/'invalid.inp'
        for case in cases:
            with self.subTest(case=case), self.assertRaises(KitError):
                write_input(self.water, replace(self.settings, **case), out)
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out)+'.json').exists())

    def test_explicit_uks_and_split_kinds_keep_aux_fit(self):
        text, m = self.generate(magnetism=(('H', .5), ('@2', -.5)))
        kinds = [kind for kind in m['kinds'].values() if kind.get('element') == 'H']
        self.assertEqual(len(kinds), 2)
        self.assertEqual(kinds[0]['aux_fit'], kinds[1]['aux_fit'])
        self.assertEqual(text.count('BASIS_SET AUX_FIT'), 3)
        self.assertIn('    UKS T', text)

    def test_q_mismatch_missing_element_unknown_q_and_damaged_payloads(self):
        for payload in (basis_entry('H', 'admm-dzp-q1'),
                        basis_entry('O', 'admm-dzp-q8')+basis_entry('H', 'admm-dzp-q1'),
                        basis_entry('O', 'admm-dzp')+basis_entry('H', 'admm-dzp-q1'),
                        'O admm-dzp-q6\n'+basis_entry('H', 'admm-dzp-q1'),
                        basis_entry('O', 'admm-dzp-q6', exponent=float('nan'))+basis_entry('H', 'admm-dzp-q1'),
                        'O admm-dzp-q6\n 1\n 1 0 0 2 1\n 1.0 1.0\n'+basis_entry('H', 'admm-dzp-q1')):
            with self.subTest(payload=payload):
                self.aux.write_text(payload)
                with self.assertRaises(KitError):
                    self.generate()

    def test_extra_auxiliary_coefficients_are_not_silently_discarded(self):
        # Invented reproduction of the descriptor/row-width mismatch seen in
        # the inspected local Ca DZ/DZP entries; no production coefficients.
        self.aux.write_text(basis_entry('O', 'admm-dzp-q6').replace('1.0 1.0', '1.0 1.0 1.0')+
                            basis_entry('H', 'admm-dzp-q1'))
        out = self.root/'extra-coefficients.inp'
        with self.assertRaisesRegex(KitError, 'expected 2 values, got 3'):
            write_input(self.water, self.settings, out)
        self.assertFalse(out.exists())

    def test_selected_only_payload_validation(self):
        with self.aux.open('a') as stream:
            stream.write('Na unrelated-role\n unsupported unused syntax\n')
        self.generate()

    def test_auxiliary_data_mandatory_and_orbital_files_checked(self):
        with self.assertRaisesRegex(KitError, 'actual AUX_FIT'):
            self.generate(data_dir=None)
        with self.assertRaisesRegex(KitError, 'checked orbital'):
            self.generate(data_dir=None, aux_basis_files=(str(self.aux),))
        self.aux.unlink()
        with self.assertRaisesRegex(KitError, 'Missing CP2K data'):
            self.generate()

    def test_explicit_sources_and_environment_root(self):
        _, explicit = self.generate(data_dir=None, basis_files=(str(self.orb),), aux_basis_files=(str(self.aux),))
        self.assertEqual(explicit['kinds']['O']['aux_fit']['basis_file'], str(self.aux.resolve()))
        with patch.dict(os.environ, CP2K_DATA_DIR=str(self.data)):
            _, m = self.generate(data_dir=None)
        self.assertEqual(m['kinds']['O']['aux_fit'], explicit['kinds']['O']['aux_fit'])

    def test_emitted_auxiliary_file_survives_orbital_alias_handling(self):
        for sources in ({}, {'data_dir': None},
                        {'aux_basis_files': (str(self.aux),)},
                        {'basis_files': (str(self.orb),)},
                        {'basis_files': (str(self.orb),), 'aux_basis_files': (str(self.aux),)}):
            with self.subTest(sources=sources), patch.dict(os.environ, CP2K_DATA_DIR=str(self.data)):
                text, manifest = self.generate(**sources)
                emitted = [line.strip().split(None, 1)[1] for line in text.splitlines()
                           if line.strip().startswith('BASIS_SET_FILE_NAME ')]
                expected_orb = str(self.orb.resolve()) if sources.get('basis_files') else self.orb.name
                expected_aux = str(self.aux.resolve()) if sources.get('aux_basis_files') else self.aux.name
                self.assertEqual(emitted, sorted((expected_orb, expected_aux)))
                self.assertEqual(manifest['emitted_data_files']['basis'], emitted)
                runtime_files = [str(self.data/file) if not Path(file).is_absolute() else file for file in emitted]
                for element, q in (('O', 6), ('H', 1)):
                    alias = manifest['kinds'][element]['aux_fit']['basis']
                    entry, name, actual_q = Libraries().select(runtime_files, 'AUX_FIT', element, (alias,), q)
                    self.assertEqual((name, actual_q, entry.validate()), (alias, q, q))

    def test_duplicate_auxiliary_aliases_are_checked(self):
        extra = self.data/'extra'
        extra.write_text(basis_entry('O', 'admm-dzp-q6', exponent=2.)+basis_entry('H', 'admm-dzp-q1'))
        with self.assertRaisesRegex(KitError, 'duplicate|Conflicting|Ambiguous'):
            self.generate(aux_basis_files=(str(self.aux), str(extra)))
        extra.write_bytes(self.aux.read_bytes())
        _, m = self.generate(aux_basis_files=(str(self.aux), str(extra)))
        self.assertEqual(m['kinds']['O']['aux_fit']['basis_file'], str(self.aux.resolve()))

    def test_cross_role_final_emitted_union_shadowing(self):
        original = self.orb.read_text()
        self.orb.write_text(original+basis_entry('O', 'admm-dzp-q6', exponent=2.))
        with self.assertRaisesRegex(KitError, 'duplicate|Conflicting|Ambiguous'):
            self.generate()
        self.orb.write_text(original)
        with self.aux.open('a') as stream:
            stream.write(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6', exponent=2.))
        with self.assertRaisesRegex(KitError, 'duplicate|Conflicting|Ambiguous'):
            self.generate()

    def test_single_union_file_deduplicated_and_hashed(self):
        self.orb.write_text(self.orb.read_text()+self.aux.read_text())
        text, m = self.generate(aux_basis_files=(str(self.orb),))
        self.assertEqual(text.count('BASIS_SET_FILE_NAME '), 1)
        self.assertIn('BASIS_SET_FILE_NAME '+str(self.orb.resolve())+'\n', text)
        self.assertEqual(m['emitted_data_files']['basis'], [str(self.orb.resolve())])
        self.assertEqual(m['method_profile']['basis_files'], [str(self.orb.resolve())])
        self.assertEqual(m['kinds']['O']['aux_fit']['basis_source']['sha256'], hashlib.sha256(self.orb.read_bytes()).hexdigest())

    def test_gaussian_aux_fit_role_is_not_potential_or_ri_parser(self):
        entries, _ = read_library(self.aux, 'AUX_FIT')
        self.assertTrue(all(entry.role == 'AUX_FIT' for entry in entries))
        entry, name, q = Libraries().select((str(self.aux),), 'AUX_FIT', 'O', ('admm-dzp-q6',), 6)
        self.assertEqual((name, q), ('admm-dzp-q6', 6))
        self.assertEqual(entry.validate(), 6)
        with self.assertRaises(KitError):
            read_library(self.aux, 'RI_AUX')

    def test_provenance_determinism_and_config_replay(self):
        text, m = self.generate(aux_basis='admm-tzp', admm_purification='NONE')
        self.assertEqual((text, m), self.generate(aux_basis='admm-tzp', admm_purification='NONE'))
        source = m['kinds']['O']['aux_fit']['basis_source']
        self.assertEqual(source['path'], str(self.aux.resolve()))
        self.assertGreater(source['entry_line'], 0)
        self.assertEqual(len(source['entry_sha256']), 64)
        self.assertEqual(source['sha256'], hashlib.sha256(self.aux.read_bytes()).hexdigest())
        self.assertFalse(m['kinds']['O']['aux_fit']['physical_pairing_validated'])
        self.assertIn(str(self.aux.resolve()), {d['path'] for d in m['data_sources'].values()})
        restored = InputSettings.from_config(json.loads(json.dumps(m)))
        self.assertEqual(generate_input(self.water, restored), (text, m))
        self.assertEqual(InputSettings.from_config({}).admm, False)
        with self.assertRaises(KitError):
            InputSettings.from_config({'aux_basis': 201}, source_version='0.2.6')
        self.assertEqual(m['schema_version'], '0.1.0')

    def test_malformed_auxiliary_config_and_xtb_controls(self):
        for value in ('a', None, 201, {}):
            with self.subTest(value=value), self.assertRaises(KitError):
                InputSettings.from_config({'aux_basis_files': value})
        for changes in ({'admm': True}, {'admm': 0}, {'admm': False, 'aux_basis': 'admm-tzp'},
                        {'admm': False, 'admm_purification': 'NONE'},
                        {'admm': False, 'aux_basis_files': (str(self.aux),)}):
            settings = replace(InputSettings(method='GFN1-xTB', periodic='NONE'), **changes)
            with self.subTest(changes=changes), self.assertRaises(KitError):
                generate_input(self.water, settings)

    def test_density_bundle_rejects_auxiliary_or_admm_identity_drift(self):
        settings = replace(self.settings, density_difference=True, fragment_a_indices='1',
                           fragment_a_charge=0, fragment_a_multiplicity=1,
                           fragment_b_charge=0, fragment_b_multiplicity=1)
        original_generator = generate_input
        for field in ('aux_fit', 'admm'):
            def tampered(structure, settings, **kwargs):
                text, manifest = original_generator(structure, settings, **kwargs)
                if '_common_ngrids' in kwargs:
                    if field == 'aux_fit':
                        next(iter(manifest['kinds'].values()))['aux_fit']['basis'] = 'different-auxiliary'
                    else:
                        manifest['method_profile']['admm']['exchange_correction_functional'] = 'PBEX'
                return text, manifest
            with self.subTest(field=field), patch('cp2kkit.inputgen.generate_input', side_effect=tampered):
                with self.assertRaisesRegex(KitError, 'AUX_FIT|ADMM'):
                    original_generator(self.water, settings)

    def test_auxiliary_source_name_collisions_keep_both_sources_protected(self):
        files = []
        for element, q in (('H', 1), ('O', 6)):
            directory = self.root/element
            directory.mkdir()
            file = directory/'shared.inp'
            file.write_text(basis_entry(element, f'admm-dzp-q{q}'))
            files.append(str(file))
        settings = replace(self.settings, aux_basis_files=tuple(files))
        _, manifest = generate_input(self.water, settings)
        recorded = {s['path'] for s in manifest['data_sources'].values()}
        self.assertTrue(set(files) <= recorded)
        for file in files:
            before = Path(file).read_bytes()
            with self.assertRaises(KitError):
                write_input(self.water, settings, file)
            self.assertEqual(Path(file).read_bytes(), before)

    def test_cli_and_repeated_file_replay(self):
        settings = replace(self.settings, aux_basis='admm-tz2p', admm_purification='NONE', aux_basis_files=(str(self.aux),))
        args = command_arguments(self.source, 0, self.root/'replay.inp', settings)
        parsed = build_parser().parse_args(args[3:])
        restored = InputSettings.from_config({name: getattr(parsed, name) for name in InputSettings.__dataclass_fields__})
        self.assertEqual(generate_input(self.water, settings), generate_input(self.water, restored))
        self.assertIn('--aux-basis-file='+str(self.aux), args)
        extra = build_parser().parse_args(['generate-input', str(self.source), '--aux-basis-file', 'a', '--aux-basis-file', 'b'])
        self.assertEqual(extra.aux_basis_files, ['a', 'b'])

    def test_cli_subprocess_bounded_synthetic_generation(self):
        out = self.root/'cli.inp'
        command = [sys.executable, '-m', 'cp2kkit', 'generate-input', str(self.source), '--periodic', 'NONE',
                   '--functional', 'HSE06', '--admm', '--aux-basis', 'admm-tzp', '--data-dir', str(self.data),
                   '--write-json', '--output', str(out)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        m = json.loads(Path(str(out)+'.json').read_text())
        text = out.read_text()
        self.assertIn('BASIS_SET AUX_FIT admm-tzp-q6', text)
        self.assertIn('BASIS_SET_FILE_NAME '+self.aux.name+'\n', text)
        self.assertEqual(m['emitted_data_files']['basis'], sorted((self.orb.name, self.aux.name)))
        self.assertTrue(m['method_profile']['hfx']['admm'])
        self.assertFalse(m['runtime_validated'])

    def test_output_protects_auxiliary_sources_and_hardlinks(self):
        before = self.aux.read_bytes()
        for target in (self.aux, self.root/'hardlink.inp'):
            if target != self.aux:
                os.link(self.aux, target)
            with self.assertRaises(KitError):
                write_input(self.water, self.settings, target)
            self.assertEqual(self.aux.read_bytes(), before)
        link = self.root/'symlink.inp'
        link.symlink_to(self.aux)
        with self.assertRaises(OutputExists):
            write_input(self.water, self.settings, link)
        self.assertEqual(self.aux.read_bytes(), before)

    def test_ordinary_overwrite_and_exclusive_sidecar_preserved(self):
        out = self.root/'ordinary.inp'
        out.write_text('old input\n')
        write_input(self.water, self.settings, out)
        self.assertIn('AUX_FIT', out.read_text())
        sidecar = Path(str(out)+'.json')
        sidecar.write_text('old provenance\n')
        before = out.read_bytes()
        with self.assertRaises(OutputExists):
            write_input(self.water, replace(self.settings, write_json=True), out)
        self.assertEqual(out.read_bytes(), before)
        self.assertEqual(sidecar.read_text(), 'old provenance\n')

    def test_auxiliary_path_validation(self):
        for filename in ('bad#file', 'bad!file', 'bad$VAR', 'bad\nfile'):
            path = self.root/filename
            path.write_bytes(self.aux.read_bytes())
            with self.subTest(filename=filename), self.assertRaises(KitError):
                self.generate(aux_basis_files=(str(path),))

    def test_density_bundle_keeps_auxiliary_and_admm_identity(self):
        settings = replace(self.settings, density_difference=True, fragment_a_indices='1',
                           fragment_a_charge=0, fragment_a_multiplicity=1,
                           fragment_b_charge=0, fragment_b_multiplicity=1)
        _, m = generate_input(self.water, settings)
        components = m['density_difference']['components']
        for component in components.values():
            self.assertEqual(component['method_profile']['admm'], m['method_profile']['admm'])
            for label, kind in component['kinds'].items():
                element = kind.get('element', label)
                self.assertEqual(kind['aux_fit'], m['kinds'][element]['aux_fit'])

    def test_menu_applicability_and_separate_auxiliary_numbers(self):
        values = dict(asdict(self.settings), path=str(self.source), frame=0, output=str(self.root/'menu.inp'))
        numbers = lambda: {e.number for e in applicable_entries(values)}
        self.assertTrue({122, 223} <= numbers())
        values['admm'] = False
        self.assertIn(122, numbers())
        self.assertNotIn(223, numbers())
        values.update(functional='B3LYP', admm=True)
        self.assertNotIn(122, numbers())
        self.assertNotIn(223, numbers())
        values.update(functional='PBE0', method='GFN1-xTB')
        self.assertNotIn(122, numbers())
        log = io.StringIO()
        chosen = edit_auxiliary_basis(Menu(TTY('1\n202\n'), log, plain=True), 'admm-dzp', values)
        self.assertEqual(chosen, 'admm-tzp')
        self.assertIn('Unallocated AUX_FIT number 1', log.getvalue())
        for raw in ('0\n', 'back\n', '\n'):
            self.assertEqual(edit_auxiliary_basis(Menu(TTY(raw), io.StringIO(), plain=True), 'admm-dzp'), 'admm-dzp')

    def test_menu_explicit_auxiliary_files_and_restore(self):
        values = dict(asdict(self.settings))
        lines = 'f\n'+json.dumps([str(self.aux)])+'\n201\n'
        chosen = edit_auxiliary_basis(Menu(TTY(lines), io.StringIO(), plain=True), 'admm-dz', values)
        self.assertEqual(chosen, 'admm-dzp')
        self.assertEqual(values['aux_basis_files'], (str(self.aux),))
        edit_auxiliary_basis(Menu(TTY('f\n[]\nback\n'), io.StringIO(), plain=True), chosen, values)
        self.assertEqual(values['aux_basis_files'], ())

    def test_tui_enable_auxiliary_select_and_write(self):
        out = self.root/'interactive.inp'
        log = TTY()
        settings = replace(self.settings, admm=False)
        code = run_interactive(str(self.source), -1, settings=settings, output=str(out),
                               stdin=TTY('122\ny\nauto\n223\n202\nr\n\n0\n'), stdout=log, plain=True)
        self.assertEqual(code, 0, log.getvalue())
        self.assertIn('BASIS_SET AUX_FIT admm-tzp-q6', out.read_text())
        self.assertIn('ADMM:', log.getvalue())


if __name__ == '__main__':
    unittest.main()
