"""Prepare three water CUBE validation cases; never execute or submit calculations."""
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

DATA_FILES = ('BASIS_MOLOPT', 'GTH_POTENTIALS')
WATER = ('3\nConstructed fixed smoke geometry, angstrom; not optimized\n'
         'O 8.000000 8.000000 8.000000\n'
         'H 8.757000 8.000000 8.586000\n'
         'H 7.243000 8.000000 8.586000\n')
CASES = (
    ('01-rks-ot', dict(charge=0, multiplicity=1, scf='ot', added_mos=0,
                       mo_nhomo=1, mo_nlumo=1)),
    ('02-rks-diag', dict(charge=0, multiplicity=1, scf='diag', added_mos=2,
                         mo_nhomo=2, mo_nlumo=2)),
    ('03-uks-ot', dict(charge=1, multiplicity=2, scf='ot', added_mos=0,
                       mo_nhomo=1, mo_nlumo=1)),
)
PENDING_FIELDS = ('process_exit_status', 'scheduler_state', 'scheduler_exit_code',
                  'native_syntax_accepted', 'scf_converged', 'virtual_eigensolver_converged',
                  'program_ended', 'clean_exit', 'actual_cube_count', 'actual_cube_inventory',
                  'grid_checks_passed', 'scientific_validation_passed')


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
            'size_bytes': len(raw)}


def save(path, text):
    with new_file(path) as stream:
        stream.write(text)


def portable_input(manifest):
    """Rebase only checked data rows; keep the original generator sidecar unchanged."""
    text = manifest['input_text']
    emitted = manifest['emitted_data_files']
    if len(emitted['basis']) != 1:
        raise ValueError('Expected one checked orbital basis file')
    for keyword, source, filename in (
        ('BASIS_SET_FILE_NAME', emitted['basis'][0], 'BASIS_MOLOPT'),
        ('POTENTIAL_FILE_NAME', emitted['potential'], 'GTH_POTENTIALS'),
    ):
        rows = [row for row in text.splitlines() if row.strip().startswith(keyword+' ')]
        if (len(rows) != 1 or Path(source).name != filename or
                rows[0].strip() != f'{keyword} {source}'):
            raise ValueError(f'Unexpected generated data reference: {keyword}')
        text = text.replace(rows[0]+'\n', f'    {keyword} {filename}\n', 1)
    return text


def frontier_request(manifest):
    """Expected 1-based MO indices from explicit PP electron state, not observed files."""
    settings = manifest['settings']
    electrons = manifest['explicit_electron_count']
    channels = manifest['extra_cube_output']['orbitals']['spin_channels']
    occupied = ([electrons//2] if channels == ['restricted'] else
                [(electrons+settings['multiplicity']-1)//2,
                 (electrons-settings['multiplicity']+1)//2])
    return [{'channel': channel, 'cp2k_spin_index': spin, 'occupied_orbitals': homo,
             'homo_index': homo, 'lumo_index': homo+1,
             'requested_occupied_indices': list(range(homo-settings['mo_nhomo']+1, homo+1)),
             'requested_virtual_indices': list(range(homo+1, homo+settings['mo_nlumo']+1))}
            for spin, (channel, homo) in enumerate(zip(channels, occupied), start=1)]


def prepare(data_dir, output):
    """Exclusive new bundle. Retain partial data/geometry on failure; never reuse it.

    All inputs, sidecars, matrix and instructions share staged publication and
    owned-inode rollback. This is not a crash-atomic directory transaction.
    """
    data_dir, output = Path(data_dir).resolve(), Path(output).absolute()
    sources = {name: identity(data_dir/name) for name in DATA_FILES}
    output.mkdir()  # Reject existing directories, files and dangling symlinks.
    data = output/'data'
    data.mkdir()
    for name in DATA_FILES:
        with (data_dir/name).open('rb') as source, new_file(data/name, binary=True) as target:
            shutil.copyfileobj(source, target)
        if identity(data/name)['sha256'] != sources[name]['sha256']:
            raise ValueError(f'Data changed during staging: {name}')
    save(output/'water.xyz', WATER)
    structure = read_structure(output/'water.xyz')
    common = InputSettings(project='water', run_type='ENERGY', cp2k_version='2026.2',
                           functional='PBE', basis='molopt-sr-dzvp', dispersion='none',
                           periodic='NONE', cell=(16., 16., 16.), kpoints=(1, 1, 1),
                           charge=0, multiplicity=1, scf='ot', added_mos=0,
                           cutoff=400., rel_cutoff=55., eps_scf=1e-7,
                           max_scf=128, max_outer_scf=20, smearing=None,
                           electron_density=True, hartree_potential=True, mo_cubes=True,
                           cube_stride=(1, 1, 1), data_dir=str(data), write_json=True)
    publications, records = {}, []
    for name, overrides in CASES:
        directory = output/name
        directory.mkdir()
        for filename in DATA_FILES:
            (directory/filename).symlink_to(Path('../data')/filename)
        _, manifest = generate_input(structure, replace(common, **overrides))
        if manifest['basis_validation']['status'] != 'data_checked':
            raise ValueError('Actual selected basis/potential entries must be checked')
        text = portable_input(manifest)
        publications[directory/'water.inp'] = text
        publications[directory/'water.inp.json'] = json_text(manifest)
        record = {'id': name, 'input': f'{name}/water.inp',
                  'sidecar': f'{name}/water.inp.json',
                  'input_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                  'generator_input_sha256': manifest['input_sha256'],
                  'deployment_change': 'Only checked basis/potential rows rebased to case-local data symlinks',
                  'requested_settings': manifest['settings'],
                  'method': 'DFT/PBE/GPW/GTH-PBE; Gamma; no dispersion',
                  'spin_treatment': 'UKS' if overrides['multiplicity'] == 2 else 'RKS',
                  'explicit_electron_count': manifest['explicit_electron_count'],
                  'expected_requests': {'density': manifest['density_output'],
                                        **manifest['extra_cube_output']},
                  'expected_frontier_channels': frontier_request(manifest),
                  'checks_status': 'pending', 'warnings': manifest['warnings']}
        record.update(dict.fromkeys(PENDING_FIELDS))
        records.append(record)
    checkout = Path(__file__).resolve().parents[2]
    protocol = checkout/'docs/cube-native-validation.md'
    matrix = {'schema_version': SCHEMA_VERSION, 'generator_version': __version__,
              'purpose': 'Preparation only; no CP2K/MPI/Multiwfn execution or scheduler submission',
              'target_cp2k_version': '2026.2', 'actual_binary_identity': None,
              'data_sources': sources, 'staged_data': {name: identity(data/name) for name in DATA_FILES},
              'common_requested_settings': asdict(common), 'geometry': identity(output/'water.xyz'),
              'cases': records,
              'implementation_sources': {str(path.relative_to(checkout)): identity(path)
                                         for path in sorted((checkout/'src/cp2kkit').glob('*.py'))},
              'preparation_source': identity(Path(__file__)), 'validation_protocol': identity(protocol)}
    publications[output/'case-matrix.json'] = json_text(matrix)
    publications[output/'VALIDATION.md'] = protocol.read_text(encoding='utf-8')
    with staged_files(publications) as streams:
        for stream, text in zip(streams, publications.values()):
            stream.write(text)
    print(f'Prepared {len(records)} inputs in {output}; no execution or submission.')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path, help='Actual CP2K data directory')
    parser.add_argument('--output', required=True, type=Path, help='Entirely new directory; parent must exist')
    args = parser.parse_args()
    prepare(args.data_dir, args.output)


if __name__ == '__main__':
    main()
