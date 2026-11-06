"""Prepare three fixed-geometry adsorption density bundles; never run or submit CP2K.

Constructed h-BN models are functional smoke tests, not optimized structures or
converged adsorption models. All lengths are angstrom. No external geometry library.
"""
import argparse
import hashlib
import math
import shutil
from pathlib import Path

from cp2kkit import __version__
from cp2kkit.density_workflow import generate_difference, write_difference
from cp2kkit.inputgen import InputSettings
from cp2kkit.io import json_text, new_file
from cp2kkit.models import SCHEMA_VERSION
from cp2kkit.structure import read_structure

DATA_FILES = ('BASIS_MOLOPT', 'GTH_POTENTIALS')


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
            'size_bytes': len(raw)}


def save(path, text):
    with new_file(path) as stream:
        stream.write(text)


def geometries():
    """3x3 primitive monolayer h-BN, a=2.50 A, surface at z=6 A."""
    a = 2.50
    h = math.sqrt(3)*a/2
    cell = ((3*a, 0., 0.), (1.5*a, 3*h, 0.), (0., 0., 18.))
    slab = []
    for i in range(3):
        for j in range(3):
            x, y = i*a+j*a/2, j*h
            slab.extend([('B', x, y, 6.), ('N', x+a/2, y+h/3, 6.)])
    # Molecular geometries/poses are deliberately fixed, neutral singlets.
    x, y, z = 3.75, h, 9.20
    molecules = {
        'water': [('O', x, y, z), ('H', x+.757, y, z+.586), ('H', x-.757, y, z+.586)],
        'ammonia': [('N', x, y, z), ('H', x+.938, y, z+.381),
                    ('H', x-.469, y+.812, z+.381), ('H', x-.469, y-.812, z+.381)],
        'carbon-dioxide': [('C', x, y, z), ('O', x-1.16, y, z), ('O', x+1.16, y, z)],
    }
    for name, molecule in molecules.items():
        atoms = slab+molecule
        lattice = ' '.join(f'{v:.10f}' for row in cell for v in row)
        text = (f'{len(atoms)}\nLattice="{lattice}" Properties=species:S:1:pos:R:3 '
                'pbc="T T T"\n')
        text += ''.join(f'{el} {px:.10f} {py:.10f} {pz:.10f}\n' for el, px, py, pz in atoms)
        yield name, text


def portable_input(component):
    """Rebase only the two checked data references for deployment; retain source JSON."""
    text = component['input_text']
    for keyword, filename in (('BASIS_SET_FILE_NAME', 'BASIS_MOLOPT'),
                              ('POTENTIAL_FILE_NAME', 'GTH_POTENTIALS')):
        rows = [row for row in text.splitlines() if row.strip().startswith(keyword+' ')]
        if len(rows) != 1 or Path(rows[0].strip().split(maxsplit=1)[1]).name != filename:
            raise ValueError(f'Unexpected generated data reference: {keyword}')
        text = text.replace(rows[0]+'\n', f'    {keyword} data/{filename}\n', 1)
    return text


def prepare(data_dir, output):
    data_dir, output = Path(data_dir).resolve(), Path(output).absolute()
    sources = {name: identity(data_dir/name) for name in DATA_FILES}
    output.mkdir()  # Exclusive; failed preparations are retained for inspection.
    data = output/'data'
    data.mkdir()
    for name in DATA_FILES:
        with (data_dir/name).open('rb') as source, new_file(data/name, binary=True) as target:
            shutil.copyfileobj(source, target)
        if identity(data/name)['sha256'] != sources[name]['sha256']:
            raise ValueError(f'Data changed while staging: {name}')
    records = []
    for name, text in geometries():
        directory = output/name
        directory.mkdir()
        save(directory/'adsorption.extxyz', text)
        structure = read_structure(directory/'adsorption.extxyz')
        settings = InputSettings(project=name, functional='PBE', basis='molopt-sr-dzvp',
                                 periodic='XYZ', charge=0, multiplicity=1, scf='ot',
                                 cutoff=400., rel_cutoff=55., eps_scf=1e-7,
                                 max_scf=25, max_outer_scf=20,
                                 data_dir=str(data),
                                 density_difference=True, fragment_a_indices='1-18',
                                 fragment_a_charge=0, fragment_a_multiplicity=1,
                                 fragment_b_charge=0, fragment_b_multiplicity=1,
                                 cube_stride=(1, 1, 1), write_json=True)
        _, manifest = generate_difference(structure, settings)
        write_difference(structure, settings, directory/'density.inp')
        components = manifest['density_difference']['components']
        for key, filename in (('whole', 'density.inp'), ('fragment_a', 'density-fragment-A.inp'),
                              ('fragment_b', 'density-fragment-B.inp')):
            run = directory/key
            run.mkdir()
            save(run/'density.inp', portable_input(components[key]))
            (run/'data').symlink_to(Path('../../data'), target_is_directory=True)
            records.append({'model': name, 'component': key,
                            'input': str((run/'density.inp').relative_to(output)),
                            'input_sha256': identity(run/'density.inp')['sha256'],
                            'generator_input_sha256': components[key]['input_sha256'],
                            'deployment_change': 'Only checked basis/potential references rebased to case-local data/ links',
                            'expected_electrons': components[key]['explicit_electron_count'],
                            'process_exit_status': None, 'scf_converged': None})
    save(output/'case-matrix.json', json_text({
        'schema_version': SCHEMA_VERSION, 'generator_version': __version__,
        'target_cp2k_version': '2026.2', 'data_sources': sources, 'cases': records,
        'preparation_source': identity(Path(__file__)),
        'purpose': 'Fixed-geometry density workflow smoke test; preparation only',
        'model': '3x3 h-BN monolayer, a=2.50 angstrom, 18 angstrom XYZ vacuum cell; adsorbate at z=9.20 angstrom',
        'limitations': ['Not optimized; no adsorption energy or charge-transfer accuracy claim',
                        'Gamma only, no k-point/cell/basis/cutoff convergence',
                        'PBE without dispersion or surface dipole correction; no ghosts',
                        'Verify actual SCF convergence, clean exit, cube grids and integrals separately']}))
    print(f'Prepared {len(records)} inputs in {output}; no execution or submission.')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='Entirely new directory')
    args = parser.parse_args()
    prepare(args.data_dir, args.output)


if __name__ == '__main__':
    main()
