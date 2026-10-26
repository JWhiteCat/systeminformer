## 非官方中英双语测试版 / Unofficial bilingual preview

This is a community fork by JWhiteCat, **not an official Winsider release**.

### 下载 / Downloads

- `systeminformer-build-win64-bin.zip`: x64 portable build. Prefer this for a reversible trial in an isolated Windows test environment.
- `systeminformer-build-release-setup.exe`: installer produced by the repository's existing build system. The word `release` in the filename is a build channel, not official-release status.
- `SHA256SUMS.txt` and `release-manifest.json`: verify downloads and identify the exact source commit.

### 语言与更新 / Language and updates

Open **Options → General → Language…**, select **简体中文** or **English**, save and restart. Some specialized text falls back to English.

The bundled official Updater is deliberately disabled, including old saved auto-update preferences. It will not offer official binaries that overwrite the bilingual fork. Obtain future fork updates manually from this repository's Releases page.

### 验证范围与限制 / Validation and limitations

The exact source commit passed localization tests, Windows CMake and MSBuild CI. Package existence, PE header, ZIP integrity, bundled license notices and SHA256 checks were verified; uploaded assets were downloaded again and verified before publication.

**Not manually tested:** Windows installation/uninstallation, GUI interaction, language restart persistence on real Windows, Chinese font clipping and 100%/150%/200% DPI.

**Unsigned unofficial binaries:** no Authenticode publisher trust or official signature is claimed. Do not bypass browser or Windows security warnings. This preview does not supply a verified production-signed kernel driver matching the fork; privileged kernel functions may be unavailable. Do not disable Secure Boot or driver-signature enforcement.

Keep your existing installation and settings backed up. This is a preview for evaluation, not a replacement for a trusted production system-management tool. Upstream copyright and license notices remain included.
