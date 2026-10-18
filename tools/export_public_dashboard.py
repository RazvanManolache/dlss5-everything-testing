"""Publish an allowlisted static result index and lossless, pixel-deduplicated images.

Reads existing evidence only. Never launches fixtures, installs addons or downloads.
"""
import argparse
import csv
import datetime
import hashlib
import json
import re
import shutil
import struct
import tempfile
from pathlib import Path

from PIL import Image
import dashboard

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_FIELDS = ('id', 'api', 'architecture', 'expected_proxy', 'application_api',
    'render_transport', 'group', 'label', 'transport', 'sha256', 'software_renderer')
RUN_FIELDS = ('id', 'fixture_id', 'label', 'group', 'api', 'transport', 'architecture',
    'suite', 'mode', 'status', 'freshness', 'timestamp', 'fps', 'game_fps', 'game_samples',
    'minimum_fps', 'maximum_fps', 'seconds', 'frames', 'width', 'height', 'samples',
    'background', 'software', 'gpu', 'neural_fps', 'fps_scope', 'neural_fps_scope',
    'scene_mode', 'execution_mode', 'execution_variant', 'execution_label',
    'requested_execution_mode', 'first_ready_render_seconds', 'startup_in_measurement',
    'captured_api', 'benchmark_profile', 'addon_sha256', 'comparison_batch',
    'requested_seconds', 'warmup_seconds', 'vsync', 'measurement_complete',
    'benchmark_warnings', 'error', 'captures', 'executable_sha256', 'expected_sha256',
    'checks_passed', 'checks_total', 'reference')
CONTROL_FIELDS = ('frozen', 'animations_enabled', 'camera_motion_enabled', 'camera_mode',
    'camera_eye', 'yaw', 'pitch', 'orbit_distance', 'character_pose',
    'simulation_seconds', 'camera_seconds')
CAPTURE_FIELDS = ('id', 'run_id', 'name', 'requested_seconds', 'seconds', 'frame',
    'shared_frame', 'width', 'height')
ASSETS = ('index.html', 'app.js', 'performance.js', 'styles.css', 'favicon.svg')
PRIVATE_PATH = re.compile(r'(?i)(?:\b[a-z]:[\\/]|\\\\[^\\\s]+\\|/Users/|/home/)')


def select(value, fields):
    return {key: value[key] for key in fields if key in value}


def public_data(data):
    result = dict(schema=data['schema'], public_snapshot=True,
        generated_at=data['generated_at'], fixtures=[select(f, FIXTURE_FIELDS) for f in data['fixtures']],
        runs=[], captures=[], groups=data['groups'], build={}, warnings=[], notes=data['notes'])
    for original in data['runs']:
        row = select(original, RUN_FIELDS)
        if row.get('timestamp'):
            row['timestamp'] = datetime.datetime.fromisoformat(row['timestamp']).astimezone(datetime.timezone.utc).isoformat()
        row['controls'] = select(original.get('controls') or {}, CONTROL_FIELDS)
        # Keep route provenance without private IPC, model directories or PIDs.
        row['processing'] = select(original.get('processing') or {}, ('execution_mode', 'api', 'fallback_reason'))
        result['runs'].append(row)
    result['captures'] = [select(c, CAPTURE_FIELDS) for c in data['captures']]
    assert_private_free(result)
    return result


def assert_private_free(value):
    text = json.dumps(value, ensure_ascii=True)
    if PRIVATE_PATH.search(text):
        raise ValueError('An absolute host path reached the public metadata allowlist')


def pixel_identity(image):
    rgba = image.convert('RGBA')
    digest = hashlib.sha256(struct.pack('<II', *rgba.size) + rgba.tobytes()).hexdigest()
    return digest, rgba


def capture_source(capture):
    relative = Path(capture['id'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Invalid capture identity')
    path = ROOT / relative
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Capture escaped the project')
    if any(p.is_symlink() or p.is_junction() for p in [path, *path.parents] if p != ROOT.parent):
        raise ValueError('Linked capture input')
    return path


def export(output, data=None, replace=False):
    output = output.resolve()
    if output == ROOT or not output.is_relative_to(ROOT / 'docs'):
        raise ValueError('Public snapshots must be below this project docs directory')
    if any(p.is_symlink() or p.is_junction() for p in [output, *output.parents]):
        raise ValueError('Linked publication directory')
    old = None
    if output.exists():
        if not replace:
            raise ValueError('Snapshot exists; use --replace to replace its owned files')
        old = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        if old.get('schema') != 'public-benchmark-snapshot/1':
            raise ValueError('Not an owned public snapshot')
        expected = set(old['files']) | {'manifest.json'}
        actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
        if actual != expected or any(p.is_symlink() or p.is_junction() for p in output.rglob('*')):
            raise ValueError('Snapshot contains unexpected files or links')
    data = dashboard.make_data() if data is None else data
    result = public_data(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='public-dashboard-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'snapshot'
        stage.mkdir()
        (stage / 'images').mkdir()
        for name in ASSETS:
            shutil.copy2(ROOT / 'dashboard' / name, stage / name)
        unique = {}
        source_bytes = 0
        for original, capture in zip(data['captures'], result['captures']):
            source = capture_source(original)
            source_bytes += source.stat().st_size
            with Image.open(source) as image:
                digest, rgba = pixel_identity(image)
            name = 'images/' + digest + '.webp'
            if digest not in unique:
                # Lossless WebP strips file metadata without changing displayed pixels.
                if old and name in old['files'] and hashlib.sha256((output/name).read_bytes()).hexdigest() == old['files'][name]:
                    shutil.copy2(output/name, stage/name)
                else:
                    rgba.save(stage / name, format='WEBP', lossless=True, quality=100, method=4)
                with Image.open(stage / name) as encoded:
                    if pixel_identity(encoded)[0] != digest:
                        raise ValueError('Lossless image round-trip failed')
                unique[digest] = name
            capture.update(src=name, bytes=(stage / name).stat().st_size, pixel_sha256=digest)
        (stage / 'data.js').write_text('window.BENCH_DATA = ' +
            json.dumps(result, ensure_ascii=True).replace('<', '\\u003c') + ';\n', encoding='utf-8')
        fields = ('fixture_id', 'architecture', 'mode', 'execution_variant', 'execution_mode',
            'status', 'fps', 'game_fps', 'neural_fps', 'fps_scope', 'width', 'height',
            'warmup_seconds', 'requested_seconds', 'vsync', 'startup_in_measurement', 'error')
        with (stage / 'results.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(result['runs'])
        summary = ROOT / 'runs/latest-x64-backends/execution-comparison.json'
        if summary.is_file():
            source = json.loads(summary.read_text(encoding='utf-8'))
            public_summary = select(source, ('schema', 'hardware', 'counts', 'totals',
                'matched_x86_rankings', 'previous_native_x64_comparison', 'failures',
                'timing_note', 'regression_note', 'route_output_comparison'))
            public_summary['dos_results'] = [r for r in result['runs'] if r['fixture_id'] == 'dos-vga']
            assert_private_free(public_summary)
            (stage / 'summary.json').write_text(json.dumps(public_summary, indent=2) + '\n', encoding='utf-8')
        files = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(stage.rglob('*')) if p.is_file()}
        manifest = dict(schema='public-benchmark-snapshot/1', records=len(result['runs']),
            capture_records=len(result['captures']), unique_images=len(unique),
            source_image_bytes=source_bytes, published_image_bytes=sum((stage/n).stat().st_size for n in unique.values()),
            pixel_deduplication='SHA-256 of dimensions plus decoded RGBA; run identities are retained',
            privacy='Allowlisted metadata only; no logs, local paths, PIDs, tokens, model files or binaries', files=files)
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        if old is not None:
            for name in expected:
                member = Path(name)
                if member.is_absolute() or '..' in member.parts:
                    raise ValueError('Invalid prior snapshot manifest member')
                (output / member).unlink()
            for directory in sorted((p for p in output.rglob('*') if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
                directory.rmdir()
            output.rmdir()
        stage.replace(output)
    print(json.dumps({k:v for k,v in manifest.items() if k != 'files'}))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/dashboard')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    export(args.output, replace=args.replace)
