"""English maintained text and documentation links; user data are outside scope."""
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from cp2kkit.input_tui import Field, parse_value

ROOT = Path(__file__).resolve().parents[1]


def maintained_files():
    paths = list(ROOT.glob('*.md')) + [ROOT/'pyproject.toml', ROOT/'.gitignore']
    for directory in ('.agents', 'docs', 'third_party', 'src', 'tests'):
        paths.extend(path for path in (ROOT/directory).rglob('*')
                     if path.is_file() and path.suffix in {'.md', '.py'})
    return sorted(set(paths))


class ProjectTextTests(unittest.TestCase):
    def test_maintained_text_has_no_literal_cjk(self):
        for path in maintained_files():
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotRegex(path.read_text(encoding='utf-8'), r'[\u3400-\u4dbf\u4e00-\u9fff]')

    def test_local_documentation_links_resolve(self):
        pattern = re.compile(r'\[[^\]]+\]\(([^\s)]+)\)')
        for path in maintained_files():
            if path.suffix != '.md':
                continue
            for target in pattern.findall(path.read_text(encoding='utf-8')):
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                with self.subTest(path=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue((path.parent/unquote(parsed.path)).exists())

    def test_every_development_prompt_requires_english(self):
        paths = sorted((ROOT/'.agents/prompts').glob('*.md')) + [ROOT/'.agents/DEVELOPMENT.md']
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding='utf-8')
                self.assertIn('Use English', text)
                self.assertIn('user', text)
                self.assertIn('Preserve', text)

    def test_legacy_boolean_aliases_remain_compatible(self):
        field = Field('enabled', 'Enabled', 'bool')
        self.assertTrue(parse_value(field, '\u5f00\u542f'))
        self.assertFalse(parse_value(field, '\u5173\u95ed'))
