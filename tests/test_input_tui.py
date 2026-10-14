"""Synthetic menu/CLI regression; never runs CP2K or Multiwfn."""
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.errors import KitError
from cp2kkit.input_tui import GROUPS, Field, command_arguments, parse_value, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import read_structure

FIXTURES = Path(__file__).parent / "fixtures"


class TTY(io.StringIO):
    def isatty(self):
        return True


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "water.xyz"
        self.path.write_text("3\nsynthetic water\nO 0 0 0\nH .76 0 .58\nH -.76 0 .58\n")
        self.output = self.dir / "water.inp"
        self.settings = InputSettings(periodic="NONE")

    def session(self, lines, **kwargs):
        log = io.StringIO()
        code = run_interactive(str(self.path), -1, str(self.output), self.settings,
                               stdin=TTY(lines), stdout=log, **kwargs)
        return code, log.getvalue()

    def test_all_menu_text_is_english(self):
        for title, fields in GROUPS:
            self.assertTrue(title.isascii(), title)
            for field in fields:
                self.assertTrue(field.label.isascii(), field.label)
        lines = ''.join(f'{i}\n0\n' for i in range(1, 9))+'9\n0\n\nq\n'
        for settings in (self.settings, replace(self.settings, run_type='CELL_OPT', periodic='XYZ',
                                               cell=(20.,20.,20.), scf='diag', smearing=300)):
            self.settings = settings
            code, log = self.session(lines)
            self.assertEqual(code, 0)
            self.assertTrue(log.isascii(), log)
            self.assertIn('Main menu: current settings', log)
            self.assertIn('Input preview (not written)', log)
            self.assertIn('Cancelled; no files generated.', log)
            self.assertFalse(self.output.exists())

    def test_all_input_fields_editable_and_ranges(self):
        fields = [f for _, group in GROUPS for f in group]
        names = [f.name for f in fields]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(InputSettings.__dataclass_fields__) | {"path", "frame", "output"})
        self.assertEqual(parse_value(Field("p", "periodic", choices=("NONE", "XYZ")), "1"), "NONE")
        self.assertEqual(parse_value(Field("p", "periodic", choices=("NONE", "XYZ")), "xyz"), "XYZ")
        for f, raw in ((Field("a", "a", "int", minimum=1), "0"),
                       (Field("a", "a", "int3", minimum=1), "1 0 2"),
                       (Field("a", "a", "float", positive=True), "nan"),
                       (Field("a", "a", "float", positive=True), "inf"),
                       (Field("a", "a", "float", positive=True), "-1"),
                       (Field("a", "a", "float3"), "1 2"),
                       (Field("a", "a", "bool"), "maybe"),
                       (Field("a", "a"), "bad\x00path")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_value(f, raw)
        self.assertIsNone(parse_value(Field("p", "periodic", choices=("NONE",), optional=True), "auto"))
        self.assertFalse(parse_value(Field("b", "b", "bool"), "n"))
        self.assertEqual(parse_value(Field("a", "a", "float3"), "1.5 2 3"), (1.5, 2., 3.))

    def test_confirmed_generation_identical_to_parameter_api(self):
        code, log = self.session("0\ny\n")
        self.assertEqual(code, 0)
        text, expected = generate_input(read_structure(self.path), self.settings)
        self.assertEqual(self.output.read_text(), text)
        self.assertEqual(json.loads(Path(str(self.output)+".json").read_text()), json.loads(json.dumps(expected)))
        self.assertIn("Reproducible command", log)
        self.assertIn("Explicit valence electrons", log)

    def test_edit_task_functional_charge_and_density(self):
        # Choose GEO_OPT/BLYP; charge +1/multiplicity 2; enable spin with stride 2 3 4.
        lines = "2\n1\n3\n0\n3\n1\n2\n0\n4\n1\n1\n2\n2\n0\n8\n2\ny\n3\n2 3 4\n0\n0\ny\n"
        code, _ = self.session(lines)
        self.assertEqual(code, 0)
        expected = replace(self.settings, run_type="GEO_OPT", functional="BLYP",
                           charge=1, multiplicity=2, spin_density=True, cube_stride=(2,3,4))
        text, _ = generate_input(read_structure(self.path), expected)
        self.assertEqual(self.output.read_text(), text)
        m = json.loads(Path(str(self.output)+".json").read_text())
        self.assertTrue(m["density_output"]["electron_density"])
        self.assertTrue(m["density_output"]["spin_density"])
        self.assertFalse(m["runtime_validated"])

    def test_invalid_combination_can_be_fixed_without_automatic_changes(self):
        code, log = self.session("8\n2\ny\n0\n0\n4\n1\n1\n2\n2\n0\n0\ny\n")
        self.assertEqual(code, 0)
        self.assertIn("Spin density requires UKS", log)
        m = json.loads(Path(str(self.output)+".json").read_text())
        self.assertEqual(m["settings"]["charge"], 1)
        self.assertEqual(m["settings"]["multiplicity"], 2)

    def test_preview_and_decline_never_write(self):
        with patch("cp2kkit.input_tui.write_input") as write:
            code, log = self.session("9\n0\n\nq\n")
            write.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("&FORCE_EVAL", log)
        self.assertIn("Not confirmed", log)
        self.assertEqual(list(self.dir.iterdir()), [self.path])

    def test_bad_local_values_and_menu_choices_retry(self):
        code, log = self.session("²\n99\n7\n999\n1\nnan\n-5\n450\n0\nq\n")
        self.assertEqual(code, 0)
        self.assertGreaterEqual(log.count("Invalid"), 4)
        self.assertIn("cutoff=450.0", log)
        self.assertFalse(self.output.exists())

    def test_scf_kpoints_and_cell_are_never_implicitly_repaired(self):
        self.settings = replace(self.settings, kpoints=(2,2,2), smearing=300)
        code, log = self.session("0\n6\n1\ndiag\n0\n5\n1\nXYZ\n2\n20 20 20\n0\n0\ny\n")
        self.assertEqual(code, 0)
        self.assertIn("Non-Gamma kpoints require XYZ", log)
        m = json.loads(Path(str(self.output)+".json").read_text())
        self.assertEqual(m["settings"]["scf"], "diag")
        self.assertEqual(m["settings"]["periodic"], "XYZ")
        self.assertEqual(m["settings"]["cell"], [20,20,20])
        self.assertEqual(m["settings"]["kpoints"], [2,2,2])
        self.assertEqual(m["settings"]["smearing"], 300)

    def test_optional_values_reset_and_enter_keeps_value(self):
        self.settings = replace(self.settings, eps_scf=1e-8, smearing=300, scf="diag")
        code, log = self.session("6\n2\nauto\n5\nauto\n1\n\n0\n0\ny\n")
        self.assertEqual(code, 0)
        m = json.loads(Path(str(self.output)+".json").read_text())
        self.assertIsNone(m["settings"]["eps_scf"])
        self.assertIsNone(m["settings"]["smearing"])
        self.assertEqual(m["settings"]["scf"], "diag")

    def test_unknown_pbc_is_not_assumed_and_source_error_can_be_fixed(self):
        self.settings = InputSettings()
        code, log = self.session("0\n5\n1\nNONE\n0\n0\ny\n")
        self.assertEqual(code, 0)
        self.assertIn("Periodicity is unknown", log)
        # A missing source is a recoverable draft error; cancellation writes nothing.
        log = io.StringIO()
        self.assertEqual(run_interactive("missing.xyz", -1, str(self.dir/"missing.inp"), self.settings,
                                        stdin=TTY("0\nq\n"), stdout=log), 0)
        self.assertIn("Cannot read", log.getvalue())
        self.assertFalse((self.dir/"missing.inp").exists())

    def test_file_and_sidecar_collisions_are_preserved(self):
        for target in (self.output, Path(str(self.output)+".json")):
            target.write_text("existing user data")
            with self.assertRaises(KitError) as cm:
                self.session("0\ny\n")
            self.assertEqual(cm.exception.code, 5)
            self.assertEqual(target.read_text(), "existing user data")
            if target != self.output:
                self.assertFalse(self.output.exists())
            target.unlink()

    def test_non_tty_eof_and_interrupt(self):
        with self.assertRaises(KitError) as cm:
            run_interactive(str(self.path), -1, str(self.output), self.settings,
                            stdin=io.StringIO("0\ny\n"), stdout=io.StringIO())
        self.assertEqual(cm.exception.code, 2)
        with self.assertRaises(KitError):
            self.session("")
        with patch.object(TTY, "readline", side_effect=KeyboardInterrupt), self.assertRaises(KitError):
            self.session("")
        self.assertFalse(self.output.exists())

    def test_cancellation_at_initial_prompt_and_confirm(self):
        for lines in ("q\n", "quit\n"):
            self.assertEqual(self.session(lines)[0], 0)
            self.assertEqual(run_interactive(None, -1, None, self.settings,
                                            stdin=TTY(lines), stdout=io.StringIO()), 0)
        self.assertEqual(self.session("0\nq\n")[0], 0)
        self.assertFalse(self.output.exists())

    def test_replay_command_spaces_optional_values_and_all_fields(self):
        source = self.dir/"structure with spaces.xyz"
        source.write_bytes(self.path.read_bytes())
        settings = replace(self.settings, scf="diag", charge=1, multiplicity=2,
                           electron_density=True, spin_density=True, cube_stride=(1,2,3),
                           smearing=200, eps_scf=1e-7, cell=(18.,19.,20.), dispersion="d3bj")
        argv = command_arguments(source, 0, "-output with spaces.inp", settings)
        self.assertEqual(shlex.split(shlex.join(argv)), argv)
        args = build_parser().parse_args(argv[3:])
        for name, value in settings.__dict__.items():
            actual = getattr(args, name)
            if isinstance(value, tuple):
                actual = tuple(actual)
            self.assertEqual(actual, value, name)
        self.assertEqual(args.output, "-output with spaces.inp")
        self.assertEqual(args.frame, 0)
        self.assertFalse(args.interactive)


class CLIInteractiveTests(unittest.TestCase):
    def call(self, args, lines, tty=True):
        log, error = io.StringIO(), io.StringIO()
        with patch("sys.stdin", TTY(lines) if tty else io.StringIO(lines)), redirect_stdout(log), redirect_stderr(error):
            code = main(args)
        return code, log.getvalue(), error.getvalue()

    def test_explicit_tui_cli_arguments_seed_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"seed.inp"
            code, log, _ = self.call(["generate-input", str(FIXTURES/"trajectory.xyz"), "--tui", "-o", str(out),
                                      "--periodic", "NONE", "--run-type", "GEO_OPT", "--cp2k-version", "2024.1"], "0\ny\n")
            self.assertEqual(code, 0)
            m = json.loads(Path(str(out)+".json").read_text())
            self.assertEqual(m["settings"]["run_type"], "GEO_OPT")
            self.assertEqual(m["target_version"], "2024.1")
            self.assertIn("run_type=GEO_OPT", log)

    def test_bare_command_and_missing_paths_prompt_in_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            for extra in ([], ["--interactive"]):
                out = Path(tmp)/("bare"+str(len(extra))+".inp")
                lines = f"{FIXTURES/'trajectory.xyz'}\n{out}\n5\n1\n1\n0\n0\ny\n"
                code, _, _ = self.call(["generate-input", *extra], lines)
                self.assertEqual(code, 0)
                self.assertTrue(out.exists())

    @unittest.skipUnless(os.name == "posix", "PTY smoke requires POSIX")
    def test_real_pty_session_preview_and_generation(self):
        import pty
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"pty.inp"
            master, slave = pty.openpty()
            try:
                with subprocess.Popen([sys.executable,"-m","cp2kkit","generate-input",
                                       str(FIXTURES/"trajectory.xyz"),"--tui","--periodic","NONE","-o",str(out)],
                                      stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
                    os.close(slave)
                    slave = None
                    try:
                        os.write(master, b"9\n0\ny\n")
                        log, error = proc.communicate(timeout=15)
                    except BaseException:
                        proc.kill()
                        proc.communicate()
                        raise
                    self.assertEqual(proc.returncode, 0, error+log)
                    self.assertIn("Input preview", log)
                    text, _ = generate_input(read_structure(FIXTURES/"trajectory.xyz"), InputSettings(periodic="NONE"))
                    self.assertEqual(out.read_text(), text)
            finally:
                os.close(master)
                if slave is not None:
                    os.close(slave)

    def test_noninteractive_missing_arguments_fail_and_tui_pipes_fail(self):
        for args in (["generate-input"], ["generate-input", "file.xyz"]):
            with redirect_stderr(io.StringIO()), patch("sys.stdin", io.StringIO()), self.assertRaises(SystemExit) as cm:
                main(args)
            self.assertEqual(cm.exception.code, 2)
        code, _, error = self.call(["generate-input", "--tui"], "q\n", tty=False)
        self.assertEqual(code, 2)
        self.assertIn("TTY", error)

    def test_regular_cli_stays_noninteractive_even_in_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"batch.inp"
            with patch("cp2kkit.input_tui.run_interactive") as menu:
                code, _, _ = self.call(["generate-input",str(FIXTURES/"trajectory.xyz"),"-o",str(out),"--periodic","NONE"], "")
            self.assertEqual(code, 0)
            menu.assert_not_called()

    def test_subprocess_non_tty_and_help(self):
        for args, expected in ((["generate-input","--tui"], 2), (["generate-input","--help"], 0)):
            p = subprocess.run([sys.executable,"-m","cp2kkit",*args],input="q\n",capture_output=True,text=True)
            self.assertEqual(p.returncode, expected)
            if expected == 2:
                self.assertIn("TTY", p.stderr)
            else:
                self.assertIn("--interactive", p.stdout)
                self.assertIn("--tui", p.stdout)


if __name__ == "__main__":
    unittest.main()
