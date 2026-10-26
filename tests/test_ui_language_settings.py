#!/usr/bin/env python3
"""Compile the real language-dialog procedure against a small Win32/settings fake.

This checks commit/cancel/error control flow, not Windows rendering or disk I/O.
Run: python tests/test_ui_language_settings.py
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

PRELUDE = r'''
#include <assert.h>
#include <stddef.h>
#include <wchar.h>
#define _In_
#define CALLBACK
#define FALSE 0
#define WM_INITDIALOG 1
#define WM_CLOSE 2
#define WM_COMMAND 3
#define IDOK 1
#define IDCANCEL 2
#define IDC_UILANGUAGE 1571
#define SETTING_UI_LANGUAGE L"UiLanguage"
#define GET_WM_COMMAND_ID(w, l) (w)
#define NT_SUCCESS(s) ((s) >= 0)
typedef int HWND, UINT, WPARAM, LPARAM, INT_PTR, INT, NTSTATUS;
typedef unsigned long ULONG;
static ULONG setting, persisted;
static int selection, writes, saves, closed, errorShown, failSave;
static int PhEnableThemeSupport, PhSettingsFileName;
static HWND GetDlgItem(HWND w, int id) { return id; }
static HWND GetParent(HWND w) { return w; }
static void ComboBox_AddString(HWND w, const wchar_t *s) { }
static void ComboBox_SetCurSel(HWND w, int value) { selection = value; }
static int ComboBox_GetCurSel(HWND w) { return selection; }
static void PhCenterWindow(HWND w, HWND parent) { }
static void PhInitializeWindowTheme(HWND w, int enabled) { }
static ULONG PhGetIntegerSetting(const wchar_t *name) { return setting; }
static void PhSetIntegerSetting(const wchar_t *name, ULONG value) { setting = value; ++writes; }
static NTSTATUS PhSaveSettings2(int path) {
    ++saves;
    if (failSave) return -1;
    persisted = setting;
    return 0;
}
static const wchar_t *PhTranslateUiText(const wchar_t *text) { return text; }
static void PhShowStatus(HWND w, const wchar_t *text, NTSTATUS status, int e) { ++errorShown; }
static void EndDialog(HWND w, int result) { closed = result; }
static void reset(ULONG value) {
    setting = persisted = value;
    writes = saves = closed = errorShown = failSave = 0;
    selection = -1;
}
'''

CASES = r'''
int main(void) {
    /* Both saved choices reload into the selector. */
    reset(0); PhpOptionsLanguageDlgProc(0, WM_INITDIALOG, 0, 0); assert(selection == 0);
    reset(1); PhpOptionsLanguageDlgProc(0, WM_INITDIALOG, 0, 0); assert(selection == 1);
    /* Unknown stored language displays the English fallback, without mutating it. */
    reset(99); PhpOptionsLanguageDlgProc(0, WM_INITDIALOG, 0, 0);
    assert(selection == 0 && writes == 0 && setting == 99);
    /* Cancel (also delivered by Escape) and title-bar X never commit. */
    reset(0); selection = 1; PhpOptionsLanguageDlgProc(0, WM_COMMAND, IDCANCEL, 0);
    assert(setting == 0 && persisted == 0 && writes == 0 && saves == 0 && closed == IDCANCEL);
    reset(1); selection = 0; PhpOptionsLanguageDlgProc(0, WM_CLOSE, 0, 0);
    assert(setting == 1 && persisted == 1 && writes == 0 && saves == 0 && closed == IDCANCEL);
    /* Commit Chinese, simulate reload, then restore English. */
    reset(0); selection = 1; PhpOptionsLanguageDlgProc(0, WM_COMMAND, IDOK, 0);
    assert(setting == 1 && persisted == 1 && saves == 1 && closed == IDOK);
    setting = persisted; selection = -1; PhpOptionsLanguageDlgProc(0, WM_INITDIALOG, 0, 0);
    assert(selection == 1);
    selection = 0; PhpOptionsLanguageDlgProc(0, WM_COMMAND, IDOK, 0);
    assert(setting == 0 && persisted == 0 && saves == 2);
    /* No selection cannot become an unsigned invalid setting. */
    reset(0); selection = -1; PhpOptionsLanguageDlgProc(0, WM_COMMAND, IDOK, 0);
    assert(writes == 0 && saves == 0 && closed == 0);
    /* No-op OK avoids rewriting all settings. */
    reset(1); selection = 1; PhpOptionsLanguageDlgProc(0, WM_COMMAND, IDOK, 0);
    assert(writes == 0 && saves == 0 && closed == IDOK);
    /* Save failure rolls back memory and keeps dialog open for retry/cancel. */
    reset(0); selection = 1; failSave = 1; PhpOptionsLanguageDlgProc(0, WM_COMMAND, IDOK, 0);
    assert(setting == 0 && persisted == 0 && writes == 2 && saves == 1 && closed == 0 && errorShown == 1);
    return 0;
}
'''


class LanguageSettingsTests(unittest.TestCase):
    def test_real_dialog_control_flow(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if not compiler:
            self.skipTest("A C compiler is required for the portable dialog control-flow harness")
        source = (ROOT / "SystemInformer/options.c").read_text()
        start = source.index("static INT_PTR CALLBACK PhpOptionsLanguageDlgProc(")
        end = source.index("\nINT_PTR CALLBACK PhpOptionsGeneralDlgProc(", start)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "test.c").write_text(PRELUDE + source[start:end] + CASES)
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", str(path / "test.c"),
                            "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True)

    def test_default_and_startup_wiring(self):
        defaults = (ROOT / "SystemInformer/settings.c").read_text()
        startup = (ROOT / "SystemInformer/main.c").read_text()
        self.assertIn('PhpAddIntegerSetting(SETTING_UI_LANGUAGE, L"0")', defaults)
        self.assertIn('PhSetUiLanguage(PhGetIntegerSetting(SETTING_UI_LANGUAGE))', startup)
        self.assertLess(startup.index('PhLoadSettingsEx('), startup.index('PhSetUiLanguage('))
        source = (ROOT / "SystemInformer/options.c").read_text()
        self.assertNotIn('PhSetUiLanguage(', source, "Language must not hot-switch existing windows")


if __name__ == "__main__":
    unittest.main()
