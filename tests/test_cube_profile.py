"""Hand-computable fields test plane geometry/quadrature, not scientific accuracy."""
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import main
from cp2kkit.cube import CubeOptions, diff_cubes
from cp2kkit.cube_profile import planar_profile, write_planar_profile
from cp2kkit.errors import KitError, OutputExists, ParseError
from cp2kkit.structure import BOHR_TO_ANGSTROM as B
from tests.test_cube import synthetic_cube


class CubeProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cube(self, values=(1, 2, 3, 4), **kwargs):
        path = self.root/'field.cube'
        path.write_text(synthetic_cube(values, **kwargs), encoding='utf-8')
        return path

    def test_all_axes_and_integral(self):
        path = self.cube()
        for axis, means, slabs in [('x', [1.5, 3.5], [3, 7]),
                                   ('y', [2.5], [10]), ('z', [2, 3], [4, 6])]:
            with self.subTest(axis=axis):
                report = planar_profile(path, axis)
                self.assertEqual(report['axis'], axis)
                self.assertEqual(report['total_integral_electrons'], 10)
                self.assertEqual(report['planes'][-1]['cumulative_electrons'], 10)
                self.assertEqual([r['slab_electrons'] for r in report['planes']], slabs)
                for row, mean in zip(report['planes'], means):
                    self.assertAlmostEqual(row['mean_density_e_per_angstrom3']*B**3, mean)
                self.assertEqual(report['input']['source']['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_skew_plane_and_left_handed_normal(self):
        path = self.cube([2]*8, shape=(2, 2, 2), origin=(0, 0, 4),
                         vectors=((1, 0, 0), (1, 2, 0), (1, 1, -3)))
        report = planar_profile(path)
        self.assertEqual(report['normal_cartesian'], [0, 0, -1])
        self.assertAlmostEqual(report['plane_spacing_angstrom'], 3*B)
        self.assertAlmostEqual(report['quadrature_plane_area_angstrom2'], 8*B**2)
        self.assertAlmostEqual(report['planes'][0]['distance_angstrom'], -4*B)
        self.assertAlmostEqual(report['planes'][1]['distance_angstrom'], -B)
        self.assertEqual(report['total_integral_electrons'], 96)
        for row in report['planes']:
            self.assertAlmostEqual(row['mean_density_e_per_angstrom3'] * report['quadrature_plane_area_angstrom2']
                                   * report['plane_spacing_angstrom'], row['slab_electrons'])

    def test_unequal_dimensions_and_all_skew_axes(self):
        # f(i,j,k)=100*i+10*j+k on a 2x3x4 grid: independently
        # known plane means catch axis/stride swaps hidden by equal dimensions.
        values = [100*i+10*j+k for i in range(2) for j in range(3) for k in range(4)]
        path = self.cube(values, shape=(2, 3, 4), origin=(1, -2, 3),
                         vectors=((2, 0, 0), (1, 3, 0), (1, 1, -4)))
        expected = {'x': [11.5, 111.5], 'y': [51.5, 61.5, 71.5],
                    'z': [60, 61, 62, 63]}
        for axis, means in expected.items():
            with self.subTest(axis=axis):
                report = planar_profile(path, axis)
                points = 24//len(means)
                self.assertAlmostEqual(report['total_integral_electrons'], 35424)
                self.assertAlmostEqual(report['quadrature_plane_area_angstrom2'] *
                                       report['plane_spacing_angstrom'], points*24*B**3)
                for index, (row, mean) in enumerate(zip(report['planes'], means)):
                    self.assertAlmostEqual(row['mean_density_e_per_angstrom3']*B**3, mean)
                    self.assertAlmostEqual(row['slab_electrons'], mean*points*24)
                    self.assertAlmostEqual(row['distance_angstrom'],
                                           report['origin_projection_angstrom'] +
                                           index*report['plane_spacing_angstrom'])

    def test_compensated_cancellation_and_negative_spin_integral(self):
        path = self.cube([1e16, 1, -1e16, -2], shape=(1, 1, 4),
                         comments=('-Quickstep-', 'SPIN DENSITY'))
        for axis in ('x', 'y', 'z'):
            with self.subTest(axis=axis):
                report = planar_profile(path, axis)
                self.assertEqual(report['total_integral_electrons'], -1)
                self.assertEqual(report['input']['statistics']['integral']['value'], -1)
        # This is a signed excess-electron integral, not a positive density
        # constraint or an automatically assigned fragment charge.
        self.assertFalse(report['validation']['charge_transfer_verified'])

    def test_integral_overflow_leaves_no_published_files(self):
        path = self.cube([1e307]*4, vectors=((10, 0, 0), (0, 10, 0), (0, 0, 10)))
        with self.assertRaises(ParseError):
            write_planar_profile(path, self.root/'overflow.csv')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['field.cube'])

    def test_rotated_plane(self):
        report = planar_profile(self.cube(vectors=((0, 1, 0), (0, 0, 1), (2, 0, 0))))
        self.assertEqual(report['normal_cartesian'], [1, 0, 0])
        self.assertAlmostEqual(report['plane_spacing_angstrom'], 2*B)
        self.assertEqual(report['total_integral_electrons'], 20)

    def test_signed_angstrom_mixed_density_units(self):
        path = self.cube(shape=(-2, -1, -2), comments=('generic', 'field'))
        report = planar_profile(path, options=CubeOptions('signed', None, 'electron-density', 'e/bohr^3'))
        self.assertAlmostEqual(report['total_integral_electrons'], 10/B**3)
        self.assertAlmostEqual(report['plane_spacing_angstrom'], 1)

    def test_spin_signed_and_zero(self):
        path = self.cube((1, -1, -1, 1), comments=('-Quickstep-', 'SPIN DENSITY'))
        report = planar_profile(path)
        self.assertEqual(report['total_integral_electrons'], 0)
        self.assertEqual([r['slab_electrons'] for r in report['planes']], [0, 0])
        self.assertEqual(report['input']['statistics']['integral']['quantity'], 'spin_excess_electrons')
        self.assertFalse(report['validation']['charge_transfer_verified'])

    def test_difference_roundtrip(self):
        path = self.cube()
        fragment = self.root/'fragment.cube'
        fragment.write_text(synthetic_cube([1, 1, 1, 1]))
        delta = self.root/'delta.cube'
        diff_cubes([path, fragment], delta)
        report = planar_profile(delta)
        self.assertEqual(report['input']['scalar_type'], 'electron-density-difference')
        self.assertEqual(report['total_integral_electrons'], 6)

    def test_native_fixed_width_through_difference_and_profile(self):
        path = self.cube()
        header = path.read_text().splitlines()[:-1]
        path.write_text('\n'.join(header+[' 0.10000E+001-0.20000E+001-0.30000E+001 0.40000E+001'])+'\n')
        fragment = self.root/'zero.cube'
        fragment.write_text(synthetic_cube([0, 0, 0, 0]))
        delta = self.root/'native-delta.cube'
        report = diff_cubes([path, fragment], delta)
        self.assertEqual(report['statistics']['integral']['value'], 0)
        profile = write_planar_profile(delta, self.root/'native.csv')
        self.assertEqual([row['slab_electrons'] for row in profile['planes']], [-2, 2])
        self.assertEqual(profile['total_integral_electrons'], 0)

    def test_csv_json_and_determinism(self):
        path = self.cube()
        output = self.root/'profile.csv'
        report = write_planar_profile(path, output)
        self.assertEqual(report, json.loads(Path(str(output)+'.json').read_text()))
        self.assertEqual(report['output']['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())
        with output.open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(float(rows[-1]['cumulative_electrons']), 10)
        other = self.root/'other.csv'
        write_planar_profile(path, other)
        self.assertEqual(output.read_bytes(), other.read_bytes())
        self.assertEqual(planar_profile(path), planar_profile(path))

    def test_unknown_semantics_units_axis_and_plane_limit(self):
        path = self.cube(comments=('generic', 'field'))
        with self.assertRaises(KitError):
            planar_profile(path)
        with self.assertRaises(KitError):
            planar_profile(path, options=CubeOptions(scalar_type='electron-density'))
        with self.assertRaises(KitError):
            planar_profile(path, 'Z')
        path = self.cube()
        with patch('cp2kkit.cube_profile.MAX_PLANES', 1), self.assertRaises(KitError):
            planar_profile(path)

    def test_partial_nonfinite_extra_data_cleanup(self):
        for values in ((1, 2), (1, 2, 'nan', 4), (1, 2, 3, 4, 5)):
            path = self.cube(values)
            with self.assertRaises(ParseError):
                write_planar_profile(path, self.root/'bad.csv')
            self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['field.cube'])

    def test_collisions_sources_and_dangling_symlinks(self):
        path = self.cube()
        before = path.read_bytes()
        with self.assertRaises(OutputExists):
            write_planar_profile(path, path)
        self.assertEqual(path.read_bytes(), before)
        output = self.root/'profile.csv'
        sidecar = Path(str(output)+'.json')
        sidecar.symlink_to(self.root/'absent')
        with self.assertRaises(OutputExists):
            write_planar_profile(path, output)
        self.assertFalse(output.exists())
        self.assertTrue(sidecar.is_symlink())

    def test_failed_publication_rolls_back(self):
        path = self.cube()
        output = self.root/'profile.csv'
        import os
        link = os.link
        calls = []

        def fail_second(source, destination):
            calls.append(destination)
            if len(calls) == 2:
                raise OSError('simulated sidecar publication failure')
            return link(source, destination)

        with patch('cp2kkit.io.os.link', side_effect=fail_second), self.assertRaises(OSError):
            write_planar_profile(path, output)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['field.cube'])

    def test_cli_and_subprocess(self):
        path = self.cube()
        output = self.root/'cli.csv'
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['cube-planar', str(path), '--axis', 'x', '-o', str(output)]), 0)
            self.assertEqual(main(['cube-planar', str(path), '-o', str(output)]), 5)
        proc = subprocess.run([sys.executable, '-m', 'cp2kkit', 'cube-planar', str(path),
                               '-o', str(self.root/'subprocess.csv')], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, '')


if __name__ == '__main__':
    unittest.main()
