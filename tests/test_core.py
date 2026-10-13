import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from cp2kkit.cli import main
from cp2kkit.discovery import discover, resolve_output
from cp2kkit.errors import AmbiguousProject, KitError, OutputExists, ParseError
from cp2kkit.export import write_csv
from cp2kkit.io import json_text, new_file
from cp2kkit.parser import parse_output
from cp2kkit.plot import plot_run
from cp2kkit.quality import quality_report
from cp2kkit.structure import BOHR_TO_ANGSTROM, read_restart, read_xyz, xyz_text
from contextlib import redirect_stdout, redirect_stderr
from importlib.util import find_spec
from unittest.mock import patch

FIXTURES = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_normal(self):
        run = parse_output(FIXTURES / "normal.out")
        self.assertEqual(run.schema_version, "0.1.0")
        self.assertEqual(run.project, "demo")
        self.assertEqual(run.segments[0].run_type, "ENERGY")
        self.assertAlmostEqual(run.segments[0].final_energy.value, -12.3456789012345)
        self.assertEqual(run.segments[0].final_energy.unit, "hartree")
        self.assertEqual(run.segments[0].wall_time.unit, "s")
        self.assertEqual(run.segments[0].scf_iterations[0].value, 8)
        self.assertIn("XC|Functional", run.segments[0].settings)
        self.assertIsNone(run.exit_status)
        self.assertEqual(quality_report(run)["status"], "passed")

    def test_truncated_never_passes(self):
        run = parse_output(FIXTURES / "truncated.out")
        report = quality_report(run)
        self.assertNotEqual(report["status"], "passed")
        self.assertIsNone(report["segments"][0]["electronic_converged"])
        self.assertTrue(run.segments[0].energies[0].scf_converged)
        self.assertIsNone(report["segments"][0]["geometry_converged"])
        self.assertFalse(report["segments"][0]["energy_usable"])

    def test_unconverged_zero_not_missing(self):
        run = parse_output(FIXTURES / "unconverged.out")
        self.assertEqual(run.segments[0].final_energy.value, 0.0)
        self.assertFalse(run.segments[0].scf_converged)
        self.assertEqual(quality_report(run)["segments"][0]["status"], "failed")
        self.assertIn("WARNING", run.segments[0].diagnostics[0].text)

    def test_step_reset(self):
        run = parse_output(FIXTURES / "restart.out")
        self.assertEqual(len(run.segments), 2)
        self.assertEqual([e.step for e in run.segments[0].energies], [1, 2])
        self.assertEqual([e.step for e in run.segments[1].energies], [1])
        self.assertFalse(run.segments[0].completed)
        self.assertEqual(quality_report(run)["segments"][1]["status"], "passed")
        self.assertNotEqual(quality_report(run)["status"], "passed")

    def test_concatenated_programs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "both.out"
            path.write_text((FIXTURES / "normal.out").read_text() * 2)
            run = parse_output(path)
            self.assertEqual(len(run.segments), 2)
            self.assertIn("software_version", run.segments[1].settings)
            self.assertEqual(run.segments[0].settings["software_version"]["source"]["line"], 1)

    def test_deterministic_and_source_line(self):
        path = FIXTURES / "normal.out"
        first = parse_output(path)
        self.assertEqual(json_text(first.to_dict()), json_text(parse_output(path).to_dict()))
        q = first.segments[0].final_energy
        self.assertEqual(path.read_text().splitlines()[q.source.line-1], q.source.text)
        self.assertEqual(len(first.source["sha256"]), 64)

    def test_csv_units_zero_null(self):
        stream = io.StringIO()
        write_csv(stream, parse_output(FIXTURES / "unconverged.out"))
        rows = list(csv.DictReader(io.StringIO(stream.getvalue())))
        self.assertEqual(rows[0]["unit"], "hartree")
        self.assertEqual(rows[0]["value"], "0.0")
        self.assertEqual(rows[0]["step"], "")
        self.assertTrue(rows[0]["source_line"])

    def test_unknown_run_type(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unknown.out"
            path.write_text((FIXTURES / "normal.out").read_text().replace("Run type ENERGY", "Run type MD"))
            self.assertNotEqual(quality_report(parse_output(path))["status"], "passed")

    def test_missing_and_malformed_energy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.out"
            path.write_text("CP2K| version string: test\nENERGY| Total FORCE_EVAL energy: NaN\n")
            run = parse_output(path)
            self.assertIsNone(run.segments[0].final_energy)
            self.assertTrue(run.parser_warnings)
            path.write_text("CP2K| version string: test\nENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]: 1e999")
            with self.assertRaises(ParseError):
                parse_output(path)

    def test_final_energy_without_scf_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.out"
            text = (FIXTURES / "normal.out").read_text()
            text = text.replace(" PROGRAM ENDED AT", " ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]: -12.4\n PROGRAM ENDED AT")
            path.write_text(text)
            run = parse_output(path)
            self.assertIsNone(run.segments[0].energies[-1].scf_converged)
            self.assertNotEqual(quality_report(run)["status"], "passed")

    def test_failed_geometry_marker_dominates_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geometry.out"
            text = (FIXTURES / "normal.out").read_text().replace("Run type ENERGY", "Run type GEO_OPT")
            text = text.replace(" PROGRAM ENDED AT", " MAXIMUM NUMBER OF OPTIMIZATION STEPS REACHED\n GEOMETRY OPTIMIZATION COMPLETED\n PROGRAM ENDED AT")
            path.write_text(text)
            run = parse_output(path)
            self.assertFalse(run.segments[0].geometry_converged)
            self.assertEqual(quality_report(run)["segments"][0]["status"], "failed")

    def test_numeric_suffix_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.out"
            path.write_text("CP2K| version string: test\nENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]: 1.2broken\n")
            self.assertIsNone(parse_output(path).segments[0].final_energy)

    def test_malformed_later_energy_cannot_use_previous_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mixed.out"
            text = (FIXTURES / "normal.out").read_text().replace(
                " PROGRAM ENDED AT", " ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]: NaN\n PROGRAM ENDED AT")
            path.write_text(text)
            run = parse_output(path)
            self.assertIsNotNone(run.segments[0].final_energy)
            self.assertEqual(len(run.segments[0].unparsed_energy_records), 1)
            self.assertFalse(quality_report(run)["segments"][0]["energy_usable"])

    def test_invalid_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.out"
            path.write_bytes(b"CP2K|\xff")
            with self.assertRaises(ParseError):
                parse_output(path)

    def test_not_cp2k(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.out"
            path.write_text("some other program")
            with self.assertRaises(ParseError):
                parse_output(path)

    def test_earlier_scf_failure_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.out"
            path.write_text((FIXTURES / "normal.out").read_text().replace(
                " SCF run converged", " SCF run NOT converged\n SCF run converged"))
            self.assertNotEqual(quality_report(parse_output(path))["status"], "passed")

    def test_error_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.out"
            path.write_text((FIXTURES / "normal.out").read_text() + "*** ERROR: synthetic failure\n")
            self.assertEqual(quality_report(parse_output(path))["segments"][0]["status"], "failed")


class DiscoveryTests(unittest.TestCase):
    def test_missing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KitError):
                resolve_output(directory)

    def test_multiple_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = (FIXTURES / "normal.out").read_text()
            (root / "b.out").write_text(text.replace("Project name demo", "Project name beta"))
            (root / "a.out").write_text(text)
            (root / "other.log").write_text("Not CP2K")
            (root / "demo-pos-1.xyz").write_text("structure placeholder")
            self.assertEqual([p.name for p in discover(root)], ["beta", "demo"])
            with self.assertRaises(AmbiguousProject):
                resolve_output(root)
            self.assertEqual(resolve_output(root, "demo").name, "a.out")
            self.assertEqual(len(discover(root)[1].structures), 1)

    def test_same_project_two_outputs_requires_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["a.out", "b.out"]:
                (root / name).write_text((FIXTURES / "normal.out").read_text())
            with self.assertRaises(AmbiguousProject):
                resolve_output(root, "demo")
            self.assertEqual(resolve_output(root / "a.out").name, "a.out")

    def test_two_names_in_one_file(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/"both.out").write_text("CP2K|\nGLOBAL| Project name a\nGLOBAL| Project name b")
            with self.assertRaises(AmbiguousProject):
                discover(directory)


class StructureTests(unittest.TestCase):
    def test_xyz_frames(self):
        last = read_xyz(FIXTURES / "trajectory.xyz")
        self.assertEqual(last.frame, 1)
        self.assertAlmostEqual(last.positions[0][2], 0.1)
        self.assertIsNone(last.cell)
        self.assertIsNone(last.pbc)
        self.assertEqual(read_xyz(FIXTURES / "trajectory.xyz", 0).positions[0][2], 0)
        with self.assertRaises(ParseError):
            read_xyz(FIXTURES / "trajectory.xyz", 2)

    def test_restart_cell_and_kind(self):
        structure = read_restart(FIXTURES / "water.restart")
        self.assertEqual(structure.symbols, ["O", "H", "H"])
        self.assertEqual(structure.cell[1], [1.0, 11.0, 0.0])
        self.assertEqual(structure.pbc, [True, True, False])

    def test_extxyz_roundtrip(self):
        original = read_restart(FIXTURES / "water.restart")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "water.xyz"
            path.write_text(xyz_text(original))
            result = read_xyz(path)
            self.assertEqual(result.cell, original.cell)
            self.assertEqual(result.pbc, original.pbc)
            self.assertEqual(result.positions, original.positions)

    def test_bohr_and_scaled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "atom.restart"
            template = "&SUBSYS\n&CELL\nABC [bohr] 10 10 10\n&END\n&COORD\nUNIT bohr\nH 1 2 3\n&END\n&END\n"
            path.write_text(template)
            result = read_restart(path)
            self.assertAlmostEqual(result.cell[0][0], 10 * BOHR_TO_ANGSTROM)
            self.assertAlmostEqual(result.positions[0][0], BOHR_TO_ANGSTROM)
            path.write_text(template.replace("UNIT bohr", "SCALED T").replace("H 1 2 3", "H 0.5 0 0"))
            self.assertAlmostEqual(read_restart(path).positions[0][0], 5 * BOHR_TO_ANGSTROM)

    def test_angles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "atom.restart"
            path.write_text("&SUBSYS\n&CELL\nABC 10 10 10\nALPHA_BETA_GAMMA 90 90 60\n&END\n&COORD\nH 0 0 0\n&END\n&END")
            result = read_restart(path)
            self.assertAlmostEqual(result.cell[1][0], 5)
            self.assertAlmostEqual(result.cell[1][1], 5*3**0.5)

    def test_truncated_and_nonfinite_xyz(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.xyz"
            for text in ["2\ncomment\nH 0 0 0", "1\ncomment\nH nan 0 0"]:
                path.write_text(text)
                with self.assertRaises(ParseError):
                    read_xyz(path)

    def test_unsupported_restart_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.restart"
            for text in [
                "&SUBSYS\n&COORD\nH 0 0 0\n&END\n&END",
                "&SUBSYS\n&CELL\nABC 10 10 10\nCELL_FILE_NAME cell.dat\n&END\n&COORD\nH 0 0 0\n&END\n&END",
                "&SUBSYS\n&COORD\nH 0 0 0\n&END",
            ]:
                path.write_text(text)
                with self.assertRaises(ParseError):
                    read_restart(path)

    def test_restart_directives_and_quoting_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.restart"
            for prefix in ["@INCLUDE another.inp\n", 'TITLE "unterminated\n']:
                path.write_text(prefix + (FIXTURES / "water.restart").read_text())
                with self.assertRaises(ParseError):
                    read_restart(path)

    def test_extxyz_invalid_cell(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.xyz"
            for comment in ['Lattice="1 2 3"', 'Lattice="0 0 0 0 0 0 0 0 0"', 'pbc="T T T"', 'pbc=T']:
                path.write_text("1\n" + comment + "\nH 0 0 0\n")
                with self.assertRaises(ParseError):
                    read_xyz(path)


class CLITests(unittest.TestCase):
    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_parse_and_report(self):
        code, out, _ = self.invoke(["parse", str(FIXTURES / "normal.out")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["schema_version"], "0.1.0")
        code, _, _ = self.invoke(["report", str(FIXTURES / "unconverged.out"), "--strict"])
        self.assertEqual(code, 7)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.invoke(["parse", directory])[0], 2)
            bad = Path(directory) / "bad.out"
            bad.write_text("not CP2K")
            self.assertEqual(self.invoke(["parse", str(bad)])[0], 4)
            bad.unlink()
            for name in ["a.out", "b.out"]:
                (Path(directory)/name).write_text((FIXTURES/"normal.out").read_text())
            self.assertEqual(self.invoke(["parse", directory])[0], 3)

    def test_csv_quality_metadata_and_no_source_changes(self):
        source = FIXTURES / "unconverged.out"
        original = source.read_bytes()
        code, out, _ = self.invoke(["parse", str(source), "--format", "csv"])
        self.assertEqual(code, 0)
        row = next(csv.DictReader(io.StringIO(out)))
        self.assertEqual(row["energy_usable"], "False")
        self.assertEqual(row["segment_status"], "failed")
        self.assertTrue(row["settings_json"])
        self.assertEqual(source.read_bytes(), original)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text("valuable content")
            code, _, _ = self.invoke(["parse", str(FIXTURES / "normal.out"), "-o", str(path)])
            self.assertEqual(code, 5)
            self.assertEqual(path.read_text(), "valuable content")

    def test_plain_xyz_requires_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "water.xyz"
            argv = ["export-structure", str(FIXTURES/"water.restart"), "-o", str(path), "--format", "xyz"]
            self.assertEqual(self.invoke(argv)[0], 2)
            self.assertFalse(path.exists())
            code, _, err = self.invoke(argv+["--allow-cell-loss"])
            self.assertEqual(code, 0)
            self.assertIn("omits cell", err)
            self.assertEqual(json.loads(Path(str(path)+".json").read_text())["cell"][0], [10, 0, 0])

    def test_sidecar_collision_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "water.xyz"
            sidecar = Path(str(path)+".json")
            sidecar.write_text("valuable")
            code, _, _ = self.invoke(["export-structure", str(FIXTURES/"water.restart"), "-o", str(path)])
            self.assertEqual(code, 5)
            self.assertFalse(path.exists())
            self.assertEqual(sidecar.read_text(), "valuable")

    def test_new_file_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial"
            with self.assertRaises(RuntimeError):
                with new_file(path) as stream:
                    stream.write("partial")
                    raise RuntimeError("test")
            self.assertFalse(path.exists())

    def test_missing_plot_dependency_code(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plot.png"
            with patch.dict("sys.modules", {"matplotlib.figure": None}):
                code, _, err = self.invoke(["plot", str(FIXTURES/"normal.out"), "-o", str(output)])
            self.assertEqual(code, 6)
            self.assertIn("matplotlib", err)
            self.assertFalse(output.exists())

    @unittest.skipUnless(find_spec("matplotlib"), "matplotlib optional")
    def test_scf_plot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scf.png"
            self.assertEqual(self.invoke(["plot", str(FIXTURES/"normal.out"), "--kind", "scf", "-o", str(output)])[0], 0)
            manifest = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual(manifest["kind"], "scf")
            self.assertIn("iteration", manifest["y_label"])

    @unittest.skipUnless(find_spec("matplotlib"), "matplotlib optional")
    def test_plot_and_correspondence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "energy.png"
            code, _, _ = self.invoke(["plot", str(FIXTURES/"restart.out"), "-o", str(path)])
            self.assertEqual(code, 0)
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
            manifest = json.loads(path.with_suffix(".json").read_text())
            self.assertFalse(manifest["segments_connected"])
            self.assertEqual(len(manifest["run"]["segments"]), 2)
            with path.with_suffix(".csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len([r for r in rows if r["record"] == "energy"]), 3)
            self.assertEqual(self.invoke(["plot", str(FIXTURES/"normal.out"), "-o", str(path)])[0], 5)

    @unittest.skipUnless(find_spec("matplotlib"), "matplotlib optional")
    def test_plot_csv_collision_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "energy.png"
            path.with_suffix(".csv").write_text("valuable")
            with self.assertRaises(OutputExists):
                plot_run(parse_output(FIXTURES/"normal.out"), path)
            self.assertFalse(path.exists())
            self.assertEqual(path.with_suffix(".csv").read_text(), "valuable")


if __name__ == "__main__":
    unittest.main()
