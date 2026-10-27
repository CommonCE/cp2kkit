"""ADMM/ADMMS combination tests with invented data only; no native execution."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.auxiliary_basis import AUXILIARY_OPTIONS
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_tui import command_arguments, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.ri_hfx import RI_BASIS_SIZES, resolve_ri_hfx
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_input_tui import TTY


class ADMMRIHFXTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-admm-ri-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.water = read_structure(self.source)
        self.data = self.root/'data'
        self.data.mkdir()
        self.orb = self.data/'BASIS_MOLOPT'
        self.orb.write_text(''.join(basis_entry(el, f'DZVP-MOLOPT-SR-GTH-q{q}')
                                    for el, q in (('H', 1), ('O', 6))))
        self.aux = self.data/'BASIS_ADMM_UZH'
        self.aux.write_text(''.join(basis_entry(el, f'{option.family}-q{q}')
                                    for option in AUXILIARY_OPTIONS for el, q in (('H', 1), ('O', 6))))
        (self.data/'GTH_POTENTIALS').write_text(''.join(potential_entry(el, q, f'GTH-PBE-q{q}')
                                                     for el, q in (('H', 1), ('O', 6))))
        self.table = self.data/'t_c_g.dat'
        self.table.write_text('synthetic table bytes, not a CP2K table\n')
        self.settings = InputSettings(functional='PBE0', periodic='NONE', admm=True,
                                      ri_hfx=True, data_dir=str(self.data))
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, **changes):
        return generate_input(self.water, replace(self.settings, **changes))

    def test_admms_effective_model_and_physical_identity(self):
        for ri in (False, True):
            for purification in (None, 'NONE'):
                for option in AUXILIARY_OPTIONS:
                    with self.subTest(ri=ri, purification=purification, aux=option.id):
                        text, m = self.generate(admm_variant='ADMMS', ri_hfx=ri,
                                                admm_purification=purification, aux_basis=option.id)
                        _, ordinary = self.generate(ri_hfx=ri, aux_basis=option.id)
                        model = m['method_profile']['admm']
                        self.assertEqual(model['variant'], 'ADMMS')
                        self.assertEqual(model['method'], 'CHARGE_CONSTRAINED_PROJECTION')
                        self.assertEqual(model['purification'], 'NONE')
                        self.assertEqual(model['purification_selection'],
                                         'explicit' if purification else 'variant-derived')
                        self.assertEqual(model['exchange_scaling_model'], 'MERLOT')
                        self.assertEqual(model['exchange_correction_functional'], 'DEFAULT')
                        self.assertIn('METHOD CHARGE_CONSTRAINED_PROJECTION', text)
                        self.assertIn('ADMM_PURIFICATION_METHOD NONE', text)
                        self.assertIn('EXCH_SCALING_MODEL MERLOT', text)
                        self.assertNotIn('ADMM_TYPE', text)
                        self.assertNotIn('MO_DIAG', text)
                        self.assertEqual(text.count('&AUXILIARY_DENSITY_MATRIX_METHOD\n'), 1)
                        self.assertEqual(m['method_profile']['hfx'], ordinary['method_profile']['hfx'])
                        self.assertEqual(m['method_profile']['xc_parameters'],
                                         ordinary['method_profile']['xc_parameters'])
                        self.assertEqual(m['kinds'], ordinary['kinds'])
                        if ri:
                            self.assertEqual(m['method_profile']['hfx']['ri']['basis_parent_role'], 'AUX_FIT')
                            self.assertNotIn('&MEMORY', text)
                        else:
                            self.assertIn('&MEMORY', text)
                        self.assertFalse(model['runtime_validated'])

    def test_admms_invalid_scope_and_retained_controls_no_publication(self):
        cases = [dict(admm=False), dict(admm_purification='MO_DIAG')]
        cases += [dict(admm_variant=v) for v in (None, '', 'admms', 'ADMM1', True, [], {})]
        cases += [dict(functional='HSE06'), dict(scf='diag'), dict(run_type='ENERGY_FORCE'),
                  dict(run_type='GEO_OPT'), dict(periodic='XYZ', cell=(12., 12., 12.)),
                  dict(multiplicity=3), dict(charge=1), dict(magnetism=()),
                  dict(magnetism=(('O', 0.),)), dict(kpoints=(2, 2, 2)),
                  dict(smearing=300.), dict(dft_plus_u=(('O', 1, 2.),)),
                  dict(basis='ae-pob-dzvp-rev2'), dict(basis='uzh-pbe0-dzvp'),
                  dict(cp2k_version='2026.1'), dict(method='GFN1-xTB'),
                  dict(ri_hfx=True, ri_metric='TRUNCATED', ri_cutoff_radius=1.7)]
        out = self.root/'admms-invalid.inp'
        out.write_text('existing input\n')
        for ri in (False, True):
            for changes in cases:
                with self.subTest(ri=ri, changes=changes), self.assertRaises(KitError):
                    settings = replace(self.settings, **{'admm_variant': 'ADMMS', 'ri_hfx': ri,
                                                          'write_json': True, **changes})
                    write_input(self.water, settings, out)
                self.assertEqual(out.read_text(), 'existing input\n')
                self.assertFalse(Path(str(out)+'.json').exists())
        for ri in (False, True):
            with self.assertRaisesRegex(KitError, 'CDD'):
                write_input(self.water, replace(self.settings, admm_variant='ADMMS', ri_hfx=ri,
                                                density_difference=True), self.root/'cdd-admms.inp')
            self.assertFalse((self.root/'cdd-admms.inp').exists())

    def test_admms_config_manifest_and_cli_replay(self):
        legacy = asdict(self.settings)
        legacy.pop('admm_variant')
        self.assertEqual(generate_input(self.water, InputSettings.from_config(legacy)), self.generate())
        self.assertEqual(InputSettings.from_config({}).admm_variant, 'BASIS_PROJECTION')
        for ri in (False, True):
            settings = replace(self.settings, admm_variant='ADMMS', ri_hfx=ri, write_json=True)
            text, manifest = generate_input(self.water, InputSettings.from_config(asdict(settings)))
            self.assertEqual(generate_input(self.water, InputSettings.from_config(json.loads(json.dumps(manifest)))),
                             (text, manifest))
            out = self.root/f'admms-cli-{ri}.inp'
            result = subprocess.run(command_arguments(self.source, -1, out, settings),
                                    text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(out.read_text(), text)
            self.assertEqual(json.loads(Path(str(out)+'.json').read_text())['method_profile'],
                             manifest['method_profile'])

    def test_admms_tui_order_and_retained_purification(self):
        profiles = []
        for first, second in (('121\ny\n\n\n\n\n', '122\ny\nADMMS\n\n'),
                              ('122\ny\nADMMS\n\n', '121\ny\n\n\n\n\n')):
            out = self.root/f'admms-menu-{len(profiles)}.inp'
            log = TTY()
            code = run_interactive(str(self.source), -1, str(out),
                                   replace(self.settings, admm=False, ri_hfx=False, write_json=True),
                                   stdin=TTY(first+second+'r\n\n0\n'), stdout=log, plain=True)
            self.assertEqual(code, 0, log.getvalue())
            self.assertIn('exchange scaling MERLOT; variant ADMMS', log.getvalue())
            self.assertIn('RI parent: AUX_FIT', log.getvalue())
            profiles.append(json.loads(Path(str(out)+'.json').read_text())['method_profile'])
        self.assertEqual(profiles[0], profiles[1])
        out = self.root/'retained.inp'
        log = TTY()
        code = run_interactive(str(self.source), -1, str(out),
                               replace(self.settings, admm_purification='MO_DIAG'),
                               stdin=TTY('122\n\nADMMS\n\nr\n-10\n'), stdout=log, plain=True)
        self.assertIn('reset retained MO_DIAG explicitly', log.getvalue())
        self.assertFalse(out.exists())

    def test_admms_disable_requires_explicit_variant_reset(self):
        from cp2kkit.input_editor import FIELDS, edit_entry
        from cp2kkit.input_tui import Menu
        from cp2kkit.menu_registry import BY_TOKEN
        values = asdict(replace(self.settings, admm_variant='ADMMS'))
        log = TTY()
        edit_entry(Menu(TTY('n\n\n'), log, plain=True), values, BY_TOKEN['122'])
        self.assertFalse(values['admm'])
        self.assertEqual(values['admm_variant'], 'ADMMS')
        with self.assertRaisesRegex(KitError, 'require ADMM enabled'):
            generate_input(self.water, InputSettings(**values))
        edit_entry(Menu(TTY('\nBASIS_PROJECTION\n'), log, plain=True), values, BY_TOKEN['122'])
        self.assertEqual(values['admm_variant'], 'BASIS_PROJECTION')
        text, _ = generate_input(self.water, InputSettings(**values))
        self.assertNotIn('&AUXILIARY_DENSITY_MATRIX_METHOD', text)
        self.assertEqual(FIELDS['admm_variant'].choices, ('BASIS_PROJECTION', 'ADMMS'))

    def test_admms_publication_protects_sources_and_sidecars(self):
        settings = replace(self.settings, admm_variant='ADMMS', write_json=True)
        alias = self.root/'aux-hardlink.inp'
        os.link(self.aux, alias)
        before = self.aux.read_bytes()
        with self.assertRaises(KitError):
            write_input(self.water, settings, alias)
        self.assertEqual(self.aux.read_bytes(), before)
        out = self.root/'admms-old.inp'
        out.write_text('old input\n')
        sidecar = Path(str(out)+'.json')
        sidecar.write_text('old json\n')
        with self.assertRaises(OutputExists):
            write_input(self.water, settings, out)
        self.assertEqual(out.read_text(), 'old input\n')
        self.assertEqual(sidecar.read_text(), 'old json\n')
        fresh = self.root/'admms-fresh.inp'
        with patch('cp2kkit.inputgen.os.link', side_effect=OSError('injected failure')):
            with self.assertRaisesRegex(OSError, 'injected failure'):
                write_input(self.water, settings, fresh)
        self.assertFalse(fresh.exists())
        self.assertFalse(Path(str(fresh)+'.json').exists())

    def test_supported_sizes_purification_and_parent_identity(self):
        for option in AUXILIARY_OPTIONS:
            for size in RI_BASIS_SIZES:
                for purification in (None, 'MO_DIAG', 'NONE'):
                    with self.subTest(aux=option.id, size=size, purification=purification):
                        text, m = self.generate(aux_basis=option.id, ri_basis_size=size,
                                                admm_purification=purification)
                        hfx = m['method_profile']['hfx']
                        ri = hfx['ri']
                        self.assertEqual(ri['basis_parent_role'], 'AUX_FIT')
                        self.assertEqual(m['method_profile']['generator_scope'],
                                         m['method_profile']['hybrid_acceleration_capabilities']['ri_hfx_admm_scope'])
                        self.assertEqual(ri['basis_size'], size)
                        self.assertTrue(hfx['admm'])
                        self.assertTrue(hfx['ri_hfx'])
                        self.assertEqual(m['settings']['multiplicity'], 1)
                        self.assertIn('UKS F', text)
                        for el, kind in m['kinds'].items():
                            parent = ri['basis_parents'][el]
                            self.assertEqual(parent, kind['aux_fit'])
                            self.assertEqual(parent['basis_source']['sha256'], hashlib.sha256(self.aux.read_bytes()).hexdigest())
                            self.assertTrue(parent['basis_source']['entry_sha256'])
                            self.assertFalse(parent['physical_pairing_validated'])
                        self.assertFalse(ri['runtime_validated'])
                        self.assertIn('generated_auxiliary_not_checked', ri['basis_validation'])
                        self.assertEqual(text.count('&AUXILIARY_DENSITY_MATRIX_METHOD\n'), 1)
                        self.assertEqual(text.count('&RI T\n'), 1)
                        self.assertNotIn('ADMMS', text)
                        self.assertNotIn('&MEMORY', text)
                        self.assertIsNone(hfx['max_memory_mib_per_mpi_process'])
                        self.assertIsNone(hfx['eps_storage_scaling'])
                        self.assertIn('ADMM_PURIFICATION_METHOD '+(purification or 'MO_DIAG'), text)
                        stack = []
                        for line in text.splitlines():
                            parts = line.split()
                            if not parts or parts[0].startswith('#'):
                                continue
                            if parts[0] == '&END':
                                self.assertEqual(stack.pop(), parts[1])
                            elif parts[0].startswith('&'):
                                if parts[0] == '&RI':
                                    self.assertEqual(stack, ['FORCE_EVAL', 'DFT', 'XC', 'HF'])
                                if parts[0] == '&AUXILIARY_DENSITY_MATRIX_METHOD':
                                    self.assertEqual(stack, ['FORCE_EVAL', 'DFT'])
                                stack.append(parts[0][1:])
                            elif parts[0] == 'AUTO_BASIS':
                                self.assertEqual(stack, ['FORCE_EVAL', 'DFT'])
                        self.assertEqual(stack, [])
                        self.assertFalse(any('No RI-HFX' in warning for warning in m['warnings']))
                        self.assertTrue(any('isolate RI error' in warning for warning in m['warnings']))

    def test_physical_settings_and_admm_model_unchanged(self):
        changes = dict(charge=2, multiplicity=1, hf_eps_schwarz=2e-7, eps_scf=3e-8,
                       ri_eps_filter=2e-10, ri_memory_cut=5)
        text, combo = self.generate(**changes)
        _, admm = self.generate(**{**changes, 'ri_hfx': False, 'ri_eps_filter': 1e-9, 'ri_memory_cut': 3})
        self.assertEqual(combo['method_profile']['admm'], admm['method_profile']['admm'])
        self.assertEqual(combo['method_profile']['xc_parameters'], admm['method_profile']['xc_parameters'])
        for key in ('fraction', 'interaction_potential', 'omega', 'cutoff_radius_angstrom', 'eps_schwarz'):
            self.assertEqual(combo['method_profile']['hfx'][key], admm['method_profile']['hfx'][key])
        self.assertEqual(combo['method_profile']['hfx']['ri']['effective_metric_operator'], 'COULOMB')
        self.assertEqual(combo['settings']['charge'], 2)
        self.assertIn('MEMORY_CUT 5', text)
        self.assertEqual(combo['method_profile']['hfx']['ri']['eps_filter'], 2e-10)
        self.assertIn('EXCH_SCALING_MODEL NONE', text)
        self.assertIn('EXCH_CORRECTION_FUNC DEFAULT', text)
        self.assertIn('METHOD BASIS_PROJECTION', text)

    def test_outside_intersection_and_bad_controls_preserve_existing_target(self):
        cases = [dict(functional=f) for f in ('HSE06', 'B3LYP', 'BHANDHLYP', 'M06-2X', 'PBE')]
        cases += [dict(functional='PBEH', pbeh_fraction=.3), dict(cp2k_version='2026.1'),
                  dict(periodic='XYZ', cell=(12., 12., 12.)), dict(periodic='XY'),
                  dict(scf='diag'), dict(run_type='ENERGY_FORCE'), dict(run_type='GEO_OPT'),
                  dict(run_type='CELL_OPT'), dict(charge=1), dict(multiplicity=3),
                  dict(magnetism=()), dict(magnetism=(('O', 0.),)),
                  dict(ri_metric='TRUNCATED', ri_cutoff_radius=1.7), dict(ri_cutoff_radius=1.7),
                  dict(kpoints=(2, 2, 2)), dict(smearing=300.), dict(dft_plus_u=(('O', 1, 2.),)),
                  dict(basis='ae-pob-dzvp-rev2'), dict(basis='uzh-pbe0-dzvp'),
                  dict(ri_eps_filter=float('nan')), dict(ri_eps_filter=float('inf')),
                  dict(ri_memory_cut=True), dict(ri_memory_cut=0), dict(hf_memory=1024),
                  dict(ri_hfx=False, ri_basis_size='LARGE'), dict(admm=False, admm_purification='NONE')]
        out = self.root/'invalid.inp'
        out.write_text('existing input\n')
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(KitError):
                write_input(self.water, replace(self.settings, write_json=True, **changes), out)
            self.assertEqual(out.read_text(), 'existing input\n')
            self.assertFalse(Path(str(out)+'.json').exists())

    def test_cdd_excluded_before_any_publication(self):
        out = self.root/'cdd.inp'
        settings = replace(self.settings, density_difference=True, fragment_a_indices='1',
                           fragment_a_charge=0, fragment_a_multiplicity=1,
                           fragment_b_charge=0, fragment_b_multiplicity=1, write_json=True)
        before = set(self.root.iterdir())
        with self.assertRaisesRegex(KitError, 'does not support CDD'):
            write_input(self.water, settings, out)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_config_manifest_replay_and_cli(self):
        settings = replace(self.settings, aux_basis='admm-tzp', ri_basis_size='LARGE',
                           ri_memory_cut=5, ri_eps_filter=2e-10, write_json=True)
        text, m = generate_input(self.water, InputSettings.from_config(asdict(settings)))
        replay, manifest = generate_input(self.water, InputSettings.from_config(json.loads(json.dumps(m))))
        self.assertEqual(replay, text)
        self.assertEqual(manifest, m)
        out = self.root/'cli.inp'
        result = subprocess.run(command_arguments(str(self.source), -1, str(out), settings),
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(out.read_text(), text)
        saved = json.loads(Path(str(out)+'.json').read_text())
        self.assertEqual(saved['method_profile'], m['method_profile'])
        bad = self.root/'bad-cli.inp'
        result = subprocess.run(command_arguments(str(self.source), -1, str(bad), replace(settings, scf='diag')),
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(bad.exists())

    def test_tui_controls_in_either_order(self):
        texts, profiles = [], []
        for first, second in (('121\ny\n\n\n\n\n', '122\ny\n\n\n'),
                              ('122\ny\n\n\n', '121\ny\n\n\n\n\n')):
            out = self.root/f'menu-{len(texts)}.inp'
            log = TTY()
            settings = replace(self.settings, admm=False, ri_hfx=False, write_json=True)
            result = run_interactive(str(self.source), -1, str(out), settings,
                                     stdin=TTY(first+second+'r\n\n0\n'), stdout=log, plain=True)
            self.assertEqual(result, 0, log.getvalue())
            self.assertIn('RI parent: AUX_FIT', log.getvalue())
            self.assertIn('ADMM: BASIS_PROJECTION; purification MO_DIAG', log.getvalue())
            texts.append(out.read_text())
            profiles.append(json.loads(Path(str(out)+'.json').read_text())['method_profile'])
        self.assertEqual(texts[0], texts[1])
        self.assertEqual(profiles[0], profiles[1])

    def test_missing_malformed_and_unknown_parent_data(self):
        with self.assertRaises(KitError):
            self.generate(data_dir=None)
        # Exercise the resolver contract independently of the checked data parser.
        _, m = self.generate()
        records = m['kinds']
        parents = {el: kind['aux_fit'] for el, kind in records.items()}
        settings = InputSettings.from_config(m)
        for parent in (None, {}, {'O': parents['O']}):
            with self.assertRaisesRegex(KitError, 'complete resolved AUX_FIT'):
                resolve_ri_hfx(settings, records, copy.deepcopy(m['method_profile']['hfx']), 'NONE', None, auxiliary=parent)
        with self.assertRaisesRegex(KitError, 'checked AUX_FIT parent identity'):
            resolve_ri_hfx(settings, records, copy.deepcopy(m['method_profile']['hfx']), 'NONE', None,
                           auxiliary={**parents, 'O': None})
        for field, value in (('basis_q', None), ('basis_source', None), ('basis_source', {}),
                             ('role', 'ORB'), ('basis', None), ('data_validation', 'not_checked')):
            damaged = copy.deepcopy(parents)
            damaged['O'][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(KitError, 'checked AUX_FIT parent identity'):
                resolve_ri_hfx(settings, records, copy.deepcopy(m['method_profile']['hfx']), 'NONE', None, auxiliary=damaged)
        original = self.aux.read_text()
        for damaged in ('O admm-dzp-q6\n', basis_entry('O', 'admm-dzp-q6'),
                        basis_entry('O', 'admm-dzp-q4')+basis_entry('H', 'admm-dzp-q1')):
            self.aux.write_text(damaged)  # Disposable synthetic data only.
            with self.assertRaises(KitError):
                self.generate()
        self.aux.write_text(original)
        self.orb.write_text('O DZVP-MOLOPT-SR-GTH-q6\n')
        with self.assertRaises(KitError):
            self.generate()

    def test_sources_collisions_symlinks_and_publication_rollback(self):
        for source in (self.source, self.orb, self.aux, self.table, self.data/'GTH_POTENTIALS'):
            before = source.read_bytes()
            with self.assertRaises(KitError):
                write_input(self.water, self.settings, source)
            self.assertEqual(source.read_bytes(), before)
        alias = self.root/'aux-alias.inp'
        os.link(self.aux, alias)
        with self.assertRaises(KitError):
            write_input(self.water, self.settings, alias)
        out = self.root/'old.inp'
        out.write_text('old input\n')
        sidecar = Path(str(out)+'.json')
        sidecar.write_text('old json\n')
        with self.assertRaises(OutputExists):
            write_input(self.water, replace(self.settings, write_json=True), out)
        self.assertEqual(out.read_text(), 'old input\n')
        self.assertEqual(sidecar.read_text(), 'old json\n')
        link = self.root/'link.inp'
        link.symlink_to(out)
        with self.assertRaises(KitError):
            write_input(self.water, self.settings, link)
        fresh = self.root/'fresh.inp'
        with patch('cp2kkit.inputgen.os.link', side_effect=OSError('injected publication failure')):
            with self.assertRaisesRegex(OSError, 'injected publication failure'):
                write_input(self.water, replace(self.settings, write_json=True), fresh)
        self.assertFalse(fresh.exists())
        self.assertFalse(Path(str(fresh)+'.json').exists())


if __name__ == '__main__':
    unittest.main()
