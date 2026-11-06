"""Plane averages on native scalar-CUBE grids; no interpolation or charge partition.

An axis selects a grid index, not necessarily a Cartesian direction. The other
two vectors span the averaging plane; project distances onto its oriented normal.
"""
import csv
import hashlib
import math
from pathlib import Path

from . import __version__
from .cube import CubeReader, Statistics, Sum, finite
from .errors import KitError
from .io import json_text, staged_files
from .models import SCHEMA_VERSION
from .structure import BOHR_TO_ANGSTROM

MAX_PLANES = 100000
FIELDS = ('index', 'distance_angstrom', 'mean_density_e_per_angstrom3',
          'slab_electrons', 'cumulative_electrons')


def planar_profile(path, axis='z', options=None):
    """Consume a cube once, retaining O(number of selected-axis planes) sums.

    Each sample has full voxel weight, matching cube-check/cube-diff. Cumulative
    integrals include the current plane's slab, and start at the CUBE origin,
    with no periodic recentering, endpoint weighting or baseline normalization.
    """
    if axis not in ('x', 'y', 'z'):
        raise KitError('Plane axis must be x, y or z (native grid index)')
    selected = ('x', 'y', 'z').index(axis)
    with CubeReader(path, options) as cube:
        if cube.scalar_type not in {'electron-density', 'electron-density-difference',
                                    'spin-density', 'spin-density-difference'}:
            raise KitError('Plane averaging requires known electron/spin density semantics')
        grid = cube.canonical_grid()
        density_factor = finite(cube.density_factor()/BOHR_TO_ANGSTROM**3, 'density conversion')
        vectors = [[finite(v*BOHR_TO_ANGSTROM, 'step conversion') for v in row]
                   for row in grid['vectors']]
        origin = [finite(v*BOHR_TO_ANGSTROM, 'origin conversion') for v in grid['origin']]
        n = cube.shape[selected]
        if n > MAX_PLANES:
            raise KitError(f'Plane profile exceeds {MAX_PLANES} planes on selected axis')
        others = [i for i in range(3) if i != selected]
        a, b = (vectors[i] for i in others)
        cross = [finite(a[1]*b[2]-a[2]*b[1], 'plane cross product'),
                 finite(a[2]*b[0]-a[0]*b[2], 'plane cross product'),
                 finite(a[0]*b[1]-a[1]*b[0], 'plane cross product')]
        area_step = finite(math.hypot(*cross), 'plane area')
        if area_step == 0:
            raise KitError('Degenerate averaging plane after unit conversion')
        normal = [v/area_step for v in cross]
        projection = finite(math.fsum(v*w for v, w in zip(normal, vectors[selected])), 'plane spacing')
        if projection < 0:
            normal = [-v for v in normal]
        spacing = abs(projection)
        if spacing == 0:
            raise KitError('Zero perpendicular plane spacing after unit conversion')
        points = math.prod(cube.shape[i] for i in others)
        area = finite(area_step*points, 'quadrature plane area')
        offset = finite(math.fsum(v*w for v, w in zip(origin, normal)), 'origin projection')
        sums = [Sum() for _ in range(n)]
        stats = Statistics()
        divisor = math.prod(cube.shape[selected+1:])
        for index, value in enumerate(cube.values()):
            sums[(index//divisor) % n].add(value)
            stats.add(value)
        cumulative = Sum()
        rows = []
        for index, total in enumerate(sums):
            mean = finite(total.value()/points*density_factor, 'plane mean density')
            # Reuse the exact voxel/unit quadrature of cube-check, also for skew grids.
            electrons = cube.integral(total.value())['value']
            cumulative.add(electrons)
            rows.append({'index': index, 'distance_angstrom': finite(offset+index*spacing, 'plane position'),
                         'mean_density_e_per_angstrom3': mean, 'slab_electrons': electrons,
                         'cumulative_electrons': cumulative.value()})
        source_report = cube.report(stats)
    warnings = list(source_report['warnings']) + [
        'Native grid-index planes, not Cartesian cuts for general skew cells; no interpolation.',
        'Cumulative integral includes each full slab from the CUBE origin; its offset is origin-dependent.',
        'Electron accumulation is positive; electron-number integrals are not electric charge or atomic/fragment charge transfer.',
        'Spin fields integrate alpha-minus-beta excess electrons; not an atomic charge partition.',
    ]
    return {'schema_version': SCHEMA_VERSION,
            'generator': {'name': 'cp2kkit', 'version': __version__},
            'operation': 'planar_density_profile', 'input': source_report,
            'axis': axis, 'axis_semantics': 'native CUBE grid index, zero-based planes',
            'normal_cartesian': normal, 'plane_spacing_angstrom': spacing,
            'quadrature_plane_area_angstrom2': area, 'origin_projection_angstrom': offset,
            'density_unit': 'e/angstrom^3', 'integral_unit': 'electron',
            'cumulative_convention': 'sum of full sampled slabs through current plane, from input origin',
            'total_integral_electrons': cumulative.value(), 'planes': rows,
            'warnings': warnings, 'validation': {'calculation_settings_verified': False,
                                                'charge_transfer_verified': False}}


def write_planar_profile(path, output, axis='z', options=None):
    """Publish CSV and provenance JSON together, exclusively, after complete parsing."""
    output = Path(output)
    sidecar = Path(str(output)+'.json')
    with staged_files([output, sidecar]) as (stream, manifest_stream):
        report = planar_profile(path, axis, options)
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(FIELDS)
        for row in report['planes']:
            writer.writerow([row['index'], *(format(row[key], '.17g') for key in FIELDS[1:])])
        stream.flush()
        digest = hashlib.sha256()
        with open(stream.name, 'rb') as raw:
            for chunk in iter(lambda: raw.read(1024*1024), b''):
                digest.update(chunk)
        report['output'] = {'path': str(output.resolve()), 'sha256': digest.hexdigest(),
                            'columns': list(FIELDS)}
        manifest_stream.write(json_text(report))
    return report
