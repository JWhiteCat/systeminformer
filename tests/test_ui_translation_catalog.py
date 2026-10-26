"""Validate explicit UI call sites against the generated bilingual catalog."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generate_dynamic', ROOT / 'tools/localization/generate_dynamic.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class TranslationCatalogTests(unittest.TestCase):
    def test_all_explicit_literals_have_translations(self):
        catalog = generator.catalog()
        count = 0
        missing = []
        for directory in ('SystemInformer', 'plugins'):
            for path in (ROOT / directory).rglob('*.c'):
                for match in re.finditer(r'PhTranslateUiText\(L("(?:[^"\\]|\\.)*")\)', path.read_text(encoding='utf-8')):
                    text = json.loads(match[1])
                    count += 1
                    if text not in catalog:
                        missing.append((str(path.relative_to(ROOT)), text))
        self.assertGreater(count, 1000)
        self.assertEqual(missing, [])

    def test_property_pages_use_language_aware_loader(self):
        for directory in ('SystemInformer', 'plugins'):
            for path in (ROOT / directory).rglob('*.c'):
                source = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(encoding='utf-8'), flags=re.S)
                self.assertNotRegex(source, r'(?<!Ph)\bCreatePropertySheetPage(?:W|A)?\s*\(')

    def test_translated_menu_lookups_match_creation(self):
        source = (ROOT / 'plugins/ExtendedTools/main.c').read_text(encoding='utf-8')
        self.assertIn('PhFindEMenuItem(menuInfo->Menu, 0, PhTranslateUiText(L"&System"), 0)', source)
        source = (ROOT / 'SystemInformer/prpgthrd.c').read_text(encoding='utf-8')
        self.assertIn('PhFindEMenuItem(Menu, PH_EMENU_FIND_DESCEND, PhTranslateUiText(L"&Priority"), 0)', source)

    def test_no_duplicate_json_keys(self):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                self.assertNotIn(key, result)
                result[key] = value
            return result
        for path in (ROOT / 'localization').glob('*.json'):
            json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


if __name__ == '__main__':
    unittest.main()
