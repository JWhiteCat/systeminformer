# 简体中文 / English UI

## 使用

构建此分支后，在 **Options → General → Language…**（**选项 → 常规 → 语言…**）
中选择 **简体中文** 或 **English**，点击 **OK / 确定** 保存。语言在重启后生效；
可以立即重启，也可以稍后手动重启。取消、Esc 或关闭语言对话框不会修改选择。
原有“选项”窗口的其他设置仍沿用上游自动保存行为。

选择保存在正常配置文件的 `UiLanguage` 整数设置中：`0` 为英文（默认），`1` 为简体中文。
其他数值按英文显示。英文界面可随时通过相同入口恢复，不依赖 Windows 系统语言。
若禁用了配置保存或文件不可写，会显示保存错误并回滚本次语言选择。

## Coverage and fallback

- The main executable and all 12 bundled plugin resource scripts have parallel
  Chinese dialogs, captions and controls. English resources remain intact.
- Explicit runtime translations cover common menus, process/service/network
  columns, property pages, settings categories, plugin menus/columns and toolbar
  labels. Process names, paths, protocol identifiers, symbols, user data and
  settings keys are never passed through a blanket translation hook.
- This is not a claim that every upstream string is translated: specialized
  dynamic error messages, statistics, help text, third-party/system dialogs and
  newly added strings may remain English. Missing catalog entries return the
  original English pointer. Technical/product names are intentionally preserved.
- No installation, security, signing, kernel-driver or update behavior is changed.
  Build the app and bundled plugins together: translated plugins import the new
  UI translation function from the matching executable.

## Architecture

`phlib/uilang.c` owns the process-wide startup language and immutable string
catalog. `PhTranslateUiText` is used only at explicit display boundaries. Returned
strings are borrowed, read-only storage, not allocations. Settings changes do not
hot-switch existing windows or worker threads.

`PhLoadResource` requests the exact selected language for dialogs, menus and
string tables; Chinese misses fall back to exact en-US, then the existing neutral
loader behavior for foreign modules. Non-UI resources retain upstream behavior.
Native property sheets also use a language-aware wrapper that loads their dialog
template explicitly, while retaining already-indirect templates and callbacks.
This avoids changing the thread locale or translating arbitrary window content.

English `.rc` files are the source of truth. Their checked-in `.zh-CN.rc` siblings
are generated caption-only copies included by the English resource scripts; IDs,
styles, font declarations, layout coordinates and accelerator resources are
preserved. Generated RC files use UTF-8; MSBuild selects `/8` and CMake selects
`/c65001`. Included files do not use code-page pragmas, which MSBuild's UTF-8-only
mode rejects. C catalog strings use
ASCII Unicode escapes so compiler source encodings do not affect Chinese text.

## Maintaining translations

```sh
python3 localization/generate_resources.py
python3 tools/localization/generate_dynamic.py
python3 localization/generate_resources.py --check
python3 tools/localization/generate_dynamic.py --check
python3 -m unittest discover -s tests -p 'test_ui_*.py' -v
python3 -m unittest discover -s localization -p test_resources.py -v
python3 tools/localization/test_dynamic.py
python3 tools/localization/test_core.py
```

- `resources.zh-CN.json`: RC captions; preserve RC escape spellings and doubled
  quotes are handled by the generator. Add translations here, not in generated RC.
- `dynamic.zh-CN.json`: main application's runtime English → Chinese strings.
- `plugins.zh-CN.json`: additional runtime plugin strings; shared entries live in
  the main catalog. JSON strings contain decoded controls (`\b`, `\t`, `\n`).
- Wrap only a known display literal with `PhTranslateUiText(L"English")`. Never
  wrap identifiers, settings keys, formatted user data or static initializers.
  For static UI structures, translate at the final display boundary instead.
- Preserve format specifiers, the original accelerator character (for example
  `&Copy` → `复制(&C)`) and the exact suffix after a menu `\b`/`\t` separator.

## Verification limits and Windows checklist

Portable tests compile the actual localization functions and language-dialog
procedure with minimal mocked Windows/settings interfaces, checking both language
values, unknown values, English restoration, missing strings, Cancel/Escape/X,
save-failure rollback and resource fallback order. Resource tests check structural
parity and generated-file freshness. These are **not** a Windows build or GUI test.

For native validation use the upstream Visual Studio 2022+ setup documented in
`build/README.md` (`build_init.cmd`, then `build_release.cmd`), or existing Windows
CI. Before distributing binaries, verify on Windows:

1. Start in English, switch to Chinese, restart, and reopen the language selector.
2. Inspect menus, tabs, property dialogs and bundled plugins at 100%, 150%, 200%
   DPI; check Chinese glyph fallback and clipping, especially long labels.
3. Change selection then Cancel, Esc and X separately; restart and confirm unchanged.
4. Switch back to English on Chinese Windows and verify both resources and menus.
5. Try an unknown `UiLanguage`, a read-only settings file and settings-disabled
   mode; confirm fallback/error behavior and no false persistence success.
6. Exercise menu accelerators and formatted messages; compare IDs/actions with
   upstream English behavior. OS-provided buttons can follow the OS display language.
