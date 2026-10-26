#!/usr/bin/env python3
"""Compile the real UI-language implementation with a small portable Win32 shim.

This checks C lookup/selection behavior and the actual PhLoadResource lookup body
against deterministic loader mocks. It is NOT a Windows build or UI test.
Requires Python 3 and a C11 compiler (CC, default: cc).
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SHIM = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <wchar.h>
typedef const wchar_t *PCWSTR;
typedef uint32_t ULONG;
typedef int32_t LONG;
#define VOID void
#define NTAPI
#define _In_
#define _In_opt_
#define _Out_opt_
#define RTL_NUMBER_OF(a) (sizeof(a)/sizeof((a)[0]))
#define PH_UI_LANGUAGE_ENGLISH 0
#define PH_UI_LANGUAGE_CHINESE_SIMPLIFIED 1
static LONG InterlockedExchange(volatile LONG *p, LONG v) { LONG old=*p; *p=v; return old; }
static LONG InterlockedCompareExchange(volatile LONG *p,LONG v,LONG e) { LONG old=*p; if(old==e) *p=v; return old; }
'''
CORE_TEST = r'''
int main(void)
{
    PCWSTR unknown = L"untranslated/user-supplied/value/42";
    assert(PhGetUiLanguage() == PH_UI_LANGUAGE_ENGLISH);
    assert(PhTranslateUiText(NULL) == NULL);
    assert(PhTranslateUiText(unknown) == unknown);
    for (ULONG i = 0; i < RTL_NUMBER_OF(PhpChineseUiTranslations); i++)
    {
        PCWSTR english = PhpChineseUiTranslations[i].English;
        PhSetUiLanguage(PH_UI_LANGUAGE_ENGLISH);
        assert(PhTranslateUiText(english) == english);
        PhSetUiLanguage(PH_UI_LANGUAGE_CHINESE_SIMPLIFIED);
        assert(PhGetUiLanguage() == PH_UI_LANGUAGE_CHINESE_SIMPLIFIED);
        assert(wcscmp(PhTranslateUiText(english), PhpChineseUiTranslations[i].Translation) == 0);
        assert(PhTranslateUiText(unknown) == unknown);
        assert(PhTranslateUiText(NULL) == NULL);
        PhSetUiLanguage(PH_UI_LANGUAGE_ENGLISH);
        assert(PhTranslateUiText(english) == english);
        PhSetUiLanguage(99);
        assert(PhGetUiLanguage() == PH_UI_LANGUAGE_ENGLISH);
        assert(PhTranslateUiText(english) == english);
        PhSetUiLanguage(UINT32_MAX);
        assert(PhGetUiLanguage() == PH_UI_LANGUAGE_ENGLISH);
    }
    return 0;
}
'''
RESOURCE_SHIM = r'''
typedef void *PVOID;
typedef void *PIMAGE_RESOURCE_DATA_ENTRY;
typedef uintptr_t ULONG_PTR;
typedef int NTSTATUS;
#define NT_SUCCESS(s) ((s) >= 0)
#define RT_DIALOG ((PCWSTR)(uintptr_t)5)
#define RT_MENU ((PCWSTR)(uintptr_t)4)
#define RT_STRING ((PCWSTR)(uintptr_t)6)
#define LANG_NEUTRAL 0
#define SUBLANG_NEUTRAL 0
#define LANG_ENGLISH 9
#define SUBLANG_ENGLISH_US 1
#define LANG_CHINESE 4
#define SUBLANG_CHINESE_SIMPLIFIED 2
#define MAKELANGID(p,s) (((s)<<10)|(p))
#define LDR_RES_SEARCH_SKIP_MUI 4
#define __try if (1)
#define __except(x) else
#define GetExceptionCode() (-2)
static ULONG language, calls, requested[4];
static int availableChinese, availableEnglish, neutralCalls;
static ULONG PhGetUiLanguage(void) { return language; }
static NTSTATUS LdrFindResourceEx_U(int flags, PVOID base, ULONG_PTR *path, ULONG count, PIMAGE_RESOURCE_DATA_ENTRY *entry)
{
    (void)base;
    assert(flags == LDR_RES_SEARCH_SKIP_MUI);
    assert(count == 3);
    assert(calls < 4);
    requested[calls++] = (ULONG)path[2];
    *entry = NULL;
    if ((path[2] == 0x804 && availableChinese) || (path[2] == 0x409 && availableEnglish))
        return 0;
    return -1;
}
static NTSTATUS LdrFindResource_U(PVOID base, ULONG_PTR *path, ULONG count, PIMAGE_RESOURCE_DATA_ENTRY *entry)
{
    (void)base;
    assert(count == 3 && path[2] == 0);
    neutralCalls++;
    *entry = NULL;
    return 0;
}
static NTSTATUS LdrAccessResource(PVOID base, PIMAGE_RESOURCE_DATA_ENTRY entry, PVOID *buffer, ULONG *length)
{
    (void)base; (void)entry;
    *buffer = (PVOID)(uintptr_t)123;
    *length = 456;
    return 0;
}
static void reset(ULONG selected, int chinese, int english)
{
    language = selected;
    availableChinese = chinese;
    availableEnglish = english;
    calls = neutralCalls = 0;
}
'''
RESOURCE_TEST = r'''
int main(void)
{
    PVOID buffer;
    ULONG length;
    PCWSTR types[] = { RT_DIALOG, RT_MENU, RT_STRING };
    for (ULONG i = 0; i < RTL_NUMBER_OF(types); i++)
    {
        reset(1, 1, 1);
        assert(NT_SUCCESS(PhLoadResource(NULL, NULL, types[i], &length, &buffer)));
        assert(calls == 1 && requested[0] == 0x804 && neutralCalls == 0);
        assert(buffer == (PVOID)(uintptr_t)123 && length == 456);
        reset(1, 0, 1);
        assert(NT_SUCCESS(PhLoadResource(NULL, NULL, types[i], NULL, NULL)));
        assert(calls == 2 && requested[0] == 0x804 && requested[1] == 0x409 && neutralCalls == 0);
        reset(0, 1, 1);
        assert(NT_SUCCESS(PhLoadResource(NULL, NULL, types[i], NULL, NULL)));
        assert(calls == 1 && requested[0] == 0x409 && neutralCalls == 0);
        reset(99, 1, 1);
        assert(NT_SUCCESS(PhLoadResource(NULL, NULL, types[i], NULL, NULL)));
        assert(calls == 1 && requested[0] == 0x409 && neutralCalls == 0);
        reset(1, 0, 0);
        assert(NT_SUCCESS(PhLoadResource(NULL, NULL, types[i], NULL, NULL)));
        assert(calls == 2 && neutralCalls == 1);
    }
    reset(1, 1, 1);
    assert(NT_SUCCESS(PhLoadResource(NULL, NULL, (PCWSTR)(uintptr_t)10, NULL, NULL)));
    assert(calls == 0 && neutralCalls == 1);
    return 0;
}
'''

PROPERTY_SHIM = r'''
#include <string.h>
typedef void *PVOID;
typedef const void *LPCDLGTEMPLATE;
typedef void *HPROPSHEETPAGE;
typedef int NTSTATUS;
#define NT_SUCCESS(s) ((s) >= 0)
#define RT_DIALOG ((PCWSTR)(uintptr_t)5)
#define PSP_DLGINDIRECT 1
// Only fields consumed by the actual wrapper are relevant to this host test.
typedef struct {
    ULONG dwSize, dwFlags;
    PVOID hInstance;
    union { PCWSTR pszTemplate; LPCDLGTEMPLATE pResource; };
    intptr_t lParam;
    ULONG newerField;
} PROPSHEETPAGE;
#define PROPSHEETPAGE_V1_SIZE offsetof(PROPSHEETPAGE, newerField)
typedef const PROPSHEETPAGE *LPCPROPSHEETPAGE;
static int loadCalls, createCalls, loadFailure;
static PROPSHEETPAGE captured;
static LPCPROPSHEETPAGE capturedPointer;
static NTSTATUS PhLoadResource(PVOID instance, PCWSTR name, PCWSTR type, ULONG *size, PVOID *result)
{
    assert(instance == (PVOID)(uintptr_t)10);
    assert(name == (PCWSTR)(uintptr_t)20);
    assert(type == RT_DIALOG && size == NULL);
    loadCalls++;
    *result = (PVOID)(uintptr_t)30;
    return loadFailure ? -1 : 0;
}
static HPROPSHEETPAGE CreatePropertySheetPage(LPCPROPSHEETPAGE page)
{
    createCalls++;
    capturedPointer = page;
    captured = *page;
    return (HPROPSHEETPAGE)(uintptr_t)40;
}
'''
PROPERTY_TEST = r'''
int main(void)
{
    PROPSHEETPAGE input = {0}, original;
    input.dwSize = sizeof(input);
    input.dwFlags = 0x80;
    input.hInstance = (PVOID)(uintptr_t)10;
    input.pszTemplate = (PCWSTR)(uintptr_t)20;
    input.lParam = 1234;
    original = input;
    assert(PhCreatePropertySheetPage(&input) == (HPROPSHEETPAGE)(uintptr_t)40);
    assert(loadCalls == 1 && createCalls == 1);
    assert(captured.dwFlags == (0x80 | PSP_DLGINDIRECT));
    assert(captured.pResource == (LPCDLGTEMPLATE)(uintptr_t)30);
    assert(captured.hInstance == input.hInstance && captured.lParam == input.lParam);
    assert(memcmp(&input, &original, sizeof(input)) == 0);
    input.dwFlags |= PSP_DLGINDIRECT;
    input.pResource = (LPCDLGTEMPLATE)(uintptr_t)50;
    assert(PhCreatePropertySheetPage(&input) == (HPROPSHEETPAGE)(uintptr_t)40);
    assert(loadCalls == 1 && createCalls == 2);
    assert(capturedPointer == &input && captured.pResource == input.pResource);
    input = original;
    loadFailure = 1;
    assert(PhCreatePropertySheetPage(&input) == NULL);
    assert(loadCalls == 2 && createCalls == 2);
    assert(memcmp(&input, &original, sizeof(input)) == 0);
    loadFailure = 0;
    input.dwSize = PROPSHEETPAGE_V1_SIZE;
    input.newerField = 99;
    assert(PhCreatePropertySheetPage(&input) == (HPROPSHEETPAGE)(uintptr_t)40);
    assert(captured.dwSize == PROPSHEETPAGE_V1_SIZE && captured.newerField == 0);
    assert(captured.lParam == input.lParam && input.newerField == 99);
    assert(loadCalls == 3 && createCalls == 3);
    input.dwSize = 0;
    assert(PhCreatePropertySheetPage(&input) == NULL);
    input.dwSize = sizeof(input) + 100;
    assert(PhCreatePropertySheetPage(&input) == NULL);
    assert(loadCalls == 3 && createCalls == 3);
    return 0;
}
'''


def compile_and_run(directory, name, source):
    path = directory / (name + '.c')
    binary = directory / name
    path.write_text(source, encoding='utf-8')
    command = shlex.split(os.environ.get('CC', 'cc'))
    command += ['-std=c11', '-Wall', '-Wextra', '-Werror', '-I' + str(directory),
                '-I' + str(ROOT / 'phlib/include'), str(path), '-o', str(binary)]
    subprocess.run(command, check=True)
    subprocess.run([str(binary)], check=True)
    print(name + ': passed')


def main():
    with tempfile.TemporaryDirectory(prefix='si-ui-language-') as temporary:
        directory = Path(temporary)
        (directory / 'ph.h').write_text(SHIM, encoding='utf-8')
        core = (ROOT / 'phlib/uilang.c').read_text(encoding='utf-8')
        compile_and_run(directory, 'catalog_and_language', core + CORE_TEST)
        loader = (ROOT / 'phlib/mapldr.c').read_text(encoding='utf-8')
        start = loader.index('NTSTATUS PhLoadResource(\n')
        body = loader[start:loader.index('\n}\n', start) + 3]
        # Resource tests do not need the interlocked stubs from the core shim.
        resource_types = SHIM[:SHIM.index('static LONG InterlockedExchange')]
        compile_and_run(directory, 'resource_fallback', resource_types + RESOURCE_SHIM + body + RESOURCE_TEST)
        gui = (ROOT / 'phlib/guisup.c').read_text(encoding='utf-8')
        start = gui.index('HPROPSHEETPAGE PhCreatePropertySheetPage(\n')
        body = gui[start:gui.index('\n}\n', start) + 3]
        compile_and_run(directory, 'property_page', resource_types + PROPERTY_SHIM + body + PROPERTY_TEST)


if __name__ == '__main__':
    main()
