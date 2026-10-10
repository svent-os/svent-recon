#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


def fields(text):
    result = {}
    current = None
    for line in text.splitlines():
        if line.startswith((' ', '\t')) and current:
            result[current] += ' ' + line.strip()
        elif ': ' in line:
            current, value = line.split(': ', 1)
            result[current] = value
    return result


def run(command, directory, log=None):
    print('[+] ' + ' '.join(map(str, command)), flush=True)
    environment = os.environ.copy()
    environment['LC_ALL'] = 'C'
    if log is None:
        return subprocess.run(command, cwd=directory, env=environment, check=True,
                              capture_output=True, text=True).stdout.strip()
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=directory, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors='replace')
        for line in process.stdout:
            print(line, end='', flush=True)
            stream.write(line)
        status = process.wait()
    if status:
        raise RuntimeError('Command failed; see ' + str(log))
    return ''


def validate_repository(root):
    tools = sorted(folder for folder in (root / 'tools').glob('sv-*') if folder.is_dir())
    packages = []
    for folder in tools:
        control = (folder / 'debian/control').read_text(encoding='utf-8')
        binary = fields(control.split('\n\n', 1)[1])
        if binary['Package'] != folder.name:
            raise RuntimeError('Package name mismatch: ' + folder.name)
        catalogs = list((folder / 'catalog.d').glob('*.json'))
        if len(catalogs) != 1:
            raise RuntimeError('Expected one catalog: ' + folder.name)
        catalog = json.loads(catalogs[0].read_text(encoding='utf-8'))
        if catalog['group'] != 'recon' or catalog['executables'] != [folder.name]:
            raise RuntimeError('Invalid Recon command registration: ' + folder.name)
        if not (folder / 'launchers' / folder.name).is_file():
            raise RuntimeError('Missing global launcher: ' + folder.name)
        if catalog['packaging'] == 'svent':
            pin = json.loads((folder / 'upstream.json').read_text(encoding='utf-8'))
            if pin['version'] in ('latest', 'master', 'main'):
                raise RuntimeError('Unpinned source: ' + folder.name)
            if 'sh ./build.sh' not in (folder / 'debian/rules').read_text(encoding='utf-8'):
                raise RuntimeError('Missing automatic source build: ' + folder.name)
        packages.append(folder.name)
    control = (root / 'metapackage/debian/control').read_text(encoding='utf-8')
    dependencies = fields(control.split('\n\n', 1)[1])['Depends']
    included = set(re.findall(r'\bsv-[a-z0-9+.-]+', dependencies))
    if included != set(packages):
        raise RuntimeError('Metapackage mismatch: missing=' + str(set(packages) - included)
                           + ', extra=' + str(included - set(packages)))
    return tools


def collect_package(folder, output, architecture, compiled):
    control = (folder / 'debian/control').read_text(encoding='utf-8')
    binary = fields(control.split('\n\n', 1)[1])
    name = binary['Package']
    version = run(['dpkg-parsechangelog', '-S', 'Version'], folder)
    target_architecture = binary['Architecture']
    if target_architecture == 'any':
        target_architecture = architecture
    artifact = folder.parent / f'{name}_{version}_{target_architecture}.deb'
    if not artifact.is_file():
        raise RuntimeError('Missing built package: ' + str(artifact))
    actual = fields(run(['dpkg-deb', '--field', str(artifact)], folder))
    if (actual.get('Package'), actual.get('Version'), actual.get('Architecture')) != (name, version, target_architecture):
        raise RuntimeError('Built package metadata mismatch: ' + name)
    process = subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(artifact)], stdout=subprocess.PIPE)
    names = set()
    executable_verified = not compiled
    with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
        for member in archive:
            filename = member.name.removeprefix('./')
            names.add(filename)
            if filename == 'usr/bin/' + name and not member.mode & 0o111:
                raise RuntimeError('Launcher is not executable: ' + name)
            if compiled:
                pin = json.loads((folder / 'upstream.json').read_text(encoding='utf-8'))
                if filename == 'usr/bin/' + pin['executable']:
                    header = archive.extractfile(member).read(20)
                    if header[:4] != b'\x7fELF' or int.from_bytes(header[18:20], 'little') != 62:
                        raise RuntimeError('Expected an amd64 ELF executable: ' + name)
                    executable_verified = bool(member.mode & 0o111)
    if process.wait():
        raise RuntimeError('Cannot inspect package archive: ' + name)
    if name.startswith('sv-') and name != 'sv-tools-recon':
        catalog_name = next((folder / 'catalog.d').glob('*.json')).name
        required = {'usr/bin/' + name, 'usr/share/svent/catalog.d/' + catalog_name}
        if not required.issubset(names) or not executable_verified:
            raise RuntimeError('Incomplete package contents: ' + name)
    destination = output / artifact.name
    shutil.copy2(artifact, destination)
    with destination.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(package=name, version=version, architecture=target_architecture,
                filename=destination.name, sha256=checksum)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path.home() / 'svent-recon-build')
    parser.add_argument('--validate-only', action='store_true')
    options = parser.parse_args()
    root = Path(__file__).resolve().parent
    tools = validate_repository(root)
    print(f'[+] Validated {len(tools)} tools and the complete metapackage.')
    if options.validate_only:
        return
    if sys.platform != 'linux':
        raise RuntimeError('Build the Debian packages on Linux.')
    architecture = run(['dpkg', '--print-architecture'], root)
    if architecture != 'amd64':
        raise RuntimeError('These upstream recipes currently target amd64.')
    output = options.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / 'manifest.json'
    manifest.unlink(missing_ok=True)
    logs = output / 'logs'
    logs.mkdir(exist_ok=True)
    recipes = tools + [root / 'metapackage']
    for folder in recipes:
        (folder / 'debian/rules').chmod(0o755)
        run(['dpkg-checkbuilddeps'], folder)
    for folder in tools:
        catalog = json.loads(next((folder / 'catalog.d').glob('*.json')).read_text(encoding='utf-8'))
        if catalog['packaging'] == 'debian':
            policy = run(['apt-cache', 'policy', catalog['package']], root)
            if not re.search(r'Candidate:\s+(?!\(none\))\S+', policy):
                raise RuntimeError('No APT candidate for Debian dependency: ' + catalog['package'])
    records = []
    for index, folder in enumerate(recipes, 1):
        print(f'[+] Building {index}/{len(recipes)}: {folder.name}', flush=True)
        run(['dpkg-buildpackage', '-b', '-us', '-uc'], folder, logs / (folder.name + '.log'))
        records.append(collect_package(folder, output, architecture, (folder / 'build.sh').is_file()))
    candidates = [str(output / record['filename']) for record in records]
    run(['apt-get', '--simulate', 'install', *candidates], root, logs / 'installation-check.log')
    temporary = manifest.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(schema=1, packages=records), indent=2) + '\n', encoding='utf-8')
    temporary.replace(manifest)
    print('[+] All packages built and checked. Manifest: ' + str(manifest))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print('[-] ' + str(error), file=sys.stderr)
        sys.exit(1)
