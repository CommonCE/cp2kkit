"""Hand-computable synthetic CUBE tests, NOT CP2K calculation results.

Fields are constructed in temporary directories; no licensed/real CUBE fixture
was available in tests/ or the authorized test-workspace at implementation time.
"""
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import main
from cp2kkit.cube import CubeOptions, CubeReader, MAX_LINE_BYTES, check_cube, diff_cubes
from cp2kkit.errors import KitError, OutputExists, ParseError
from cp2kkit.io import staged_files
from cp2kkit.structure import BOHR_TO_ANGSTROM


def synthetic_cube(values, shape=(2, 1, 2), vectors=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                   origin=(0, 0, 0), atoms=1, comments=("-Quickstep-", "ELECTRON DENSITY"), nval=None):
    # Numeric expectations in tests are independent of the production serializer.
    rows = list(comments)
    rows.append(f"{atoms} " + " ".join(str(v) for v in origin) + (" " + str(nval) if nval is not None else ""))
    rows.extend(str(n) + " " + " ".join(str(v) for v in row) for n, row in zip(shape, vectors))
    rows.extend("  1  0.000000  0.0  0.0  0.0" for _ in range(max(atoms, 0)))
    rows.append(" ".join(str(v) for v in values))
    return "\n".join(rows) + "\n"


class CubeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def cube(self, name, values=(1, 2, 3, 4), **kwargs):
        path = self.dir / name
        path.write_text(synthetic_cube(values, **kwargs), encoding="utf-8")
        return path

    def test_cp2k_header_stats_hash_zero_atom_field(self):
        p = self.cube("cp2k.cube")
        r = check_cube(p)
        self.assertEqual(r["comments"], ["-Quickstep-", "ELECTRON DENSITY"])
        self.assertEqual(r["atoms"][0]["atom_field"], 0)
        self.assertEqual(r["source"]["sha256"], hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(r["source"]["size_bytes"], p.stat().st_size)
        self.assertEqual(r["shape"], [2, 1, 2])
        self.assertEqual(r["scalar_type"], "electron-density")
        self.assertEqual(r["scalar_unit"], "e/bohr^3")
        self.assertEqual(r["statistics"]["minimum"], 1)
        self.assertEqual(r["statistics"]["maximum"], 4)
        self.assertEqual(r["statistics"]["sum"], 10)
        self.assertEqual(r["statistics"]["integral"]["value"], 10)
        self.assertEqual(r["statistics"]["integral"]["unit"], "electron")
        self.assertFalse(r["validation"]["calculation_settings_verified"])

    def test_nonorthogonal_constant_field(self):
        # det([1,0,0], [1,2,0], [0,1,3])=6, 8 samples of value 2 -> 96.
        p = self.cube("shear.cube", [2]*8, shape=(2, 2, 2), vectors=((1, 0, 0), (1, 2, 0), (0, 1, 3)))
        r = check_cube(p)
        self.assertEqual(r["voxel_volume"]["value"], 6)
        self.assertEqual(r["statistics"]["integral"]["value"], 96)
        self.assertEqual(r["sample_span_vectors"][1], [1, 2, 0])
        self.assertEqual(r["quadrature_span_vectors"][1], [2, 4, 0])

    def test_left_handed_grid_and_fortran_exponents(self):
        p = self.cube("d.cube", ["1D+00", "2d+00", "-1.0D+00", "0.0E+00"], vectors=((1, 0, 0), (0, 1, 0), (0, 0, -2)))
        r = check_cube(p)
        self.assertEqual(r["voxel_volume"]["value"], 2)
        self.assertEqual(r["statistics"]["integral"]["value"], 4)
        self.assertEqual(r["statistics"]["positive_integral"]["value"], 6)
        self.assertEqual(r["statistics"]["negative_integral"]["value"], -2)

    def test_spin_signed_values(self):
        p = self.cube("s.cube", [1, -1, 0, 2], comments=("-Quickstep-", "SPIN DENSITY"))
        r = check_cube(p)
        self.assertEqual(r["scalar_type"], "spin-density")
        self.assertEqual(r["statistics"]["integral"]["quantity"], "spin_excess_electrons")
        self.assertEqual(r["statistics"]["integral"]["value"], 2)

    def test_generic_not_assumed_electron_density(self):
        p = self.cube("g.cube", comments=("Synthetic generic field", "OUTER LOOP: X, MIDDLE LOOP: Y, INNER LOOP: Z"))
        r = check_cube(p)
        self.assertEqual(r["length_unit"], "bohr")
        self.assertEqual(r["scalar_type"], "unknown")
        self.assertEqual(r["statistics"]["integral"]["quantity"], "raw_numerical_integral")
        r = check_cube(p, CubeOptions(scalar_type="electron-density", scalar_unit="e/bohr^3"))
        self.assertEqual(r["statistics"]["integral"]["unit"], "electron")
        self.assertIn("explicit user", r["interpretation"]["scalar_basis"])
        r = check_cube(p, CubeOptions(scalar_unit="e/bohr^3"))
        self.assertEqual(r["statistics"]["integral"]["quantity"], "raw_numerical_integral")

    def test_potential_and_total_charge_titles_are_not_electron_density(self):
        for title in ('TOTAL DENSITY', 'HARTREE POTENTIAL', 'No Title'):
            p = self.cube('not-electronic.cube', comments=('-Quickstep-',title))
            r = check_cube(p)
            self.assertEqual(r['scalar_type'], 'unknown')
            self.assertEqual(r['statistics']['integral']['quantity'], 'raw_numerical_integral')
            with self.assertRaises(KitError):
                diff_cubes([p,p], self.dir/'no.cube')

    def test_negative_counts_are_explicit_convention(self):
        p = self.cube("negative.cube", [2]*4, shape=(-2, -1, -2), comments=("synthetic", "unknown field"))
        self.assertIsNone(check_cube(p)["length_unit"])
        r = check_cube(p, CubeOptions(dialect="signed", scalar_type="electron-density", scalar_unit="e/angstrom^3"))
        self.assertEqual(r["length_unit"], "angstrom")
        self.assertEqual(r["shape"], [2, 1, 2])
        self.assertAlmostEqual(r["statistics"]["integral"]["value"], 8)
        r = check_cube(p, CubeOptions(length_unit="bohr"))
        self.assertEqual(r["length_unit"], "bohr")
        with self.assertRaises(ParseError):
            check_cube(p, CubeOptions(dialect="gaussian"))

    def test_density_and_space_units_can_differ(self):
        p = self.cube("angstrom.cube", [2]*4, shape=(-2, -1, -2), comments=("synthetic", "density"))
        r = check_cube(p, CubeOptions(dialect="signed", scalar_type="electron-density", scalar_unit="e/bohr^3"))
        self.assertAlmostEqual(r["statistics"]["integral"]["value"], 8/BOHR_TO_ANGSTROM**3)

    def test_bad_data_counts_nonfinite(self):
        for values in ((1, 2, 3), (1, 2, 3, 4, 5), (1, 2, 3, "nan"), (1, 2, 3, "Inf"), (1, 2, 3, "BAD")):
            with self.subTest(values=values), self.assertRaises(ParseError):
                check_cube(self.cube("bad.cube", values))

    def test_unsupported_variants_and_bad_grid(self):
        cases = [dict(atoms=-1), dict(nval=2), dict(shape=(0, 1, 2)), dict(shape=(-2, 1, 2)),
                 dict(vectors=((1, 0, 0), (1, 0, 0), (0, 0, 1))),
                 dict(origin=("NaN", 0, 0)), dict(comments=("test", "OUTER LOOP: Z, MIDDLE LOOP: Y, INNER LOOP: X"))]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ParseError):
                check_cube(self.cube("bad.cube", **kwargs))

    def test_header_truncation_and_invalid_atom_record(self):
        for text in ("", "one comment\n", "a\nb\n", synthetic_cube([1,2,3,4]).replace("1  0.000000", "x  0.000000")):
            p = self.dir / "bad.cube"
            p.write_text(text)
            with self.assertRaises(ParseError):
                check_cube(p)
        p = self.cube("good.cube", nval=1, atoms=0)
        self.assertEqual(check_cube(p)["atom_count"], 0)

    def test_bounded_lines_and_invalid_encoding(self):
        p = self.dir / "long.cube"
        p.write_bytes(b"x"*(MAX_LINE_BYTES+1) + b"\n")
        with self.assertRaises(ParseError):
            check_cube(p)
        p.write_bytes(b"\xff\n")
        with self.assertRaises(ParseError):
            check_cube(p)

    def test_stream_order_compensated_sum_and_whitespace_hash(self):
        p = self.cube("order.cube", [1e16, 1, -1e16, 2])
        with p.open("a") as f:
            f.write("\n  \t\n")
        with CubeReader(p) as cube:
            self.assertEqual(list(cube.values()), [1e16, 1, -1e16, 2])
            self.assertEqual(cube.source["sha256"], hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(check_cube(p)["statistics"]["sum"], 3)

    def test_conflicting_assertions_and_cp2k_negative_counts(self):
        p = self.cube("known.cube")
        for options in (CubeOptions(length_unit="angstrom"), CubeOptions(scalar_type="spin-density"),
                        CubeOptions(scalar_unit="e/angstrom^3")):
            with self.assertRaises(KitError):
                check_cube(p, options)
        p = self.cube("bad.cube", shape=(-2, -1, -2))
        with self.assertRaises(ParseError):
            check_cube(p)

    def test_mutation_detected(self):
        p = self.cube("changing.cube")
        with CubeReader(p) as cube:
            it = cube.values()
            next(it)
            with p.open("a") as f:
                f.write(" \n")
            with self.assertRaisesRegex(ParseError, "changed during reading"):
                list(it)

    def inputs(self):
        return [self.cube("AB.cube", [4, 1, 5, 0], atoms=3),
                self.cube("A.cube", [1, 1, 2, 1], atoms=2),
                self.cube("B.cube", [2, 0, 1, 1], atoms=1)]

    def test_difference_different_atoms_integrals_and_roundtrip(self):
        paths = self.inputs()
        before = [p.read_bytes() for p in paths]
        out = self.dir / "delta.cube"
        m = diff_cubes(paths, out)
        with CubeReader(out) as reader:
            self.assertEqual(list(reader.values()), [1, 0, 2, -2])
            self.assertEqual(reader.atom_count, 3)
            self.assertEqual(reader.atom_lines, ["  1  0.000000  0.0  0.0  0.0"]*3)
        check = check_cube(out)
        self.assertEqual(check["scalar_type"], "electron-density-difference")
        self.assertEqual(m["statistics"]["integral"]["value"], 1)
        self.assertEqual(m["statistics"]["positive_integral"]["value"], 3)
        self.assertEqual(m["statistics"]["negative_integral"]["value"], -2)
        self.assertEqual([r["statistics"]["integral"]["value"] for r in m["inputs"]], [10, 5, 4])
        self.assertEqual(m["output"]["sha256"], hashlib.sha256(out.read_bytes()).hexdigest())
        self.assertEqual(json.loads(Path(str(out)+".json").read_text()), m)
        self.assertEqual(before, [p.read_bytes() for p in paths])
        self.assertTrue(any("Nonzero difference" in w for w in m["warnings"]))
        self.assertEqual(m["grid_deviations"][0]["max_origin_deviation_bohr"], 0)

    def test_many_fragments(self):
        paths = self.inputs() + [self.cube("C.cube", [.5]*4)]
        m = diff_cubes(paths, self.dir / "delta.cube")
        self.assertEqual(m["expression"], "rho[0] - rho[1] - rho[2] - rho[3]")
        self.assertEqual(m["statistics"]["integral"]["value"], -1)
        self.assertEqual(m["statistics"]["positive_integral"]["value"], 2)
        self.assertEqual(m["statistics"]["negative_integral"]["value"], -3)

    def test_spin_difference_and_type_mismatch(self):
        p = self.cube("spin.cube", [1,-1,1,-1], comments=("-Quickstep-", "SPIN DENSITY"))
        q = self.cube("spin2.cube", [0]*4, comments=("-Quickstep-", "SPIN DENSITY"))
        m = diff_cubes([p,q], self.dir / "delta.cube")
        self.assertEqual(m["output"]["scalar_type"], "spin-density-difference")
        self.assertEqual(m["statistics"]["integral"]["value"], 0)
        with self.assertRaises(KitError):
            diff_cubes([p,self.cube("electron.cube")], self.dir / "bad.cube")

    def test_units_normalized_without_grid_interpolation(self):
        a = BOHR_TO_ANGSTROM
        p = self.cube("bohr.cube", [4]*4)
        q = self.cube("ang.cube", [1/a**3]*4, shape=(-2,-1,-2), vectors=((a,0,0),(0,a,0),(0,0,a)),
                      comments=("synthetic", "density"))
        opts = [CubeOptions(), CubeOptions(dialect="signed", scalar_type="electron-density", scalar_unit="e/angstrom^3")]
        m = diff_cubes([p,q], self.dir / "delta.cube", opts)
        self.assertAlmostEqual(m["inputs"][1]["statistics"]["integral"]["value"], 4)
        self.assertAlmostEqual(m["statistics"]["integral"]["value"], 12)
        out = self.dir / "delta-ang.cube"
        diff_cubes([q,p], out, list(reversed(opts)))
        r = check_cube(out)
        self.assertEqual(r["length_unit"], "angstrom")
        self.assertAlmostEqual(r["statistics"]["integral"]["value"], -12)

    def test_grid_mismatches_and_tolerance_boundary(self):
        ref = self.cube("AB.cube")
        for kw in (dict(shape=(1,2,2)), dict(origin=(1e-4,0,0)), dict(vectors=((1.0001,0,0),(0,1,0),(0,0,1)))):
            with self.subTest(kw=kw), self.assertRaises(KitError):
                diff_cubes([ref,self.cube("A.cube", **kw)], self.dir / "bad.cube")
            self.assertFalse((self.dir / "bad.cube").exists())
        for field in ("origin", "vectors"):
            kw = {"origin": (1e-6,0,0)} if field == "origin" else {"vectors": ((1,1e-6,0),(0,1,0),(0,0,1))}
            m = diff_cubes([ref,self.cube("A.cube", **kw)], self.dir / f"{field}.cube", grid_atol=1e-6)
            self.assertAlmostEqual(m["grid_deviations"][0][f"max_{field}_deviation_bohr"], 1e-6)
            kw = {"origin": (1.001e-6,0,0)} if field == "origin" else {"vectors": ((1,1.001e-6,0),(0,1,0),(0,0,1))}
            with self.assertRaises(KitError):
                diff_cubes([ref,self.cube("A.cube", **kw)], self.dir / "fail.cube", grid_atol=1e-6)

    def test_unknown_semantics_and_units_refused(self):
        p = self.cube("u.cube", comments=("generic", "field"))
        for opts in (CubeOptions(), CubeOptions(scalar_type="electron-density"), CubeOptions(scalar_unit="e/bohr^3")):
            with self.assertRaises(KitError):
                diff_cubes([p,p], self.dir / "bad.cube", opts)
        p = self.cube("negative.cube", comments=("generic", "field"), shape=(-2,-1,-2))
        with self.assertRaises(KitError):
            diff_cubes([p,p], self.dir / "bad.cube", CubeOptions(scalar_type="electron-density", scalar_unit="e/bohr^3"))

    def test_options_and_tolerances_validation(self):
        paths = self.inputs()
        for kw in (dict(grid_atol=-1),dict(grid_rtol=math.nan),dict(integral_atol=math.inf),dict(options=[CubeOptions()])):
            with self.assertRaises(KitError):
                diff_cubes(paths, self.dir / "bad.cube", **kw)
        with self.assertRaises(KitError):
            diff_cubes(paths[:1], self.dir / "bad.cube")

    def test_output_collisions_and_dangling_symlink(self):
        paths = self.inputs()
        out = self.dir / "delta.cube"
        sidecar = Path(str(out)+".json")
        sidecar.write_text("keep me")
        with self.assertRaises(OutputExists):
            diff_cubes(paths, out)
        self.assertFalse(out.exists())
        self.assertEqual(sidecar.read_text(), "keep me")
        sidecar.unlink()  # synthetic temporary test artifact only
        out.symlink_to(self.dir / "absent")
        with self.assertRaises(OutputExists):
            diff_cubes(paths, out)
        self.assertTrue(out.is_symlink())
        out.unlink()
        diff_cubes(paths, out)
        original = out.read_bytes()
        with self.assertRaises(OutputExists):
            diff_cubes(paths, out)
        self.assertEqual(out.read_bytes(), original)

    def test_truncation_and_extra_data_cleanup(self):
        paths = self.inputs()
        for values in ([1,2], [1,2,3,4,5], [1,2,3,math.nan]):
            bad = self.cube("bad-input.cube", values)
            out = self.dir / "bad-output.cube"
            with self.assertRaises(ParseError):
                diff_cubes([paths[0],bad], out)
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out)+".json").exists())
            self.assertFalse(list(self.dir.glob(".*.tmp")))

    def test_stage_write_and_publish_failure_cleanup(self):
        out, side = self.dir / "one", self.dir / "two"
        with self.assertRaises(OSError):
            with staged_files([out,side]) as streams:
                streams[0].write("staged")
                raise OSError("simulated write failure")
        self.assertFalse(out.exists())
        real_link = os.link
        def link(src, dst):
            if Path(dst) in {side, Path(str(out)+".json")}:
                raise OSError("simulated second publication failure")
            real_link(src,dst)
        with patch("cp2kkit.io.os.link", side_effect=link), self.assertRaises(OSError):
            diff_cubes(self.inputs(), out)
        self.assertFalse(out.exists())
        self.assertFalse(Path(str(out)+".json").exists())
        self.assertFalse(list(self.dir.glob(".*.tmp")))
        # Exercise failure on the actual second target.
        with patch("cp2kkit.io.os.link", side_effect=link), self.assertRaises(OSError):
            with staged_files([out,side]) as streams:
                streams[0].write("one")
                streams[1].write("two")
        self.assertFalse(out.exists())
        self.assertFalse(side.exists())

    def test_actual_cube_and_json_write_failures_cleanup(self):
        paths = self.inputs()
        out = self.dir/'delta.cube'
        def fail_header(stream, *args):
            stream.write('partial header')
            raise OSError('simulated CUBE write failure')
        for target, side_effect in (('cp2kkit.cube._write_header', fail_header),
                                    ('cp2kkit.cube.json_text', OSError('simulated JSON write failure'))):
            with patch(target, side_effect=side_effect), self.assertRaises(OSError):
                diff_cubes(paths,out)
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out)+'.json').exists())
            self.assertFalse(list(self.dir.glob('.*.tmp')))

    def test_rollback_does_not_remove_replaced_user_inode(self):
        out, side = self.dir/'one', self.dir/'two'
        real_link = os.link
        def link(src,dst):
            if Path(dst) == side:
                out.rename(self.dir/'old-published')
                out.write_text('new user file')
                raise OSError('simulated publication failure')
            real_link(src,dst)
        with patch('cp2kkit.io.os.link',side_effect=link), self.assertRaises(OSError):
            with staged_files([out,side]) as streams:
                streams[0].write('ours')
                streams[1].write('ours')
        self.assertEqual(out.read_text(),'new user file')
        self.assertFalse(side.exists())

    def test_publication_race_preserves_existing_file(self):
        paths = self.inputs()
        out = self.dir / "delta.cube"
        side = Path(str(out)+".json")
        real_link = os.link
        def link(src,dst):
            if Path(dst) == side:
                side.write_text("racing user's file")
            real_link(src,dst)
        with patch("cp2kkit.io.os.link", side_effect=link), self.assertRaises(OutputExists):
            diff_cubes(paths,out)
        self.assertFalse(out.exists())
        self.assertEqual(side.read_text(), "racing user's file")
        self.assertFalse(list(self.dir.glob(".*.tmp")))

    def test_cli_success_errors_and_exclusive_json(self):
        paths = self.inputs()
        out = self.dir / "delta.cube"
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(["cube-check",str(paths[0])]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["statistics"]["sum"], 10)
        with redirect_stderr(io.StringIO()):
            check = self.dir / "check.json"
            self.assertEqual(main(["cube-check",str(paths[0]),"-o",str(check)]), 0)
            self.assertEqual(main(["cube-check",str(paths[0]),"-o",str(check)]), 5)
            args = ["cube-diff",*map(str,paths),"-o",str(out)]
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args), 5)
            self.assertEqual(main(["cube-diff",str(paths[0]),"-o",str(self.dir/'x')]), 2)
            bad = self.cube("invalid.cube", [1,2])
            self.assertEqual(main(["cube-check",str(bad)]), 4)
            self.assertEqual(main(["cube-check",str(self.dir/'missing')]), 2)
            self.assertEqual(main(["cube-diff",*map(str,paths),"--input-length-units","bohr","-o",str(self.dir/'x')]), 2)

    def test_cli_mixed_units_and_incompatible_grids(self):
        p = self.cube('AB.cube')
        q = self.cube('generic.cube', [1]*4, comments=('generic','density'))
        out = self.dir/'delta.cube'
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['cube-diff',str(p),str(q),'-o',str(out),
                                   '--scalar-type','electron-density',
                                   '--input-scalar-units','auto','e/bohr^3']),0)
            self.assertEqual(main(['cube-diff',str(p),str(self.cube('shifted.cube',origin=(.1,0,0))),
                                   '-o',str(self.dir/'bad.cube')]),2)

    def test_cli_subprocess(self):
        p = self.cube("AB.cube")
        proc = subprocess.run([sys.executable,"-m","cp2kkit","cube-check",str(p)], capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["expected_value_count"],4)


if __name__ == "__main__":
    unittest.main()
