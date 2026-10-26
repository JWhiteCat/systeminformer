"""Built-in metric names/semantics plus portable execution of the real C metadata.

The C shim tests immutable lookup and language selection, not Win32 GUI behavior.
"""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'SystemInformer/include/proccolmeta.h'


def records():
    pattern = r'\{ PHPRTLC_(\w+),\s*' + r',\s*'.join([r'L("(?:[^"\\]|\\.)*")'] * 5) + r'\s*\}'
    return {m[0]: tuple(json.loads(x) for x in m[1:])
            for m in re.findall(pattern, HEADER.read_text())}


class ProcessColumnMetadataTests(unittest.TestCase):
    def test_complete_ids_and_original_names(self):
        source = (ROOT / 'SystemInformer/proctree.c').read_text()
        titles = dict(re.findall(r'PhAddTreeNewColumn\w*\(hwnd, PHPRTLC_(\w+), (?:TRUE|FALSE), (?:PhTranslateUiText\()?L"([^"]+)"', source))
        data = records()
        self.assertEqual(len(data), 109)
        self.assertEqual(set(data), set(titles))
        for key, fields in data.items():
            self.assertEqual(fields[0], titles[key], key)
            self.assertTrue(fields[1] and fields[3] and fields[4], key)

    def test_distinguishes_memory_and_nonrate_deltas(self):
        data = records()
        self.assertIn('physical RAM', data['PRIVATEWS'][3])
        self.assertIn('当前驻留在物理内存中的私有部分', data['PRIVATEWS'][4])
        self.assertIn('nonresident', data['PRIVATEBYTES'][3])
        self.assertIn('不等于私有工作集', data['PRIVATEBYTES'][4])
        self.assertIn('whether currently shared or not', data['SHAREABLEWS'][3])
        self.assertIn('currently shared', data['SHAREDWS'][3])
        self.assertIn('not total commit', data['COMMITSIZE'][3])
        self.assertIn('not per second', data['CYCLESDELTA'][3])
        self.assertIn('not the number of handles owned', data['REFERENCEDELTA'][3])
        self.assertIn('retained', data['CPUAVERAGE'][3])

    def test_real_c_lookup_and_language_selection(self):
        compiler = shlex.split(os.environ.get('CC', 'cc'))
        if not shutil.which(compiler[0]):
            self.skipTest('C compiler unavailable; native lookup not executed')
        defines = '\n'.join(re.findall(r'^#define PHPRTLC_\w+ \d+$',
            (ROOT / 'SystemInformer/include/proctree.h').read_text(), re.M))
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <wchar.h>
typedef uint32_t ULONG;
typedef const wchar_t *PCWSTR;
#define _In_
#define RTL_NUMBER_OF(a) (sizeof(a) / sizeof((a)[0]))
#define PH_UI_LANGUAGE_CHINESE_SIMPLIFIED 1
static ULONG language;
static ULONG PhGetUiLanguage(void) { return language; }
''' + defines + '\n#include "' + str(HEADER) + '"\n' + r'''
int main(void)
{
    assert(RTL_NUMBER_OF(PhpProcessColumnMetadata) == PHPRTLC_MAXIMUM);
    for (ULONG id = 0; id < PHPRTLC_MAXIMUM; id++)
    {
        const PH_PROCESS_COLUMN_METADATA *m = PhpGetProcessColumnMetadata(id);
        assert(m && m->Id == id && m->EnglishName[0] && m->ChineseName[0]);
        language = 0;
        assert(PhpGetProcessColumnDescription(id) == m->EnglishDescription);
        language = 1;
        assert(PhpGetProcessColumnDescription(id) == m->ChineseDescription);
        language = 99;
        assert(PhpGetProcessColumnDescription(id) == m->EnglishDescription);
    }
    assert(!PhpGetProcessColumnMetadata(PHPRTLC_MAXIMUM));
    assert(!PhpGetProcessColumnMetadata(UINT32_MAX));
    assert(!PhpGetProcessColumnDescription(PHPRTLC_MAXIMUM));
    const PH_PROCESS_COLUMN_METADATA *m = PhpGetProcessColumnMetadata(PHPRTLC_PRIVATEWS);
    assert(wcsstr(m->Aliases, L"private working set"));
    assert(wcsstr(m->ChineseDescription, L"\u7269\u7406\u5185\u5b58"));
    assert(!wcscmp(m->EnglishName, L"Private WS"));
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='si-column-meta-') as temp:
            source = Path(temp) / 'test.c'
            exe = Path(temp) / 'test'
            source.write_text(program)
            subprocess.run(compiler + ['-std=c11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
