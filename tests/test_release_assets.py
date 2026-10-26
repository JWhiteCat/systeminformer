"""Prerelease staging tests use fake PE fixtures; they do not run binaries."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_release', ROOT / 'tools/release/prepare_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
COMMIT = 'a' * 40


def fake_pe():
    data = bytearray(132)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    data[128:] = b'PE\0\0'
    return bytes(data)


class ReleaseAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'output'
        self.source.mkdir()
        self.dest = self.root / 'staged'
        self.payload = {'SystemInformer.exe': fake_pe(), 'LICENSE.txt': b'license',
                        'COPYRIGHT.txt': b'copyright', 'README.txt': b'readme'}
        (self.source / release.ASSETS[0]).write_bytes(fake_pe())
        self.write_zip()

    def write_zip(self):
        with zipfile.ZipFile(self.source / release.ASSETS[1], 'w') as archive:
            for name, content in self.payload.items():
                archive.writestr(name, content)
        self.write_hashes()

    def write_hashes(self):
        (self.source / 'systeminformer-build-checksums.txt').write_text(''.join(
            f'{name}\nSHA256: {release.digest(self.source / name).upper()}\n\n'
            for name in release.ASSETS))

    def test_stages_selected_assets_and_verifies(self):
        (self.source / 'unrelated.zip').write_bytes(b'not for distribution')
        release.stage(self.source, self.dest, COMMIT)
        release.verify(self.dest, COMMIT)
        self.assertEqual(set(p.name for p in self.dest.iterdir()), set(release.ASSETS) | {release.CHECKSUMS, release.MANIFEST})

    def test_deterministic_manifest_and_hashes(self):
        release.stage(self.source, self.dest, COMMIT)
        second = self.root / 'second'
        release.stage(self.source, second, COMMIT)
        for name in (release.CHECKSUMS, release.MANIFEST):
            self.assertEqual((self.dest / name).read_bytes(), (second / name).read_bytes())

    def test_does_not_overwrite_existing_destination(self):
        self.dest.mkdir()
        (self.dest / 'keep.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'empty'):
            release.stage(self.source, self.dest, COMMIT)
        self.assertEqual((self.dest / 'keep.txt').read_text(), 'keep')

    def test_missing_installer_fails(self):
        (self.source / release.ASSETS[0]).unlink()
        with self.assertRaises(ValueError):
            release.stage(self.source, self.dest, COMMIT)

    def test_bad_pe_fails(self):
        (self.source / release.ASSETS[0]).write_text('not a binary')
        self.write_hashes()
        with self.assertRaisesRegex(ValueError, 'Windows executable'):
            release.stage(self.source, self.dest, COMMIT)

    def test_missing_license_fails(self):
        del self.payload['LICENSE.txt']
        self.write_zip()
        with self.assertRaisesRegex(ValueError, 'LICENSE'):
            release.stage(self.source, self.dest, COMMIT)

    def test_unsafe_zip_path_fails(self):
        self.payload['../outside.txt'] = b'bad'
        self.write_zip()
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            release.stage(self.source, self.dest, COMMIT)

    def test_source_checksum_mismatch_fails(self):
        (self.source / release.ASSETS[0]).write_bytes(fake_pe() + b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            release.stage(self.source, self.dest, COMMIT)

    def test_corrupt_downloaded_asset_fails(self):
        release.stage(self.source, self.dest, COMMIT)
        (self.dest / release.ASSETS[0]).write_bytes(fake_pe() + b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            release.verify(self.dest, COMMIT)

    def test_wrong_commit_fails(self):
        release.stage(self.source, self.dest, COMMIT)
        with self.assertRaisesRegex(ValueError, 'commit mismatch'):
            release.verify(self.dest, 'b' * 40)

    def test_extra_staged_files_fail(self):
        release.stage(self.source, self.dest, COMMIT)
        (self.dest / 'unexpected.exe').write_bytes(fake_pe())
        with self.assertRaisesRegex(ValueError, 'exactly'):
            release.verify(self.dest, COMMIT)

    def test_bad_commit_format_fails(self):
        with self.assertRaisesRegex(ValueError, 'full lowercase'):
            release.stage(self.source, self.dest, 'master')

    def test_workflow_uploads_only_verified_prerelease_directory(self):
        workflow = (ROOT / '.github/workflows/msbuild.yml').read_text()
        self.assertLess(workflow.index('Verify and stage bilingual'), workflow.index('Upload verified prerelease'))
        self.assertIn('path: build/prerelease/*', workflow)
        self.assertIn('name: systeminformer-prerelease-${{ github.sha }}', workflow)


if __name__ == '__main__':
    unittest.main()
