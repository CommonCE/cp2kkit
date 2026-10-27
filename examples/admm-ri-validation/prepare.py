"""Prepare six isolated water ENERGY comparisons; never execute or submit CP2K.

Run from a cp2kkit checkout with PYTHONPATH=src. See
../../docs/admm-ri-native-validation.md for the validation protocol.
"""
import argparse
import hashlib
import shutil
from dataclasses import asdict, replace
from pathlib import Path

from cp2kkit import __version__
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.io import json_text, new_file, staged_files
from cp2kkit.models import SCHEMA_VERSION
from cp2kkit.structure import read_structure

DATA_FILES = ('BASIS_MOLOPT', 'GTH_POTENTIALS', 'BASIS_ADMM_UZH', 't_c_g.dat')
CASES = (
    ('01-direct', False, False, 'BASIS_PROJECTION'),
    ('02-admm', True, False, 'BASIS_PROJECTION'),
    ('03-admms', True, False, 'ADMMS'),
    ('04-ri', False, True, 'BASIS_PROJECTION'),
    ('05-admm-ri', True, True, 'BASIS_PROJECTION'),
    ('06-admms-ri', True, True, 'ADMMS'),
)
WATER = ('3\nConstructed smoke geometry translated into cell, angstrom; not optimized\n'
         'O 8.000000 8.000000 8.000000\n'
         'H 8.757000 8.000000 8.586000\n'
         'H 7.243000 8.000000 8.586000\n')


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
            'size_bytes': len(raw)}


def save(path, text):
    with new_file(path) as stream:
        stream.write(text)


def prepare(data_dir, output):
    """Create an entirely new bundle; errors retain partial files for inspection."""
    data_dir, output = Path(data_dir).resolve(), Path(output).absolute()
    sources = {name: identity(data_dir/name) for name in DATA_FILES}
    # mkdir is exclusive, including symlinks. No reuse or cleanup of user paths.
    output.mkdir()
    staged_data = output/'data'
    staged_data.mkdir()
    for name in DATA_FILES:
        with (data_dir/name).open('rb') as source, new_file(staged_data/name, binary=True) as target:
            shutil.copyfileobj(source, target)
        if identity(staged_data/name)['sha256'] != sources[name]['sha256']:
            raise ValueError(f'Data changed during staging: {name}')
    save(output/'water.xyz', WATER)
    structure = read_structure(output/'water.xyz')
    common = InputSettings(project='water', functional='PBE0', basis='molopt-sr-dzvp',
                           periodic='NONE', cell=(16., 16., 16.), charge=0, multiplicity=1,
                           scf='ot', eps_scf=1e-8, max_scf=25, max_outer_scf=20,
                           hf_eps_schwarz=1e-8, data_dir=str(staged_data), write_json=True)
    records = []
    for name, admm, ri, variant in CASES:
        directory = output/name
        directory.mkdir()
        for filename in DATA_FILES:
            (directory/filename).symlink_to(Path('../data')/filename)
        text, manifest = generate_input(structure, replace(common, admm=admm, ri_hfx=ri,
                                                         admm_variant=variant))
        with staged_files([directory/'water.inp', directory/'water.inp.json']) as streams:
            streams[0].write(text)
            streams[1].write(json_text(manifest))
        records.append({'id': name, 'input': f'{name}/water.inp',
                        'sidecar': f'{name}/water.inp.json', 'input_sha256': manifest['input_sha256'],
                        'admm': manifest['method_profile'].get('admm'),
                        'ri': manifest['method_profile']['hfx'].get('ri'),
                        'process_exit_status': None, 'native_syntax_accepted': None,
                        'scf_converged': None, 'clean_exit': None,
                        'energy_hartree': None, 'wall_time_seconds': None,
                        'peak_memory_bytes': None, 'warnings': manifest['warnings']})
    checkout = Path(__file__).resolve().parents[2]
    matrix = {'schema_version': SCHEMA_VERSION, 'generator_version': __version__,
              'purpose': 'Input preparation only; no native execution authorized or performed',
              'target_cp2k_version': '2026.2', 'actual_binary_identity': None,
              'data_sources': sources, 'common_requested_settings': asdict(common),
              'geometry': identity(output/'water.xyz'), 'cases': records,
              'comparison_pairs': [
                  {'test': '04-ri', 'reference': '01-direct', 'meaning': 'independent RI error'},
                  {'test': '05-admm-ri', 'reference': '02-admm', 'meaning': 'RI increment with ordinary ADMM'},
                  {'test': '06-admms-ri', 'reference': '03-admms', 'meaning': 'RI increment with ADMMS'},
                  *({'test': name, 'reference': '01-direct', 'meaning': 'total approximation difference'}
                    for name in ('02-admm', '03-admms', '05-admm-ri', '06-admms-ri'))],
              'energy_difference_convention': 'E(test) - E(reference), hartree; converged clean-exit pairs only',
              'energy_acceptance_tolerance_hartree': None,
              'implementation_sources': {str(path.relative_to(checkout)): identity(path)
                                         for path in sorted((checkout/'src/cp2kkit').glob('*.py'))},
              'preparation_source': identity(Path(__file__)),
              'validation_protocol': identity(checkout/'docs/admm-ri-native-validation.md')}
    save(output/'case-matrix.json', json_text(matrix))
    save(output/'VALIDATION.md', (checkout/'docs/admm-ri-native-validation.md').read_text())
    print(f'Prepared {len(records)} inputs in {output}; no CP2K execution or submission.')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True, help='Actual CP2K 2026.2 data directory')
    parser.add_argument('--output', type=Path, required=True, help='Entirely new directory; parent must exist')
    args = parser.parse_args()
    prepare(args.data_dir, args.output)


if __name__ == '__main__':
    main()
