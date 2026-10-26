/*
 * Copyright (c) 2022 Winsider Seminars & Solutions, Inc.  All rights reserved.
 *
 * This file is part of System Informer.
 *
 * Authors:
 *
 *     dmex    2011-2026
 *
 */

#include "updater.h"
#include <trace.h>

PPH_PLUGIN PluginInstance;
PH_CALLBACK_REGISTRATION PluginLoadCallbackRegistration;
PH_CALLBACK_REGISTRATION PluginUnloadCallbackRegistration;
PH_CALLBACK_REGISTRATION PluginMenuItemCallbackRegistration;
PH_CALLBACK_REGISTRATION MainMenuInitializingCallbackRegistration;
PH_CALLBACK_REGISTRATION MainWindowShowingCallbackRegistration;
PH_CALLBACK_REGISTRATION PluginShowOptionsCallbackRegistration;

/**
 * Callback function called when the plugin is loaded.
 *
 * \param Parameter Startup parameters.
 * \param Context Unused.
 */
_Function_class_(PH_CALLBACK_FUNCTION)
VOID NTAPI LoadCallback(
    _In_opt_ PVOID Parameter,
    _In_opt_ PVOID Context
    )
{
    NOTHING;
}

/**
 * Callback function called when the plugin is unloading.
 *
 * \param Parameter Unload parameters.
 * \param Context Unused.
 */
_Function_class_(PH_CALLBACK_FUNCTION)
VOID NTAPI UnloadCallback(
    _In_opt_ PVOID Parameter,
    _In_opt_ PVOID Context
    )
{
    BOOLEAN SessionEnding = (BOOLEAN)PtrToUlong(Parameter);

    if (SessionEnding)
        return;

    if (PhGetIntegerSetting(SETTING_NAME_TOAST_NOTIFICATIONS))
        UpdaterHideActiveToasts();
}

/**
 * Callback function called when the main window is showing.
 *
 * \param Parameter Unused.
 * \param Context Unused.
 */
_Function_class_(PH_CALLBACK_FUNCTION)
VOID NTAPI MainWindowShowingCallback(
    _In_opt_ PVOID Parameter,
    _In_opt_ PVOID Context
    )
{
    // Check if there's a pending update and the user wants the update prompt before the main window.
    if (PhGetIntegerSetting(SETTING_NAME_UPDATE_MODE) && PhGetIntegerSetting(SETTING_NAME_UPDATE_AVAILABLE))
    {
        PPH_STRING string;

        if (string = PhGetStringSetting(SETTING_NAME_UPDATE_DATA))
        {
            // Clear the update cache. (dmex)
            PhSetStringSetting(SETTING_NAME_UPDATE_DATA, L"");
            PhSetIntegerSetting(SETTING_NAME_UPDATE_AVAILABLE, FALSE);

            // Show the update prompt. (dmex)
            ShowStartupUpdateDialog(string);

            PhDereferenceObject(string);
        }
    }

    // Check if the user want's us to auto-check for updates.
    if (PhGetIntegerSetting(SETTING_NAME_AUTO_CHECK))
    {
        // All good, queue up our update check.
        StartInitialCheck();
    }
}

/**
 * Callback function called when the main menu is initializing.
 *
 * \param Parameter A pointer to a PH_PLUGIN_MENU_INFORMATION structure.
 * \param Context Unused.
 */
_Function_class_(PH_CALLBACK_FUNCTION)
VOID NTAPI MainMenuInitializingCallback(
    _In_ PVOID Parameter,
    _In_ PVOID Context
    )
{
    PPH_PLUGIN_MENU_INFORMATION menuInfo = Parameter;

    if (menuInfo->u.MainMenu.SubMenuIndex == PH_MENU_ITEM_LOCATION_HELP)
    {
        PhInsertEMenuItem(menuInfo->Menu, PhPluginCreateEMenuItem(PluginInstance, 0, UPDATE_MENUITEM_UPDATE, PhTranslateUiText(L"Check for &updates"), NULL), 0);
    }
}

/**
 * Callback function called when a plugin menu item is selected.
 *
 * \param Parameter A pointer to a PH_PLUGIN_MENU_ITEM structure.
 * \param Context Unused.
 */
_Function_class_(PH_CALLBACK_FUNCTION)
VOID NTAPI MenuItemCallback(
    _In_ PVOID Parameter,
    _In_ PVOID Context
    )
{
    PPH_PLUGIN_MENU_ITEM menuItem = Parameter;
    PH_RELEASE_CHANNEL channel;
    PPH_UPDATER_CONTEXT context;

    switch (menuItem->Id)
    {
    case UPDATE_MENUITEM_UPDATE:
        ShowUpdateDialog(NULL);
        return;
    case UPDATE_SWITCH_RELEASE:
        channel = PhReleaseChannel;
        break;
    //case UPDATE_SWITCH_PREVIEW:
    //    channel = PhPreviewChannel;
    //    break;
    case UPDATE_SWITCH_CANARY:
        channel = PhCanaryChannel;
        break;
    //case UPDATE_SWITCH_DEVELOPER:
    //    channel = PhDeveloperChannel;
    //    break;
    default:
        return;
    }

    if (PhGetBuildReleaseChannel() != channel)
    {
        context = CreateUpdateContext(FALSE);
        context->Channel = channel;
        context->SwitchingChannel = TRUE;
        ShowUpdateDialog(context);
    }
}

/**
 * Callback function called when the options window is initializing.
 *
 * \param Parameter A pointer to a PH_PLUGIN_OPTIONS_POINTERS structure.
 * \param Context Unused.
 */
_Function_class_(PH_CALLBACK_FUNCTION)
VOID NTAPI ShowOptionsCallback(
    _In_ PVOID Parameter,
    _In_ PVOID Context
    )
{
    PPH_PLUGIN_OPTIONS_POINTERS optionsEntry = (PPH_PLUGIN_OPTIONS_POINTERS)Parameter;

    optionsEntry->CreateSection(
        L"Updater",
        NtCurrentImageBase(),
        MAKEINTRESOURCE(IDD_OPTIONS),
        OptionsDlgProc,
        NULL
        );
}

/**
 * The entry point for the plugin DLL.
 *
 * \param Instance The instance handle of the DLL.
 * \param Reason The reason for calling the function.
 * \param Reserved Unused.
 * \return LOGICAL TRUE if the initialization was successful, FALSE otherwise.
 */
LOGICAL DllMain(
    _In_ HINSTANCE Instance,
    _In_ ULONG Reason,
    _Reserved_ PVOID Reserved
    )
{
    switch (Reason)
    {
    case DLL_PROCESS_ATTACH:
        {
            PPH_PLUGIN_INFORMATION info;

            // Deliberately inert in this unofficial bilingual fork. Register only
            // descriptive metadata: never register update callbacks or settings.
            // Shipping this DLL also replaces older copies during installation,
            // so existing AutoCheck/update-cache preferences cannot re-enable it.
            PluginInstance = PhRegisterPlugin(PLUGIN_NAME, Instance, &info);
            if (!PluginInstance)
                return FALSE;

            info->DisplayName = L"Update Checker (disabled in bilingual fork)";
            info->Description = L"Upstream binary updates are disabled to preserve this unofficial bilingual build. Download updates from JWhiteCat/systeminformer Releases.";
        }
        break;
    }

    return TRUE;
}
