"""Install an offline Phoenix payload through the real application CLI.

Records original and added files without changing the sealed clean baseline.
Does not launch the fixtures or infer runtime success from installation success.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import time


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size}
            for p in sorted(folder.rglob('*')) if p.is_file()}


def architecture(path):
    with path.open('rb') as stream:
        assert stream.read(2) == b'MZ', f'Not a PE file: {path.name}'
        stream.seek(0x3c)
        offset = struct.unpack('<I', stream.read(4))[0]
        stream.seek(offset)
        assert stream.read(4) == b'PE\0\0', f'Invalid PE signature: {path.name}'
        return {0x14c: 'x86', 0x8664: 'x64'}[struct.unpack('<H', stream.read(2))[0]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    suite, output = args.suite.resolve(), args.output.resolve()
    installer, payload = args.installer.resolve(), args.payload.resolve()
    assert installer.is_file() and payload.is_dir(), 'Missing installer or payload'
    output.mkdir(parents=True, exist_ok=False)
    matrix = json.loads((suite / 'matrix.json').read_text(encoding='utf-8'))
    report = {'schema': 1, 'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'installer_sha256': digest(installer), 'games_launched': False,
              'runtime_validated': False, 'games': []}

    def save():
        (output / 'installations.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    for game in matrix['games']:
        if args.only and game['id'] not in args.only:
            continue
        folder = (suite / game['install_directory']).resolve()
        exe = (suite / game['executable']).resolve()
        assert folder.is_relative_to(suite / 'games'), 'Game path outside this suite'
        assert exe.parent == folder and digest(exe) == game['sha256'], 'Fixture changed'
        original = snapshot(folder)
        item = {'id': game['id'], 'api': game['api'], 'architecture': game['architecture'],
                'original_files': original, 'passed': False}
        report['games'].append(item)
        save()
        try:
            process = subprocess.run([str(installer), '--install', str(exe), '--offline',
                                      '--payload', str(payload)], cwd=installer.parent,
                                     capture_output=True, text=True, timeout=180)
            (output / (game['id'] + '.stdout.log')).write_text(process.stdout, encoding='utf-8')
            (output / (game['id'] + '.stderr.log')).write_text(process.stderr, encoding='utf-8')
            item['exit_code'] = process.returncode
            assert process.returncode == 0, process.stderr.strip() or process.stdout.strip()
            addon = folder / ('Phoenix' + game['addon_extension'])
            assert architecture(addon) == game['architecture'], 'Wrong add-on architecture'
            assert digest(addon) == digest(payload / addon.name), 'Installed add-on differs from payload'
            if game['api'] != 'vulkan':
                proxy = folder / game['expected_proxy']
                assert architecture(proxy) == game['architecture'], 'Wrong proxy architecture'
                if game['api'] == 'dx8':
                    assert architecture(folder / 'd3d9.dll') == 'x86', 'Missing DX8 translation target'
            else:
                assert (folder / '_DLSS5_Vulkan' / 'ReShade.json').is_file(), 'Missing Vulkan launch layer'
            config = json.loads((folder / 'Phoenix.json').read_text(encoding='utf-8-sig'))
            assert config['armed'] and config['input_provider'] == 'feeder_d3d12', 'Wrong input route'
            assert digest(Path(config['weight_source']['path'])) == config['weight_source']['sha256'], 'Wrong model'
            after = snapshot(folder)
            item['added_files'] = {name: entry for name, entry in after.items() if name not in original}
            item['modified_original_files'] = [name for name in original if original[name] != after.get(name)]
            assert not item['modified_original_files'], 'Installer modified original fixture files'
            item['passed'] = True
        except Exception as error:
            item['error'] = str(error)
        save()
        print(json.dumps({key: item[key] for key in ('id', 'passed', 'error') if key in item}), flush=True)
    report['passed'] = all(game['passed'] for game in report['games'])
    save()
    print(json.dumps({'passed': report['passed'], 'installed': sum(g['passed'] for g in report['games']),
                      'total': len(report['games']), 'report': str(output / 'installations.json')}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
