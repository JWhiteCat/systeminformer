"""Cross-platform resource checks (not a replacement for Windows visual QA)."""
import json
import re
import unittest

from generate_resources import ROOT, CATALOG, SOURCES, blocks, render, CAPTION, STRING_ENTRY


class ResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding='utf-8'))

    def test_generated_resources_are_current(self):
        for path in SOURCES:
            with self.subTest(source=str(path.relative_to(ROOT))):
                generated, _ = render(path.read_text(encoding='utf-8-sig'), self.catalog)
                self.assertEqual(path.with_name(path.stem + '.zh-CN.rc').read_text(encoding='utf-8'), generated)

    def test_resource_structure_and_noncaption_strings_are_unchanged(self):
        # Comparing each line except its display caption proves IDs, dimensions,
        # styles, control classes, font and ordering remain identical.
        def structure(block):
            regex = STRING_ENTRY if block[0].startswith('STRINGTABLE') else CAPTION
            return [regex.sub(lambda m: m[1] + '"<caption>"', line) for line in block]
        for path in SOURCES:
            english = blocks(path.read_text(encoding='utf-8-sig'))
            chinese = blocks(path.with_name(path.stem + '.zh-CN.rc').read_text(encoding='utf-8'))
            with self.subTest(source=str(path.relative_to(ROOT))):
                self.assertEqual([structure(b) for b in english], [structure(b) for b in chinese])

    def test_accelerators_escapes_placeholders_and_links(self):
        patterns = [r'(?<!&)&(?!&)(.)', r'\\[nrt]', r'%(?:\d+\$)?[-+ #0]*\d*(?:\.\d+)?(?:I64|ll|l|h|z)?[a-zA-Z%]', r'<[^>]+>']
        for english, chinese in self.catalog.items():
            with self.subTest(caption=english):
                self.assertTrue(chinese)
                for pattern in patterns:
                    self.assertEqual(re.findall(pattern, english), re.findall(pattern, chinese))

    def test_english_sources_include_only_their_own_chinese_resources(self):
        for path in SOURCES:
            source = path.read_text(encoding='utf-8-sig')
            include = f'#include "{path.stem}.zh-CN.rc"'
            with self.subTest(source=str(path.relative_to(ROOT))):
                self.assertEqual(source.count(include), 1)
                self.assertIn('LANGUAGE LANG_ENGLISH, SUBLANG_ENGLISH_US', source)
                chinese = path.with_name(path.stem + '.zh-CN.rc').read_text(encoding='utf-8')
                self.assertIn('LANGUAGE LANG_CHINESE, SUBLANG_CHINESE_SIMPLIFIED', chinese)
                self.assertNotRegex(chinese, r'(?m)^\w+[ \t]+(?:ICON|BITMAP|VERSIONINFO|ACCELERATORS)\b')

    def test_unknown_caption_falls_back_to_english(self):
        source = 'IDD_TEST DIALOGEX 0,0,10,10\nCAPTION "Not translated"\nBEGIN\n    LTEXT "Other text",IDC_STATIC,0,0,10,10\nEND'
        output, _ = render(source, self.catalog)
        self.assertIn('CAPTION "Not translated"', output)
        self.assertIn('LTEXT "Other text",IDC_STATIC,0,0,10,10', output)

    def test_resource_encoding_is_selected_by_both_build_systems(self):
        # RC4215: /8 (UTF-8-only mode) rejects any code_page pragma, even 65001.
        for path in SOURCES:
            generated = path.with_name(path.stem + '.zh-CN.rc').read_text(encoding='utf-8')
            self.assertNotIn('#pragma code_page', generated)
        self.assertIn('/8 %(AdditionalOptions)', (ROOT / 'Common.User.props').read_text())
        self.assertIn('$<$<COMPILE_LANGUAGE:RC>:/c65001>', (ROOT / 'cmake/commands.cmake').read_text())


if __name__ == '__main__':
    unittest.main()
