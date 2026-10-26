/*
 * System Informer user-interface language support.
 * English is the source language and the unconditional fallback.
 */

#include <ph.h>

static volatile LONG PhpUiLanguage = PH_UI_LANGUAGE_ENGLISH;

typedef struct _PH_UI_TRANSLATION
{
    PCWSTR English;
    PCWSTR Translation;
} PH_UI_TRANSLATION;

static const PH_UI_TRANSLATION PhpChineseUiTranslations[] =
{
#include <uilang_zh_cn.h>
};

/** Set once after loading settings, before creating UI or starting UI threads.
 * Changes to the persisted setting take effect after restarting the application.
 * Unknown values deliberately select English, independent of the OS language.
 */
VOID NTAPI PhSetUiLanguage(
    _In_ ULONG Language
    )
{
    InterlockedExchange(&PhpUiLanguage,
        Language == PH_UI_LANGUAGE_CHINESE_SIMPLIFIED ? PH_UI_LANGUAGE_CHINESE_SIMPLIFIED : PH_UI_LANGUAGE_ENGLISH);
}

ULONG NTAPI PhGetUiLanguage(
    VOID
    )
{
    return (ULONG)InterlockedCompareExchange(&PhpUiLanguage, 0, 0);
}

/** Translate explicitly identified UI literals, never identifiers or user data.
 * The return value is borrowed immutable storage. Do not free or modify it.
 * A missing translation, English mode, and NULL preserve the input pointer.
 */
PCWSTR NTAPI PhTranslateUiText(
    _In_opt_ PCWSTR English
    )
{
    if (!English || PhGetUiLanguage() != PH_UI_LANGUAGE_CHINESE_SIMPLIFIED)
        return English;

    for (ULONG i = 0; i < RTL_NUMBER_OF(PhpChineseUiTranslations); i++)
    {
        if (wcscmp(English, PhpChineseUiTranslations[i].English) == 0)
            return PhpChineseUiTranslations[i].Translation;
    }

    return English;
}
