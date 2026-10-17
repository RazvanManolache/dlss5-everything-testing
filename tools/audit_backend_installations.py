"""Audit installed component identities against each tested installer plan."""
import argparse
from pathlib import Path
from run_backends import ROOT, digest, read, write


def audit(payload, background_only=False):
    output = ROOT / 'runs/latest-x64-backends'
    targets = read(ROOT/'state/background-rerun.json').get('targets',{}) if background_only else None
    rows = []
    for game in read(ROOT / 'matrix.json')['games']:
        if targets is not None and game['id'] not in targets:
            continue
        case = output / game['id']
        inventory = read(case / 'inventory.json')
        candidate = (inventory.get('Games') or [{}])[0]
        plan = ((inventory.get('Plans') or [{}])[0].get('Plan') or {})
        folder = ROOT / game['install_directory']
        manifest = read(folder / '_DLSS5_Compat_Backup/manifest.json')
        row = dict(id=game['id'], detected_api=candidate.get('Api'),
                   detection=candidate.get('Detection'), proxy=plan.get('Proxy'),
                   translation=plan.get('Translation'), installer_route=manifest.get('Route'),
                   installed_files=manifest.get('Added') or [], modes={})
        expected = [(folder / ('Phoenix.addon32' if game['architecture']=='x86' else 'Phoenix.addon64'),
                     Path(plan['Addon']) if plan.get('Addon') else payload / ('Phoenix.addon32' if game['architecture']=='x86' else 'Phoenix.addon64')),
                    (folder / 'PhoenixModel.dll', payload / 'nvngx_dlssnr.dll')]
        reshade = payload / ('ReShade32.dll' if game['architecture']=='x86' else 'ReShade64.dll')
        if plan.get('Proxy'):
            expected.append((folder / plan['Proxy'], reshade))
        else:
            layer_manifest = folder / '_DLSS5_Vulkan/ReShade.json'
            library = read(layer_manifest).get('layer', {}).get('library_path')
            if library:
                path = Path(library)
                expected.append((path if path.is_absolute() else layer_manifest.parent / path, reshade))
        for mode in ('nvidia', 'phoenix'):
            if targets is not None and mode not in targets[game['id']]:
                continue
            result_path = case / mode / 'result.json'
            result = read(result_path)
            if not result:
                continue
            proof = dict(tested=result.get('passed'), runtime_api=result.get('processing', {}).get('api'),
                         execution_mode=result.get('execution_mode') or result.get('diagnostics', {}).get('execution_mode'))
            if result.get('passed'):
                checks = {path.name: path.is_file() and digest(path)==digest(source) for path,source in expected}
                proof['component_hashes_match_payload'] = checks
                proof['verified'] = all(checks.values())
                result['installation_verification'] = dict(detected_api=row['detected_api'],
                    proxy=row['proxy'], translation=row['translation'], **proof)
                write(result_path, result)
            row['modes'][mode] = proof
        rows.append(row)
    report = dict(schema='installer-runtime-audit/1', fixtures=rows,
                  mismatches=[row['id'] for row in rows if any(m.get('verified') is False for m in row['modes'].values())])
    write(output / 'installation-audit.json', report)
    print('Installation audit mismatches:', report['mismatches'])
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--background-only', action='store_true')
    args = parser.parse_args()
    audit(args.payload.resolve(), args.background_only)
