# Unofficial bilingual preview releases

This is JWhiteCat's fork, **not an official Winsider release**. English remains
available; choose **Options → General → Language…**, save, and restart to switch
between English and 简体中文. Some specialized text falls back to English.

## Update behavior

The bundled Updater plugin is deliberately inert. It registers descriptive plugin
metadata but no callbacks or preferences, so old AutoCheck settings and cached
upstream update offers cannot replace this fork. It is included to overwrite an
older bundled Updater.dll during installation, rather than merely omitted.
Download new fork versions manually from this repository's Releases page.
No fork update server, credentials or signing keys are configured.

## Preview limitations

- Unsigned unofficial binaries: no Authenticode trust or publisher identity is
  claimed. Do not bypass OS/browser security warnings to install them.
- Native build CI is not GUI testing. Installation/uninstallation, Chinese glyphs,
  clipping, 100%/150%/200% DPI, language restart persistence and interaction flows
  have not been manually verified on Windows.
- The ordinary release build does not supply a verified production-signed kernel
  driver matching this fork. Some privileged kernel features may be unavailable.
  Do not disable Secure Boot, driver-signature enforcement or other protections.
- Test in an appropriate isolated Windows environment first. Prefer the x64
  portable ZIP for a reversible trial; keep your existing installation/settings.
- Neither the setup package nor its filename constitutes an official release or
  proof that every System Informer feature works in this fork.

## Release procedure

1. Push reviewed changes to master without force. Let localization, CMake and
   MSBuild CI all finish successfully for the **same commit**.
2. Release CI stages the setup EXE, x64 portable ZIP, SHA256SUMS.txt and a source manifest; missing files,
   checksum mismatches and malformed packages fail rather than publish partial
   output. It uploads a commit-named `systeminformer-prerelease-<SHA>` artifact.
3. After reviewing the exact commit and its test results, push a new immutable
   `bilingual-vYYYY.MM.DD-preview.N` tag pointing to that commit. Do not move an
   existing release tag. Tag publication is a separate explicit action.
4. The bilingual-prerelease workflow verifies all three successful push workflows
   for that SHA, downloads only its package artifact, rechecks hashes, creates a
   **draft prerelease**, uploads the assets and publishes only the complete draft.
   It does not mark this preview as Latest or upload canary installers/PDBs.
5. Inspect the public release page, commit/tag, four assets and their hashes.
   If publication fails, inspect its existing draft before retrying; the workflow
   intentionally refuses to overwrite a pre-existing release.

Future releases still require source/build review and a deliberately created tag.

## Verify downloaded packages without running them

The CI staging helper cross-checks `CustomBuildTool`'s original SHA256 file,
checks the installer's PE header and portable ZIP integrity, and requires
README, copyright and license notices plus the portable executable. It rejects
unsafe or duplicate ZIP paths and never extracts or executes the binaries.

After downloading and unpacking the CI artifact into a fresh directory:

```sh
python tools/release/prepare_release.py --verify --destination <download-directory> --commit <expected-full-sha>
```

Exactly four files must be present: `systeminformer-build-release-setup.exe`,
`systeminformer-build-win64-bin.zip`, `SHA256SUMS.txt`, and
`release-manifest.json`. The manifest must match the expected source commit and
both asset hashes. Checksums establish integrity, not Authenticode trust or GUI
correctness. For staging a fresh build, omit `--verify` (defaults to source
`build/output`, destination `build/prerelease`); nonempty output is never replaced.

Portable helper tests: `python -m unittest discover -s tests -p 'test_release_assets.py' -v`.
