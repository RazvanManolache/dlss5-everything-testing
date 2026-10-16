"""Publish identical clean and ReShade suites with shared scene assets."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import stat
import datetime
import os
from asset_paths import find_assets,point_assets

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_config(path):
    config = json.loads(path.read_text())
    for key in ('clean_suite', 'reshade_suite', 'shared_assets', 'validation', 'matched_reference'):
        if key not in config:continue
        value = Path(config[key])
        config[key] = value.resolve() if value.is_absolute() else (ROOT / value).resolve()
    clean, working = config['clean_suite'], config['reshade_suite']
    if (clean/'games').is_relative_to(working/'games') or (working/'games').is_relative_to(clean/'games'):
        raise RuntimeError('The clean and ReShade suite directories must be separate')
    return config


def members(baseline, game):
    result = {}
    for name, pin in baseline['files'].items():
        prefix = 'common/' if name.startswith('common/') else f"games/{game['id']}/"
        if name.startswith(prefix):
            rel = Path(name[len(prefix):])
            if rel.is_absolute() or '..' in rel.parts:
                raise RuntimeError('Invalid baseline member: ' + name)
            result[rel.as_posix()] = pin
    return result


def ordinary(path, parent):
    if not path.resolve().is_relative_to(parent.resolve()):
        raise RuntimeError('Destination escapes suite: ' + str(path))
    current = path
    while current != parent:
        if current.exists() and current.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError('Published files must be independent ordinary copies: ' + str(current))
        current = current.parent


def matches(path, pin):
    return path.is_file() and path.stat().st_size == pin['bytes'] and digest(path) == pin['sha256']


def prepare_assets(folder, shared, pins):
    assets = folder/'assets'
    if assets.exists():
        if assets.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError('Remove the asset link before publication: ' + str(assets))
        expected = {name[len('assets/'):]: pin for name, pin in pins.items() if name.startswith('assets/')}
        actual = {p.relative_to(assets).as_posix() for p in assets.rglob('*') if p.is_file()}
        if actual != set(expected) or not all(matches(assets/name, pin) for name, pin in expected.items()):
            raise RuntimeError('Assets differ; refusing to remove independent copy: ' + str(assets))
        if assets.resolve() != folder.resolve()/'assets':raise RuntimeError('Unsafe asset directory')
        if any(p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT for p in assets.rglob('*')):
            raise RuntimeError('Unexpected link within duplicate assets: '+str(assets))
        shutil.rmtree(assets)
    folder.mkdir(parents=True, exist_ok=True)


def write_json(path, value):
    temporary = path.with_name(path.name + '.publishing')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def publish(source, validation_path, config_path, output, build_only=False):
    source = source.resolve()
    config = load_config(config_path)
    baseline = json.loads((ROOT / 'baseline.json').read_text())
    matrix = json.loads((source / 'matrix.json').read_text())
    validation = json.loads(validation_path.read_text())
    if matrix != baseline['matrix'] or (not build_only and not validation['passed']):
        raise RuntimeError('Publication requires a sealed build and passing validation')
    if not build_only:
        results = {(r['id'], r['mode']): r for r in validation['results']}
        for game in matrix['games']:
            for mode in ('matched', 'showcase'):
                r = results.get((game['id'], mode), {})
                if not r.get('passed') or r.get('sha256') != game['sha256']:
                    raise RuntimeError('Missing current validation: ' + game['id'] + ' ' + mode)
    # Verify common source assets only once, while retaining per-copy verification.
    verified_sources = set()
    for game in matrix['games']:
        for rel, pin in members(baseline, game).items():
            folder=source/game['install_directory']
            src = (find_assets(folder)/rel[len('assets/'):] if rel.startswith('assets/') else folder/rel).resolve()
            identity = (src, pin['sha256'])
            if identity not in verified_sources:
                if not matches(src, pin):
                    raise RuntimeError('Source differs from sealed build: ' + str(src))
                verified_sources.add(identity)

    plans = []
    shared = config['shared_assets']
    for target in (config['clean_suite']/'games', config['reshade_suite']/'games'):
        if shared.is_relative_to(target) or target.is_relative_to(shared):
            raise RuntimeError('Shared assets must be outside both game trees')
    shared_pins = {name[len('common/assets/'):]: pin for name, pin in baseline['files'].items() if name.startswith('common/assets/')}
    shared_probe = shared
    while not shared_probe.exists(): shared_probe = shared_probe.parent
    shared_required = sum(max(0, pin['bytes'] - ((shared/name).stat().st_size if (shared/name).exists() else 0)) for name, pin in shared_pins.items())
    if shared_required + 1024**3 > shutil.disk_usage(shared_probe).free:
        raise RuntimeError('Not enough space for the single shared asset snapshot')
    for kind in ('clean', 'reshade'):
        target = config[kind + '_suite']
        if target == source or target.is_relative_to(source) or source.is_relative_to(target / 'games'):
            raise RuntimeError('Publication destination overlaps staging')
        old_file = target / 'fixture-baseline.json'
        old = json.loads(old_file.read_text()) if old_file.exists() else baseline
        old_games = {g['id']: g for g in old['matrix']['games']}
        plan = {'kind': kind, 'target': target, 'games': [], 'required': 0, 'preserved': {}}
        for game in matrix['games']:
            folder = target / game['install_directory']
            ordinary(folder, target)
            pins = members(baseline, game)
            previous = members(old, old_games[game['id']]) if game['id'] in old_games else {}
            seed = set(game.get('runtime_files', {}))
            customized = kind == 'reshade' and folder.exists() and any(
                not matches(folder / rel, previous.get(rel, pins[rel])) for rel in seed)
            preserve = set(seed) if customized else set()
            if folder.exists():
                for path in folder.rglob('*'):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(folder).as_posix()
                    if rel.startswith('assets/'):
                        continue
                    ordinary(path, target)
                    if rel not in pins and not rel.startswith('run/'):
                        if kind == 'clean':
                            raise RuntimeError('Unexpected file in clean set; move it before publishing: ' + str(path))
                    if rel not in pins or rel in preserve:
                        plan['preserved'][path] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
                if kind == 'clean':
                    for rel in seed:
                        path = folder / rel
                        if path.exists() and not matches(path, previous.get(rel, pins[rel])):
                            raise RuntimeError('Modified runtime in clean set: ' + str(path))
            for rel, pin in pins.items():
                if rel.startswith('assets/'):
                    continue
                dest = folder / rel
                ordinary(dest, target)
                if rel not in preserve:
                    plan['required'] += max(0, pin['bytes'] - (dest.stat().st_size if dest.exists() else 0))
            plan['games'].append((game, pins, preserve))
        probe = target
        while not probe.exists():
            probe = probe.parent
        plan['volume'] = probe.anchor.lower()
        plan['free'] = shutil.disk_usage(probe).free
        plans.append(plan)
    for plan in plans:
        needed = sum(p['required'] for p in plans if p['volume'] == plan['volume'])
        if needed + 1024**3 > plan['free']:
            raise RuntimeError(f"{plan['target']}: needs {needed/1e9:.1f} GB; {plan['free']/1e9:.1f} GB free")

    report = {'passed': False, 'runtime_tests_run': not build_only, 'validation': str(validation_path.resolve()), 'sets': []}
    shared.mkdir(parents=True, exist_ok=True)
    source_assets = find_assets(source/matrix['games'][0]['install_directory'])
    for rel, pin in shared_pins.items():
        dest = shared/rel
        ordinary(dest, shared)
        if matches(dest, pin): continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_name(dest.name + '.publishing')
        shutil.copy2(source_assets/rel, temporary)
        if not matches(temporary, pin): raise RuntimeError('Shared asset copy mismatch: '+rel)
        temporary.replace(dest)
    report['shared_assets'] = str(shared)
    report['shared_asset_bytes'] = sum(pin['bytes'] for pin in shared_pins.values())
    for plan in plans:
        target = plan['target']
        target.mkdir(parents=True, exist_ok=True)
        point_assets(target,shared)
        suite_report = {'kind': plan['kind'], 'suite': str(target), 'games': [],
                        'preserved_files': [str(p.relative_to(target)) for p in plan['preserved']]}
        for game, pins, preserve in plan['games']:
            folder = target / game['install_directory']
            prepare_assets(folder, shared, pins)
            for rel, pin in pins.items():
                if rel.startswith('assets/'):
                    continue
                if rel in preserve:
                    continue
                dest = folder / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if matches(dest, pin):
                    continue
                temporary = dest.with_name(dest.name + '.publishing')
                shutil.copy2(source / game['install_directory'] / rel, temporary)
                if not matches(temporary, pin):
                    raise RuntimeError('Copied file mismatch: ' + str(dest))
                temporary.replace(dest)
            suite_report['games'].append({'id': game['id'], 'sha256': digest(target / game['executable']),
                                          'preserved_runtime_seed': sorted(preserve)})
            print(plan['kind'], game['id'], 'verified', flush=True)
        for path, pin in plan['preserved'].items():
            if not matches(path, pin):
                raise RuntimeError('Installed file changed during publication: ' + str(path))
        write_json(target / 'matrix.json', matrix)
        write_json(target / 'fixture-baseline.json', baseline)
        write_json(target / 'suite-role.json', {'role': plan['kind'], 'source': os.path.relpath(ROOT/'pristine.zip',target),
                   'updated_at': datetime.datetime.now().astimezone().isoformat(),
                   'install_reshade_here': plan['kind'] == 'reshade'})
        report['sets'].append(suite_report)
    report['passed'] = True
    write_json(output, report)
    config['validation'] = validation_path.resolve()
    config['runtime_validation_current'] = not build_only
    write_json(config_path, {k: os.path.relpath(v,ROOT) if isinstance(v, Path) else v for k, v in config.items()})
    print('PASS: published', len(matrix['games']), 'games to both sets with shared scene assets', flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--build-only',action='store_true',help='Publish checked build files without game runtime tests')
    p.add_argument('--validation', type=Path, required=True)
    p.add_argument('--config', type=Path, default=ROOT / 'build-sets.json')
    p.add_argument('--output', type=Path, default=ROOT / 'state/publication.json')
    a = p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    publish(a.source, a.validation, a.config, a.output, build_only=a.build_only)


if __name__ == '__main__':
    main()
