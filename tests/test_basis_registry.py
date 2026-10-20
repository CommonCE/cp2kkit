"""Invented libraries only: no native CP2K execution or scientific results."""
import hashlib
import io
import json
import os
import re
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cp2kkit.basis_registry import (BY_ID, BY_NUMBER, OPTIONS, RESERVED_RANGES, BasisRole,
                                   basis_option, migrate_basis, numbered_basis, validate_registry)
from cp2kkit.basis_ui import edit_basis
from cp2kkit.cli import build_parser, main
from cp2kkit.cp2k_data import Libraries, read_library
from cp2kkit.errors import AmbiguousProject, KitError, OutputExists, ParseError
from cp2kkit.input_tui import Menu, command_arguments, parse_value, GROUPS
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.structure import Structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_input_tui import TTY


class BasisRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)
        self.atom = Structure(['O'], [[0., 0., 0.]], None, None, {'path': 'synthetic.xyz'})
        self.settings = InputSettings(periodic='NONE', write_json=True)

    def file(self, name, text):
        path = self.root/name
        path.write_text(text)
        return str(path)

    def generate(self, **changes):
        return generate_input(self.atom, replace(self.settings, **changes))

    def menu(self, text, current='molopt-sr-dzvp', values=None):
        log = io.StringIO()
        value = edit_basis(Menu(TTY(text), log, plain=True), current, values)
        return value, log.getvalue()

    def uzh(self, family='TZVP', element='O', q=6):
        b = self.file('BASIS_MOLOPT_UZH_2026.2', basis_entry(element, f'{family}-MOLOPT-PBE-GTH-q{q}', f'{family}-MOLOPT-GGA-GTH-q{q}'))
        p = self.file('POTENTIAL_UZH_2026.2', potential_entry(element, q, f'GTH-PBE-q{q}', f'GTH-GGA-q{q}'))
        return b, p

    def test_allocated_number_id_contract_is_explicit(self):
        expected = {1:'molopt-sr-szv', 2:'molopt-sr-dzvp', 3:'molopt-tzvp', 4:'molopt-tzv2p',
                    5:'molopt-tzv2px', 6:'molopt-szv', 7:'molopt-dzvp', 8:'molopt-sr-tzvp',
                    9:'molopt-sr-tzv2p', 20:'uzh-pbe-dzvp', 21:'uzh-pbe-tzvp', 22:'uzh-pbe-tzv2p',
                    30:'uzh-pbe0-dzvp', 31:'uzh-pbe0-tzvp', 32:'uzh-pbe0-tzv2p', 900:'custom-orbital'}
        expected.update({50:'ae-6-31g-star',51:'ae-6-311g-starstar',52:'ae-def2-tzvp',53:'ae-def2-qzvp',
                         54:'ae-pob-tzvp',55:'ae-pob-dzvp-rev2',56:'ae-pob-tzvp-rev2',
                         57:'ae-uzh-svp',58:'ae-uzh-tzvpp',59:'ae-uzh-qzvpp'})
        self.assertEqual({o.number:o.id for o in OPTIONS}, expected)
        self.assertEqual([BY_NUMBER[n].name for n in range(1, 6)],
                         ['SZV-MOLOPT-SR-GTH', 'DZVP-MOLOPT-SR-GTH', 'TZVP-MOLOPT-GTH',
                          'TZV2P-MOLOPT-GTH', 'TZV2PX-MOLOPT-GTH'])
        validate_registry()
        for bad in (OPTIONS+(OPTIONS[0],), (replace(OPTIONS[0], number=0),),
                    (replace(OPTIONS[0], number=10),)):
            with self.assertRaises(ValueError):
                validate_registry(bad)
        with self.assertRaises(TypeError):
            BY_NUMBER[1] = OPTIONS[1]

    def test_reserved_unavailable_and_unallocated_cannot_be_selected(self):
        for number in (0, 10, 19, 23, 29, 30, 31, 32, 33, 39, 40, 49, 60, 79, 80, 99, 100, 199, 200, 901):
            with self.subTest(number=number), self.assertRaises(ValueError):
                numbered_basis(number)
        with self.assertRaisesRegex(KitError, 'hybrid/HF/ADMM'):
            self.generate(basis='uzh-pbe0-tzvp')

    def test_roles_are_distinct_and_auxiliary_roles_are_not_orb(self):
        self.assertEqual({r.value for r in BasisRole}, {'ORB', 'AUX_FIT', 'RI_AUX'})
        self.assertTrue(all(o.role == BasisRole.ORB for o in OPTIONS if o.selectable))
        self.assertFalse(replace(OPTIONS[0], role=BasisRole.AUX_FIT).selectable)
        self.assertFalse(replace(OPTIONS[0], role=BasisRole.RI_AUX).selectable)
        with self.assertRaisesRegex(KitError, 'distinct'):
            read_library('not-read', 'RI_AUX')

    def test_sorting_filtering_and_names_do_not_change_numbers(self):
        for option in reversed(sorted(OPTIONS, key=lambda o:o.name)):
            if option.selectable:
                self.assertEqual(numbered_basis(option.number), option.id)
        value, log = self.menu('/UZH-PBE\n21\n')
        self.assertEqual(value, 'uzh-pbe-tzvp')
        self.assertIn('21. TZVP-MOLOPT-PBE-GTH', log)
        self.assertIn('UNAVAILABLE', log)
        self.assertEqual(self.menu('molopt-tzv2px\n')[0], 'molopt-tzv2px')
        self.assertEqual(self.menu('0\n')[0], self.settings.basis)
        self.assertEqual(self.menu('\n')[0], self.settings.basis)
        self.assertEqual(self.menu('30\n19\n22\n')[0], 'uzh-pbe-tzv2p')

    def test_legacy_names_and_versioned_numeric_migration(self):
        self.assertEqual(migrate_basis('DZVP-MOLOPT-GTH'), 'molopt-dzvp')
        self.assertEqual(migrate_basis(3, '0.2.6'), 'molopt-dzvp')
        self.assertEqual(migrate_basis('8', '0.2.6'), 'molopt-tzv2px')
        self.assertEqual(numbered_basis(3), 'molopt-tzvp')
        for value in (3, '3'):
            with self.assertRaises(KitError):
                migrate_basis(value)
            with self.assertRaises(KitError):
                basis_option(value)
        with self.assertRaises(KitError):
            migrate_basis(6, '0.2.5')
        old = InputSettings.from_config({'basis':3, 'periodic':'NONE'}, '0.2.6')
        self.assertEqual(old.basis, 'molopt-dzvp')

    def test_json_settings_and_sidecars_migrate_without_changing_physics(self):
        legacy = json.loads(json.dumps(asdict(replace(self.settings, basis='DZVP-MOLOPT-SR-GTH',
                                                    basis_overrides=(('O','TZVP-MOLOPT-GTH'),)))))
        loaded = InputSettings.from_config(legacy)
        self.assertEqual(loaded.basis, 'molopt-sr-dzvp')
        self.assertEqual(loaded.basis_overrides, (('O','molopt-tzvp'),))
        self.assertEqual(generate_input(self.atom, loaded)[0],
                         self.generate(basis_overrides=(('O','TZVP-MOLOPT-GTH'),))[0])
        _, manifest = self.generate()
        replay = InputSettings.from_config(json.loads(json.dumps(manifest)))
        self.assertEqual(generate_input(self.atom, replay)[0], manifest['input_text'])
        manifest['settings']['basis'] = 3
        with self.assertRaisesRegex(KitError,'explicit supported source_version'):
            InputSettings.from_config(manifest, source_version='0.2.6')

    def test_template_and_data_checked_status_are_distinct(self):
        text, manifest = self.generate()
        self.assertEqual(manifest['basis_validation']['status'], 'unverified_template')
        self.assertFalse(manifest['basis_validation']['runtime_validated'])
        self.assertFalse(manifest['basis_validation']['runnable_verified'])
        self.assertTrue(any('UNVERIFIED TEMPLATE' in w for w in manifest['warnings']))
        self.assertIn('BASIS_SET DZVP-MOLOPT-SR-GTH-q6', text)
        self.assertEqual(manifest['basis_selection']['number'], 2)
        self.assertEqual(manifest['settings']['basis'], 'molopt-sr-dzvp')

    def test_ucl_sr_actual_files_and_all_split_kinds(self):
        self.atom = Structure(['Fe','Fe'], [[0.,0.,0.],[2.,0.,0.]], None, None, {'path':'synthetic.xyz'})
        self.file('BASIS_MOLOPT_UCL', basis_entry('Fe', 'TZVP-MOLOPT-SR-GTH-q16'))
        self.file('GTH_POTENTIALS', potential_entry('Fe',16,'GTH-PBE-q16'))
        _, manifest = self.generate(basis='molopt-sr-tzvp', data_dir=str(self.root),
                                    magnetism=(('@1',4.),('@2',-4.)), dft_plus_u=(('Fe',2,4.),))
        self.assertEqual(manifest['basis_validation']['status'], 'data_checked')
        for kind in manifest['kinds'].values():
            self.assertEqual(kind['basis_number'], 8)
            self.assertEqual(kind['basis_q'],16)
            self.assertEqual(kind['dft_plus_u']['U_minus_J'],4.)
            self.assertEqual(Path(kind['basis_file']).name,'BASIS_MOLOPT_UCL')

    def test_uzh_pbe_uses_real_q_names_and_paired_potentials(self):
        for family, identifier in (('DZVP','uzh-pbe-dzvp'), ('TZVP','uzh-pbe-tzvp'), ('TZV2P','uzh-pbe-tzv2p')):
            self.uzh(family)
            text, manifest = self.generate(basis=identifier, data_dir=str(self.root))
            self.assertEqual(manifest['basis_validation']['status'], 'data_checked')
            self.assertIn(f'BASIS_SET {family}-MOLOPT-PBE-GTH-q6',text)
            self.assertEqual(manifest['kinds']['O']['protocol_pairing'],'unverified_pair')
            self.assertEqual(Path(manifest['method_profile']['potential_file']).name,'POTENTIAL_UZH_2026.2')
            self.assertNotIn('GTH_POTENTIALS',text)
            self.assertIn('BASIS_SET_FILE_NAME BASIS_MOLOPT_UZH\n', text)
            self.assertIn('POTENTIAL_FILE_NAME POTENTIAL_UZH\n', text)
            self.assertNotIn('_UZH_2026', text)
            self.assertEqual(manifest['emitted_data_files']['basis'], ['BASIS_MOLOPT_UZH'])
            self.assertEqual(manifest['emitted_data_files']['potential'], 'POTENTIAL_UZH')
            self.assertEqual(text.count('POTENTIAL_FILE_NAME'),1)
            self.assertFalse(manifest['method_profile']['runtime_validated'])

    def test_uzh_runtime_aliases_without_data_and_explicit_sources_preserved(self):
        text, report = self.generate(basis='uzh-pbe-tzvp')
        self.assertIn('BASIS_SET_FILE_NAME BASIS_MOLOPT_UZH\n', text)
        self.assertIn('POTENTIAL_FILE_NAME POTENTIAL_UZH\n', text)
        b, p = map(Path, self.uzh())
        text, report = self.generate(basis='uzh-pbe-tzvp', basis_files=(str(b),), potential_files=(str(p),))
        self.assertIn(f'BASIS_SET_FILE_NAME {b.resolve()}\n', text)
        self.assertIn(f'POTENTIAL_FILE_NAME {p.resolve()}\n', text)
        self.assertEqual(report['emitted_data_files']['basis'], [str(b.resolve())])
        self.assertEqual(report['emitted_data_files']['potential'], str(p.resolve()))

    def test_uzh_pbe_rejects_wrong_functionals_and_targets(self):
        for kwargs in ({'functional':'BLYP'}, {'functional':'RPBE', 'libxc_available':True, 'allow_pbe_potential':True},
                       {'cp2k_version':'2025.2'}):
            with self.assertRaises(KitError):
                self.generate(basis='uzh-pbe-tzvp', **kwargs)

    def test_header_aliases_are_used_only_when_they_actually_exist(self):
        self.uzh()
        self.file('BASIS_MOLOPT_UZH_2026.2',basis_entry('O','TZVP-MOLOPT-GGA-GTH-q6'))
        text, manifest = self.generate(basis='uzh-pbe-tzvp',data_dir=str(self.root))
        self.assertIn('BASIS_SET TZVP-MOLOPT-GGA-GTH-q6',text)
        self.assertNotIn('BASIS_SET TZVP-MOLOPT-PBE-GTH-q6',text)
        self.assertEqual(manifest['kinds']['O']['basis_q'],6)

    def test_missing_fixed_q_has_no_small_core_or_family_fallback(self):
        self.atom = Structure(['Mg'], [[0.,0.,0.]], None, None, {'path':'synthetic.xyz'})
        self.file('BASIS_MOLOPT_UCL',basis_entry('Mg','TZVP-MOLOPT-SR-GTH-q2'))
        self.file('GTH_POTENTIALS',potential_entry('Mg',10,'GTH-PBE-q10'))
        with self.assertRaisesRegex(KitError,'required q10.*observed q=q2'):
            self.generate(basis='molopt-sr-tzvp',data_dir=str(self.root))
        self.assertEqual(self.settings.charge,0)

    def test_all_missing_elements_and_catalog_alternatives_are_listed(self):
        self.atom = Structure(['O','N'], [[0.,0.,0.],[0.,0.,2.]], None, None, {'path':'synthetic.xyz'})
        with self.assertRaises(KitError) as error:
            self.generate(basis='molopt-sr-tzvp',multiplicity=2)
        for expected in ('element O q6', 'element N q5', 'Catalog alternatives', '2:molopt-sr-dzvp', 'No basis or valence fallback'):
            self.assertIn(expected,str(error.exception))

    def test_duplicate_alias_different_content_needs_explicit_disambiguation(self):
        a = self.file('a',basis_entry('O','DZVP-MOLOPT-SR-GTH-q6',exponent=1.))
        b = self.file('b',basis_entry('O','DZVP-MOLOPT-SR-GTH-q6',exponent=2.))
        for files in ((a,b),(b,a)):
            with self.assertRaises(AmbiguousProject) as error:
                self.generate(basis_files=files)
            self.assertIn(a,str(error.exception))
            self.assertIn(b,str(error.exception))
        text, _ = self.generate(basis_files=(b,))
        self.assertIn(b,text)
        self.assertNotIn('"'+a+'"',text)

    def test_identical_entries_and_symlinks_deduplicate_sources(self):
        real = self.file('real',basis_entry('O','DZVP-MOLOPT-SR-GTH-q6'))
        link = self.root/'link'
        link.symlink_to(real)
        text, manifest = self.generate(basis_files=(str(link),real))
        self.assertEqual(text.count('BASIS_SET_FILE_NAME'),1)
        source = manifest['kinds']['O']['basis_source']
        self.assertEqual(source['path'],real)
        self.assertEqual(source['requested_paths'], sorted((str(link),real)))
        self.assertEqual(source['sha256'],hashlib.sha256(Path(real).read_bytes()).hexdigest())

    def test_potential_duplicate_aliases_are_not_selected_by_file_order(self):
        a = self.file('p1',potential_entry('O',6,'GTH-PBE-q6'))
        b = self.file('p2',potential_entry('O',6,'GTH-PBE-q6').replace('-1.0','-2.0'))
        with self.assertRaises(AmbiguousProject):
            self.generate(potential_files=(a,b))

    def test_actual_files_not_catalogs_are_authoritative(self):
        # Non-SR TZVP Fe is absent from the pinned catalog, but explicitly supplied
        # invented data can be parsed. This is not a basis-quality endorsement.
        self.atom = Structure(['Fe'], [[0.,0.,0.]], None, None, {'path':'synthetic.xyz'})
        b = self.file('new-library',basis_entry('Fe','TZVP-MOLOPT-GTH-q16'))
        text, manifest = self.generate(basis='molopt-tzvp',basis_files=(b,))
        self.assertIn('BASIS_SET TZVP-MOLOPT-GTH-q16',text)
        self.assertEqual(manifest['kinds']['Fe']['basis_source']['data_version'],None)

    def test_directory_priority_environment_and_explicit_files(self):
        self.uzh()
        with patch.dict(os.environ, {'CP2K_DATA_DIR':str(self.root)}):
            _, manifest = self.generate(basis='uzh-pbe-tzvp')
            self.assertEqual(manifest['basis_validation']['status'],'data_checked')
            with self.assertRaisesRegex(KitError,'not a directory'):
                self.generate(data_dir=str(self.root/'missing'))
        b = self.file('chosen',basis_entry('O','DZVP-MOLOPT-SR-GTH-q6'))
        self.generate(basis_files=(b,))
        p = self.file('chosen-pot',potential_entry('O',6,'GTH-PBE-q6'))
        with patch.dict(os.environ, {'CP2K_DATA_DIR':str(self.root/'stale-environment-path')}):
            _, explicit = self.generate(basis_files=(b,),potential_files=(p,))
            self.assertEqual(explicit['basis_validation']['status'],'data_checked')
        with self.assertRaisesRegex(KitError,'not a file'):
            self.generate(basis_files=(str(self.root/'missing'),))

    def test_file_names_do_not_prove_data_versions(self):
        self.uzh()
        _, manifest = self.generate(basis='uzh-pbe-tzvp', data_dir=str(self.root))
        for key in ('basis_source','potential_source'):
            self.assertIsNone(manifest['kinds']['O'][key]['data_version'])
        _, partial = self.generate(basis='uzh-pbe-tzvp',basis_files=(str(self.root/'BASIS_MOLOPT_UZH_2026.2'),))
        self.assertEqual(partial['kinds']['O']['protocol_pairing'],'unverified_pair')
        self.assertEqual(partial['basis_validation']['status'],'unverified_template')

    def test_custom_real_alias_file_and_potential_q_validation(self):
        b = self.file('custom orbital',basis_entry('O','REAL-ORB-q6','my-orbital'))
        p = self.file('custom potential',potential_entry('O',6,'REAL-POT-q6','my-potential'))
        text, manifest = self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name='my-orbital',
                                       custom_potential_file=p,custom_potential_name='my-potential')
        self.assertIn('BASIS_SET my-orbital',text)
        self.assertIn('POTENTIAL my-potential',text)
        kind = manifest['kinds']['O']
        self.assertEqual(kind['basis_number'],900)
        self.assertEqual(kind['basis_q'],6)
        self.assertEqual(kind['data_validation'],'data_checked')
        self.assertEqual(kind['protocol_pairing'],'custom_user_asserted')
        with self.assertRaisesRegex(KitError,'No matching ORB'):
            self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name='imaginary-q6')
        self.file('custom potential',potential_entry('O',2,'my-potential'))
        with self.assertRaisesRegex(KitError,'required q6.*q2'):
            self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name='my-orbital',
                          custom_potential_file=p,custom_potential_name='my-potential')

    def test_unknown_custom_basis_q_is_not_guessed(self):
        b = self.file('orb',basis_entry('O','unknown-valence'))
        p = self.file('pot',potential_entry('O',6,'GTH-PBE'))
        _, manifest = self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name='unknown-valence',potential_files=(p,))
        self.assertIsNone(manifest['kinds']['O']['basis_q'])
        self.assertEqual(manifest['basis_validation']['status'],'unverified_template')
        self.assertTrue(any('UNKNOWN' in w for w in manifest['warnings']))

    def test_custom_rejects_auxiliary_all_electron_and_injection(self):
        b = self.file('orb',basis_entry('O','basis-q6'))
        for name in ('AUX_FIT-q6','RI_AUX-q6','basis-ae-q6','bad\n&END','bad$VAR'):
            with self.subTest(name=name), self.assertRaises(KitError):
                self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name=name)
        p = self.file('all',potential_entry('O',6,'ALL'))
        with self.assertRaisesRegex(ParseError,'all-electron'):
            self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name='basis-q6',
                          custom_potential_file=p,custom_potential_name='ALL')

    def test_custom_menu_records_real_names_transactionally(self):
        b = self.file('orbital file',basis_entry('O','real-q6'))
        p = self.file('potential file',potential_entry('O',6,'real-pot'))
        values = asdict(self.settings)
        value, _ = self.menu(f'900\n{b}\nreal-q6\n{p}\nreal-pot\n',values=values)
        self.assertEqual(value,'custom-orbital')
        self.assertEqual(values['custom_basis_name'],'real-q6')
        before = dict(values)
        value, _ = self.menu(f'900\n{b}\nback\n',values=values)
        self.assertEqual(value,self.settings.basis)
        self.assertEqual(values,before)

    def test_data_controls_preserve_settings_and_return_does_not_select_zero(self):
        values = asdict(self.settings)
        value, _ = self.menu(f'd\n{self.root}\nb\n{self.root}/basis\nv\n{self.root}/potential\n0\n',values=values)
        self.assertEqual(value,self.settings.basis)
        self.assertEqual(values['data_dir'],str(self.root))
        self.assertEqual(values['basis_files'],(str(self.root/'basis'),))
        self.assertEqual(values['potential_files'],(str(self.root/'potential'),))

    def test_incomplete_nonfinite_and_conflicting_q_payloads_are_rejected(self):
        for payload in ('O DZVP-MOLOPT-SR-GTH-q6\n', basis_entry('O','DZVP-MOLOPT-SR-GTH-q6').replace('1.0 1.0','NaN 1.0'),
                        basis_entry('O','DZVP-MOLOPT-SR-GTH-q6','other-q2'),
                        basis_entry('O','DZVP-MOLOPT-SR-GTH-q6')+' 0.0\n',
                        basis_entry('O','DZVP-MOLOPT-SR-GTH-q6').replace('1.0 1.0','1_0 1.0')):
            b = self.file('broken',payload)
            with self.subTest(payload=payload), self.assertRaises(ParseError):
                self.generate(basis_files=(b,))
        p = self.file('broken-pot',potential_entry('O',2,'GTH-PBE-q6'))
        with self.assertRaisesRegex(ParseError,'occupations q2 disagree with header q6'):
            self.generate(potential_files=(p,))

    def test_fortran_exponents_and_case_insensitive_element_headers(self):
        b = self.file('b',basis_entry('O','DZVP-MOLOPT-SR-GTH-q6').replace('O ','o ').replace('1.0','1.D+0'))
        p = self.file('p',potential_entry('O',6,'GTH-PBE-q6').replace('0.2','2.D-1'))
        _, manifest = self.generate(basis_files=(b,),potential_files=(p,))
        self.assertEqual(manifest['basis_validation']['status'],'data_checked')

    def test_unknown_unused_headers_are_not_silently_repaired(self):
        b = self.file('b',basis_entry('O','DZVP-MOLOPT-SR-GTH-q6') + basis_entry('a','TZVP-MOLOPT-PBE0-GTH-q10'))
        _, manifest = self.generate(basis_files=(b,))
        headers = manifest['kinds']['O']['basis_source']['unrecognized_headers']
        self.assertEqual(headers[0]['line'],5)
        self.assertTrue(headers[0]['text'].startswith('a '))
        self.assertTrue(any('unrecognized unused headers' in w for w in manifest['warnings']))

    def test_mixed_potential_files_cannot_silently_merge_or_replace(self):
        self.atom = Structure(['O','Fe'], [[0.,0.,0.],[0.,0.,2.]], None, None, {'path':'synthetic.xyz'})
        self.uzh()
        self.file('BASIS_MOLOPT_UCL',basis_entry('Fe','TZVP-MOLOPT-SR-GTH-q16'))
        self.file('GTH_POTENTIALS',potential_entry('Fe',16,'GTH-PBE-q16'))
        with self.assertRaisesRegex(KitError,'single POTENTIAL_FILE_NAME'):
            self.generate(basis='uzh-pbe-tzvp',basis_overrides=(('Fe','molopt-sr-tzvp'),),data_dir=str(self.root))

    def test_cli_replay_files_custom_names_and_stable_ids(self):
        b = self.file('orb file',basis_entry('O','real-q6'))
        p = self.file('pot file',potential_entry('O',6,'real-pot'))
        settings = replace(self.settings,project='replay',basis='custom-orbital',custom_basis_file=b,custom_basis_name='real-q6',
                           custom_potential_file=p,custom_potential_name='real-pot',basis_files=(b,),potential_files=(p,))
        source = self.file('source.xyz','1\nsynthetic\nO 0 0 0\n')
        output = self.root/'replayed.inp'
        args = command_arguments(source,-1,str(output),settings)
        parsed = build_parser().parse_args(args[3:])
        reconstructed = InputSettings.from_config({key:getattr(parsed,key) for key in InputSettings.__dataclass_fields__})
        self.assertEqual(generate_input(self.atom,reconstructed)[0],generate_input(self.atom,settings)[0])
        self.assertIn('--basis=custom-orbital',args)
        self.assertIn('--basis-file='+b,args)
        with patch('sys.stderr',io.StringIO()):
            self.assertEqual(main(args[3:]),0)
        self.assertEqual(output.read_text(),generate_input(self.atom,settings)[0])
        with patch('sys.stderr',io.StringIO()), self.assertRaises(SystemExit) as error:
            build_parser().parse_args(['generate-input','--basis','3'])
        self.assertEqual(error.exception.code,2)

    def test_new_outputs_keep_exclusive_creation_and_original_data_bytes(self):
        b,p = self.uzh()
        before = {path:Path(path).read_bytes() for path in (b,p)}
        settings = replace(self.settings,basis='uzh-pbe-tzvp',data_dir=str(self.root))
        out = self.root/'new.inp'
        write_input(self.atom,settings,out)
        with self.assertRaises(OutputExists):
            write_input(self.atom,settings,out)
        for path in before:
            self.assertEqual(Path(path).read_bytes(),before[path])

    def test_emitted_file_union_cannot_shadow_another_kinds_basis(self):
        self.atom = Structure(['O','Fe'], [[0.,0.,0.],[0.,0.,2.]], None, None, {'path':'synthetic.xyz'})
        self.file('BASIS_MOLOPT', basis_entry('O','TZVP-MOLOPT-GTH-q6') +
                  basis_entry('Fe','TZVP-MOLOPT-SR-GTH-q16',exponent=2.))
        self.file('BASIS_MOLOPT_UCL',basis_entry('Fe','TZVP-MOLOPT-SR-GTH-q16',exponent=1.))
        self.file('GTH_POTENTIALS',potential_entry('O',6,'GTH-PBE-q6') + potential_entry('Fe',16,'GTH-PBE-q16'))
        with self.assertRaisesRegex(AmbiguousProject,'Ambiguous ORB alias/content'):
            self.generate(basis='molopt-tzvp',basis_overrides=(('Fe','molopt-sr-tzvp'),),data_dir=str(self.root))

    def test_generic_alias_cannot_hide_a_different_q_entry(self):
        b = self.file('orb',basis_entry('O','real-q2','generic') + basis_entry('O','real-q6','generic'))
        with self.assertRaisesRegex(AmbiguousProject,'q-qualified alias'):
            self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name='generic')
        _, manifest = self.generate(basis='custom-orbital',custom_basis_file=b,custom_basis_name='real-q6')
        self.assertEqual(manifest['kinds']['O']['basis_q'],6)

    def test_default_known_policy_changes_reconstruct_026_reference(self):
        # Independently generated from git HEAD 229d09d in a temporary source tree;
        # invented isolated O geometry, not a CP2K calculation or recommendation.
        text, _ = self.generate()
        self.assertNotIn('BASIS_SET_FILE_NAME "', text)
        self.assertNotIn('POTENTIAL_FILE_NAME "', text)
        legacy_text = re.sub(r'(?m)^(\s*(?:BASIS_SET_FILE_NAME|POTENTIAL_FILE_NAME)) (.+)$',
                             r'\1 "\2"', text)
        self.assertNotIn('NGRIDS', text)
        legacy_text = legacy_text.replace('# Multiwfn references:', '# CELL vectors and COORD Cartesian coordinates are in angstrom (CP2K default units).\n# Multiwfn references:')
        legacy_text = legacy_text.replace('      REL_CUTOFF [Ry] 55\n', '      REL_CUTOFF [Ry] 55\n      NGRIDS 4\n')
        legacy_text = legacy_text.replace('    &SCF\n', '    &SCF\n      SCF_GUESS ATOMIC\n')
        legacy_text = legacy_text.replace('        ALGORITHM STRICT\n', '')
        legacy_text = legacy_text.replace('EPS_SCF 1.0E-06', 'EPS_SCF 5.0E-06')
        legacy_text = legacy_text.replace('      &PRINT\n        &RESTART\n          BACKUP_COPIES 0\n        &END RESTART\n      &END PRINT\n', '')
        legacy_text = legacy_text.replace('      PERIODIC NONE\n    &END CELL', '      PERIODIC NONE #Direction(s) of applied PBC (geometry aspect)\n    &END CELL')
        self.assertEqual(hashlib.sha256(legacy_text.encode()).hexdigest(),
                         '26af096bc28739351a0d34635c5612969c6a248c3c6fcfe91786fb323b0a2308')

    def test_uzh_pbe_catalog_covers_all_existing_fixed_valences(self):
        from cp2kkit.basis_resolution import catalog_files
        from cp2kkit.inputgen import VALENCE
        for identifier in ('uzh-pbe-dzvp','uzh-pbe-tzvp','uzh-pbe-tzv2p'):
            for element,q in VALENCE.items():
                with self.subTest(identifier=identifier,element=element):
                    self.assertTrue(catalog_files(BY_ID[identifier],element,q))
                    self.atom = Structure([element],[[0.,0.,0.]],None,None,{'path':'synthetic.xyz'})
                    _, manifest = self.generate(basis=identifier,multiplicity=1+q%2)
                    self.assertEqual(manifest['kinds'][element]['valence_electrons'],q)
                    self.assertEqual(manifest['basis_validation']['status'],'unverified_template')

    def test_missing_data_lists_actual_split_kind_labels(self):
        self.atom = Structure(['Fe','Fe'],[[0.,0.,0.],[2.,0.,0.]],None,None,{'path':'synthetic.xyz'})
        with self.assertRaises(KitError) as error:
            self.generate(basis='molopt-tzvp',magnetism=(('@1',4.),('@2',-4.)))
        self.assertIn('Fe_m1',str(error.exception))
        self.assertIn('Fe_m2',str(error.exception))

    def test_full_editor_registry_and_custom_choices_write_same_shared_metadata(self):
        from cp2kkit.input_tui import run_interactive
        b,p = self.uzh()
        source = self.file('synthetic.xyz','1\nsynthetic\nO 0 0 0\n')
        for choice, expected in (('21\n','uzh-pbe-tzvp'),
                                 (f'900\n{b}\nTZVP-MOLOPT-PBE-GTH-q6\n{p}\nGTH-PBE-q6\n','custom-orbital')):
            out = self.root/(expected+'.inp')
            log = TTY()
            code = run_interactive(source,-1,str(out),replace(self.settings,data_dir=str(self.root)),
                                   stdin=TTY('2\n'+choice+'w\ny\n\n'),stdout=log,plain=True)
            self.assertEqual(code,0)
            manifest = json.loads(Path(str(out)+'.json').read_text())
            self.assertEqual(manifest['settings']['basis'],expected)
            self.assertIn('basis=TZVP-MOLOPT-PBE-GTH-q6',log.getvalue())
            self.assertIn('potential=6 [occupations]',log.getvalue())
            self.assertFalse(manifest['basis_validation']['runnable_verified'])

    def test_protocol_guard_uses_pinned_content_identity_not_file_name(self):
        b,p = self.uzh()
        # Mock a known classic reference identity using invented bytes. This tests
        # the guard only; it does NOT identify this fixture as real CP2K data.
        source = {'url':'https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/GTH_POTENTIALS',
                  'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
        with patch('cp2kkit.data_catalog.CATALOG_SOURCES',[source]):
            with self.assertRaisesRegex(KitError,'classic GTH_POTENTIALS reference'):
                self.generate(basis='uzh-pbe-tzvp',data_dir=str(self.root))

    def test_public_field_numbers_are_not_choice_positions(self):
        field = next(f for _,group in GROUPS for f in group if f.name=='basis')
        self.assertEqual(parse_value(field,'3'),'molopt-tzvp')
        self.assertEqual(parse_value(field,'900'),'custom-orbital')
        self.assertEqual(self.menu('3\n',current='invalid-retained-value')[0],'molopt-tzvp')
        from cp2kkit.input_tui import field_display
        self.assertIn('invalid',field_display(field,{'basis':'invalid-retained-value'}))
        self.assertIn('UNAVAILABLE',field_display(field,{'basis':'uzh-pbe0-tzvp'}))
        with self.assertRaises(ValueError):
            parse_value(field,'10')


if __name__ == '__main__':
    unittest.main()
