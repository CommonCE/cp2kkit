"""Source-tree version declarations and CLI must stay in sync."""
import io
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cp2kkit import __version__
from cp2kkit.cli import main
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.models import SCHEMA_VERSION
from cp2kkit.structure import Structure

ROOT = Path(__file__).resolve().parents[1]


class VersionTests(unittest.TestCase):
    def test_package_metadata_readme_and_changelog_match(self):
        self.assertRegex(__version__, r'^\d+\.\d+\.\d+$')
        metadata = (ROOT/'pyproject.toml').read_text()
        declared = re.search(r'^version\s*=\s*"([^"]+)"\s*$', metadata, re.M)
        self.assertIsNotNone(declared)
        self.assertEqual(declared[1], __version__)
        self.assertIn(f'**v{__version__} preliminary implementation**', (ROOT/'README.md').read_text())
        changelog = (ROOT/'CHANGELOG.md').read_text()
        first_version = re.search(r'^## (\d+\.\d+\.\d+)\s*$', changelog, re.M)
        self.assertIsNotNone(first_version)
        self.assertEqual(first_version[1], __version__)

    def test_generator_version_and_independent_schema(self):
        structure = Structure(['He'], [[0., 0., 0.]], None, [False]*3, {'path': 'synthetic.xyz'})
        _, manifest = generate_input(structure, InputSettings())
        self.assertEqual(manifest['generator']['version'], __version__)
        self.assertEqual(manifest['schema_version'], SCHEMA_VERSION)

    def test_cli_version(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as cm:
            main(['--version'])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), f'cp2kkit {__version__}')
