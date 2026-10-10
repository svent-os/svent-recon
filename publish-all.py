#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location


def validated_packages(root, output):
    specification = spec_from_file_location('recon_builder', root / 'build-all.py')
    builder = module_from_spec(specification)
    specification.loader.exec_module(builder)
    tools = builder.validate_repository(root)
    recipes = {folder.name: folder for folder in tools}
    recipes['sv-tools-recon'] = root / 'metapackage'
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    records = manifest.get('packages', [])
    if manifest.get('schema') != 1 or len(records) != len(recipes):
        raise RuntimeError('Incomplete build manifest; build all packages first.')
    if {record['package'] for record in records} != set(recipes):
        raise RuntimeError('Build manifest does not match the current tool set.')
    artifacts = []
    for record in records:
        folder = recipes[record['package']]
        version = re.search(r'^\S+ \(([^)]+)\)', (folder / 'debian/changelog').read_text(encoding='utf-8')).group(1)
        if record['version'] != version:
            raise RuntimeError('Outdated build: ' + record['package'])
        path = (output / record['filename']).resolve()
        if path.parent != output or not path.is_file() or path.suffix != '.deb':
            raise RuntimeError('Missing or invalid package file: ' + record['package'])
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != record['sha256']:
            raise RuntimeError('Package checksum mismatch: ' + record['package'])
        artifacts.append(path)
    return artifacts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', type=Path, default=Path.home() / 'svent-recon-build')
    parser.add_argument('--repository', type=Path, default=Path(os.environ.get('SVENT_PKGS', str(Path.home() / 'pkgs'))))
    parser.add_argument('--validate-only', action='store_true')
    options = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = options.build_dir.expanduser().resolve()
    artifacts = validated_packages(root, output)
    print(f'[+] Verified {len(artifacts)} package files before importing anything.', flush=True)
    if options.validate_only:
        return
    repository = options.repository.expanduser().resolve()
    for filename in ('conf/distributions', 'sventos-setup.sh', 'svent-archive-keyring.gpg'):
        if not (repository / filename).is_file():
            raise RuntimeError('Missing repository file: ' + filename)
    environment = os.environ.copy()
    environment['SVENT_PKGS'] = str(repository)
    for artifact in artifacts:
        subprocess.run(['reprepro', '-b', str(repository), 'includedeb', 'rolling', str(artifact)], check=True)
    subprocess.run(['reprepro', '-b', str(repository), 'export', 'rolling'], check=True)
    subprocess.run(['reprepro', '-b', str(repository), 'check', 'rolling'], check=True)
    subprocess.run(['svent-pkg', 'publish'], env=environment, check=True)
    print('[+] Recon packages published successfully.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        print('[-] ' + str(error), file=sys.stderr)
        sys.exit(1)
