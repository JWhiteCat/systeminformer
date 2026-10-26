#!/usr/bin/env python3
"""Portable catalog tests; this does not replace a Windows build/UI smoke test."""
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from generate_dynamic import ROOT, catalog


class DynamicCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = catalog()

    def test_generated_header_is_current(self):
        subprocess.run([sys.executable, str(Path(__file__).with_name('generate_dynamic.py')), '--check'], check=True)

    def test_every_explicit_literal_has_translation(self):
        # Match only literal UI arguments, never dynamic process names or paths.
        pattern = re.compile(r'PhTranslateUiText\((L"(?:[^"\\]|\\.)*")\)')
        sources = list((ROOT / 'SystemInformer').glob('*.c'))
        sources += list((ROOT / 'plugins').glob('*/*.c'))
        count = 0
        for path in sources:
            for match in pattern.finditer(path.read_text(encoding='utf-8')):
                source = json.loads(match[1][1:])
                with self.subTest(file=str(path.relative_to(ROOT)), source=source):
                    self.assertIn(source, self.values)
                count += 1
        self.assertGreater(count, 1000)

    def test_main_tabs_keep_identifiers(self):
        source = (ROOT / 'SystemInformer/mainwnd.c').read_text(encoding='utf-8')
        for name in ('Processes', 'Services', 'Network'):
            self.assertIn(f'PhMwpCreateInternalPage(L"{name}"', source)
        self.assertIn('item.Text = (PWSTR)PhTranslateUiText(name->Buffer);', source)
        self.assertIn('page->Name = Template->Name;', source)

    def test_known_menu_shortcut(self):
        source = '&Copy\bCtrl+C'
        self.assertEqual(self.values[source], '复制(&C)\bCtrl+C')

    def test_settings_and_primary_columns(self):
        for source in ('General', 'Advanced', 'Tray Icon', 'Plugins', 'Processes',
                       'Services', 'Network', 'Private bytes', 'Local address',
                       'Remote address', 'One or more options you have changed requires a restart of System Informer.'):
            with self.subTest(source=source):
                self.assertIn(source, self.values)
                self.assertNotEqual(self.values[source], source)


if __name__ == '__main__':
    unittest.main()
