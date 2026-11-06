"""Frozen cross-mode generator policy using invented data, never native CP2K.

Expected support is explicit here rather than derived from the capability helper:
changing that helper must not silently broaden this acceptance baseline.
"""
import copy
import itertools
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.errors import KitError
from cp2kkit.input_tui import command_arguments
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.ri_hfx import acceleration_capabilities
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry


FUNCTIONALS = ('PBE0', 'HSE06', 'B3LYP', 'BHANDHLYP', 'M06-2X', 'PBEH')
MODES = {
    'direct': {},
    'admm': {'admm': True},
    'ri': {'ri_hfx': True},
    'admm-ri': {'admm': True, 'ri_hfx': True},
    'admms': {'admm': True, 'admm_variant': 'ADMMS'},
    'admms-ri': {'admm': True, 'admm_variant': 'ADMMS', 'ri_hfx': True},
}
STATES = {
    'rks': {'charge': 0, 'multiplicity': 1},
    'doublet': {'charge': 1, 'multiplicity': 2},
    'explicit-uks': {'charge': 0, 'multiplicity': 1, 'magnetism': ()},
}


def supported(functional, mode, periodic, scf, task, state):
    if mode == 'direct':
        return True
    if mode in ('admm', 'ri'):
        return functional in ('PBE0', 'HSE06')
    return (functional == 'PBE0' and periodic == 'NONE' and scf == 'ot'
            and task == 'ENERGY' and state == 'rks')


class HybridScopeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-hybrid-scope-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\ninvented scope fixture\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.water = read_structure(self.source)
        self.data = self.root/'data'
        self.data.mkdir()
        (self.data/'BASIS_MOLOPT').write_text(''.join(
            basis_entry(el, f'DZVP-MOLOPT-SR-GTH-q{q}') for el, q in (('H', 1), ('O', 6))))
        (self.data/'BASIS_ADMM_UZH').write_text(''.join(
            basis_entry(el, f'admm-dzp-q{q}') for el, q in (('H', 1), ('O', 6))))
        (self.data/'GTH_POTENTIALS').write_text(''.join(
            potential_entry(el, q, f'GTH-{family}-q{q}')
            for family in ('PBE', 'BLYP') for el, q in (('H', 1), ('O', 6))))
        (self.data/'t_c_g.dat').write_text('invented bytes, not a numerical CP2K table\n')
        self.settings = InputSettings(functional='PBE0', periodic='NONE', cell=(20., 21., 22.),
                                      data_dir=str(self.data))
        self.target = self.root/'existing.inp'
        self.target.write_text('preserve existing input\n')
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def assert_identity(self, text, manifest, settings):
        profile = manifest['method_profile']
        hfx = profile['hfx']
        self.assertEqual(manifest['settings']['charge'], settings.charge)
        self.assertEqual(manifest['settings']['multiplicity'], settings.multiplicity)
        for name in ('functional', 'periodic', 'scf', 'run_type', 'admm', 'admm_variant', 'ri_hfx'):
            self.assertEqual(manifest['settings'][name], getattr(settings, name))
        self.assertEqual(text.count('      &HF\n'), 1)
        self.assertEqual(text.count('        &RI T\n'), int(settings.ri_hfx))
        self.assertEqual(text.count('    &AUXILIARY_DENSITY_MATRIX_METHOD\n'), int(settings.admm))
        self.assertEqual('        &MEMORY\n' in text, not settings.ri_hfx)
        self.assertEqual(hfx['fraction'], profile['exact_exchange_fraction'])
        operator = ('SHORTRANGE' if settings.functional == 'HSE06' else
                    'TRUNCATED' if settings.periodic == 'XYZ' else 'COULOMB')
        self.assertEqual(hfx['interaction_potential'], operator)
        self.assertEqual(hfx['admm'], settings.admm)
        self.assertEqual(hfx['ri_hfx'], settings.ri_hfx)
        self.assertFalse(hfx['runtime_validated'])
        if settings.ri_hfx:
            self.assertIsNone(hfx['max_memory_mib_per_mpi_process'])
            self.assertEqual(hfx['ri']['basis_parent_role'], 'AUX_FIT' if settings.admm else 'ORB')
            self.assertEqual(hfx['ri']['effective_metric_operator'], operator)
        if settings.admm:
            model = profile['admm']
            admms = settings.admm_variant == 'ADMMS'
            self.assertEqual(model['method'], 'CHARGE_CONSTRAINED_PROJECTION' if admms else 'BASIS_PROJECTION')
            self.assertEqual(model['purification'], 'NONE' if admms or settings.scf == 'diag' else 'MO_DIAG')
            self.assertEqual(model['exchange_scaling_model'], 'MERLOT' if admms else 'NONE')
            self.assertNotIn('ADMM_TYPE', text)

    def test_frozen_cross_mode_matrix_and_rejection_before_publication(self):
        sources = {path: path.read_bytes() for path in (self.source, *self.data.iterdir())}
        entries = set(self.root.iterdir())
        accepted = rejected = 0
        for functional, mode, periodic, scf, task, state in itertools.product(
                FUNCTIONALS, MODES, ('NONE', 'XYZ'), ('ot', 'diag'),
                ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'), STATES):
            with self.subTest(functional=functional, mode=mode, periodic=periodic,
                              scf=scf, task=task, state=state):
                settings = replace(self.settings, functional=functional, periodic=periodic,
                                   scf=scf, run_type=task, libxc_available=True,
                                   pbeh_fraction=.4 if functional == 'PBEH' else None,
                                   write_json=True, **MODES[mode], **STATES[state])
                before = copy.deepcopy(asdict(settings))
                if supported(functional, mode, periodic, scf, task, state):
                    text, manifest = generate_input(self.water, settings)
                    self.assert_identity(text, manifest, settings)
                    accepted += 1
                else:
                    with self.assertRaises(KitError):
                        write_input(self.water, settings, self.target)
                    self.assertEqual(self.target.read_text(), 'preserve existing input\n')
                    self.assertEqual(set(self.root.iterdir()), entries)
                    rejected += 1
                self.assertEqual(asdict(settings), before)
        self.assertEqual((accepted, rejected), (363, 933))
        for path, contents in sources.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_resolved_pbc_and_automatic_spin_cannot_bypass_narrow_modes(self):
        for mode in ('admm-ri', 'admms', 'admms-ri'):
            for pbc, charge, allowed in (([False]*3, 0, True), ([False]*3, 1, False),
                                         ([True]*3, 0, False)):
                with self.subTest(mode=mode, pbc=pbc, charge=charge):
                    water = replace(self.water, pbc=pbc)
                    settings = replace(self.settings, periodic=None, charge=charge,
                                       multiplicity=None, **MODES[mode])
                    if allowed:
                        _, manifest = generate_input(water, settings)
                        self.assertEqual(manifest['settings']['multiplicity'], 1)
                        self.assertEqual(manifest['generated_structure']['pbc'], pbc)
                    else:
                        with self.assertRaises(KitError):
                            write_input(water, settings, self.target)
                        self.assertEqual(self.target.read_text(), 'preserve existing input\n')

    def test_all_modes_manifest_replay_is_deterministic(self):
        for mode, controls in MODES.items():
            with self.subTest(mode=mode):
                settings = replace(self.settings, **controls)
                expected = generate_input(self.water, settings)
                replay = InputSettings.from_config(json.loads(json.dumps(expected[1])))
                self.assertEqual(generate_input(self.water, replay), expected)

    def test_cli_narrow_modes_reject_without_replacing_existing_input(self):
        for mode in ('admm-ri', 'admms', 'admms-ri'):
            with self.subTest(mode=mode):
                settings = replace(self.settings, run_type='ENERGY_FORCE', write_json=True, **MODES[mode])
                result = subprocess.run(command_arguments(self.source, -1, self.target, settings),
                                        text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('ENERGY', result.stderr)
                self.assertEqual(self.target.read_text(), 'preserve existing input\n')
                self.assertFalse(Path(str(self.target)+'.json').exists())

    def test_capabilities_match_frozen_functional_inventory(self):
        caps = acceleration_capabilities()
        self.assertEqual(tuple(caps['direct_hfx']), FUNCTIONALS)
        self.assertEqual(caps['admm'], ['PBE0', 'HSE06'])
        self.assertEqual(caps['ri_hfx'], ['PBE0', 'HSE06'])
        self.assertEqual(caps['admm_variants'], ['BASIS_PROJECTION', 'ADMMS'])
        self.assertTrue(caps['ri_hfx_admm'])
        self.assertFalse(caps['uzh_pbe0_protocol'])
        self.assertFalse(caps['runtime_validated'])


if __name__ == '__main__':
    unittest.main()
