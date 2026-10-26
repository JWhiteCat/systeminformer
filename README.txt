UNOFFICIAL BILINGUAL PREVIEW - JWhiteCat/systeminformer

This is not an official Winsider release. The fork supports English and
Simplified Chinese under Options > General > Language; save and restart.
Some specialized text falls back to English. The bundled Updater is disabled:
get fork updates manually from https://github.com/JWhiteCat/systeminformer/releases

No Authenticode signing or production-signed matching kernel driver is claimed.
Privileged kernel functions may be unavailable. Do not disable Windows security
protections or bypass browser/OS security warnings. GUI, DPI and installation
flows have not been manually tested. Use an isolated Windows test environment
and preserve your existing installation/settings. See the release page for the
exact source commit, CI evidence, SHA256 checksums and preview limitations.

System Informer is a powerful free and open source process viewer.

## Getting started

Simply run SystemInformer.exe to start System Informer. There are two
versions, 32-bit (x86) and 64-bit (x64). If you are not sure which
version to use, open Control Panel > System and check the "System
type". You cannot run the 32-bit version of System Informer on a
64-bit system and expect it to work correctly, unlike other programs.

## System requirements

Windows 10 or higher, 32-bit or 64-bit.

## Settings

If you are running System Informer from a USB drive, you may want to
save System Informer's settings there as well. To do this, create a
blank file named "SystemInformer.exe.settings.xml" in the same
directory as SystemInformer.exe. You can do this using Windows Explorer:

1. Make sure "Hide extensions for known file types" is unticked in
   Tools > Folder options > View.
2. Right-click in the folder and choose New > Text Document.
3. Rename the file to SystemInformer.exe.settings.xml (delete the ".txt"
   extension).

## Plugins

Plugins can be configured from Hacker > Plugins.

If you experience any crashes involving plugins, make sure they
are up to date.

The ExtendedTools plugin is only available for Windows Vista and
above. Disk and Network information provided by this plugin is
only available when running Process Hacker with administrative
rights.
