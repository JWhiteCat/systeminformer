#!/usr/bin/env python3
"""Verify and stage the fork's selected prerelease assets. Never executes binaries."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import zipfile

ASSETS = ('systeminformer-build-release-setup.exe', 'systeminformer-build-win64-bin.zip')
CHECKSUMS = 'SHA256SUMS.txt'
MANIFEST = 'release-manifest.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_pe(data, name):
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError(f'{name}: not a Windows executable')
    offset = struct.unpack_from('<I', data, 60)[0]
    if offset < 64 or offset + 4 > len(data) or data[offset:offset + 4] != b'PE\0\0':
        raise ValueError(f'{name}: invalid PE header')


def check_payloads(directory):
    for name in ASSETS:
        path = directory / name
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError(f'Missing or invalid asset: {name}')
    check_pe((directory / ASSETS[0]).read_bytes(), ASSETS[0])
    with zipfile.ZipFile(directory / ASSETS[1]) as archive:
        names = archive.namelist()
        normalized = [name.replace('\\', '/') for name in names]
        folded = [name.casefold() for name in normalized]
        if len(folded) != len(set(folded)):
            raise ValueError('Duplicate ZIP paths')
        if any(stat.S_ISLNK(info.external_attr >> 16) for info in archive.infolist()):
            raise ValueError('ZIP symlinks are not allowed')
        for name in normalized:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or ':' in name:
                raise ValueError(f'Unsafe ZIP path: {name}')
        for required in ('LICENSE.txt', 'COPYRIGHT.txt', 'README.txt', 'SystemInformer.exe'):
            if required.casefold() not in folded:
                raise ValueError(f'Portable ZIP missing {required}')
        executable = names[folded.index('systeminformer.exe')]
        check_pe(archive.read(executable), executable)
        if archive.testzip() is not None:
            raise ValueError('Corrupt ZIP payload')


def source_hashes(path):
    """Read CustomBuildTool's filename / SHA256 pair format without ambiguity."""
    lines = [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if len(lines) % 2:
        raise ValueError('Malformed upstream checksums')
    result = {}
    for name, value in zip(lines[0::2], lines[1::2]):
        if name in result or not re.fullmatch(r'SHA256: [0-9a-fA-F]{64}', value):
            raise ValueError('Duplicate or malformed upstream checksum')
        result[name] = value[8:].lower()
    return result


def stage(source, destination, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected full lowercase source commit SHA')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Destination must be empty; refusing to replace existing release files')
    check_payloads(source)
    expected = source_hashes(source / 'systeminformer-build-checksums.txt')
    hashes = {name: digest(source / name) for name in ASSETS}
    for name, actual in hashes.items():
        if expected.get(name) != actual:
            raise ValueError(f'Upstream checksum mismatch or missing: {name}')
    destination.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        shutil.copyfile(source / name, destination / name)
    (destination / CHECKSUMS).write_text(''.join(f'{hashes[name]}  {name}\n' for name in ASSETS), encoding='utf-8', newline='\n')
    manifest = {'schema': 1, 'source_commit': commit, 'assets': hashes,
                'status': 'unofficial-bilingual-prerelease',
                'limitations': ['No Authenticode signing performed', 'Windows GUI and DPI not manually tested',
                                'Signed kernel driver compatibility not guaranteed']}
    (destination / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')
    verify(destination, commit)


def verify(directory, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected full lowercase source commit SHA')
    expected_names = set(ASSETS) | {CHECKSUMS, MANIFEST}
    if {path.name for path in directory.iterdir()} != expected_names:
        raise ValueError('Staged directory must contain exactly the selected assets, checksums and manifest')
    if any(path.is_symlink() for path in directory.iterdir()):
        raise ValueError('Staged files must not be symlinks')
    manifest = json.loads((directory / MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or manifest.get('source_commit') != commit:
        raise ValueError('Manifest source commit mismatch')
    hashes = {name: digest(directory / name) for name in ASSETS}
    if manifest.get('assets') != hashes:
        raise ValueError('Manifest asset checksum mismatch')
    expected_text = ''.join(f'{hashes[name]}  {name}\n' for name in ASSETS)
    if (directory / CHECKSUMS).read_text(encoding='utf-8') != expected_text:
        raise ValueError('SHA256SUMS mismatch')
    check_payloads(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('build/output'))
    parser.add_argument('--destination', type=Path, default=Path('build/prerelease'))
    parser.add_argument('--commit', required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        verify(args.destination, args.commit)
    else:
        stage(args.source, args.destination, args.commit)
    print(f'Verified {len(ASSETS)} assets for {args.commit}')


if __name__ == '__main__':
    main()
