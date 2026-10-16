"""Installer-driven x64 sweep: 5s warmup, 20s measured, one final capture.

Native runs use clean/games without modifying that baseline. Enhanced
captures come from Phoenix's presented-output screenshot API, not fixture readback.
Only children and helper PIDs observed in this test's authenticated mailbox close.
"""
import argparse
import csv
import configparser
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import time
import uuid

import numpy as np
from PIL import Image
import psutil

from storage_policy import latest_output

ROOT = Path(__file__).resolve().parents[1]
WARMUP_SECONDS, MEASURE_SECONDS = 5, 20
WIDTH, HEIGHT = 1920, 1080
PROFILE = 'uncapped-1080p-warmup5-measure20-single-capture-v1'


def read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def emit(value):
    print(json.dumps(value), flush=True)


def ini_backend(folder, backend):
    for name in ('ReShade.ini', 'ReShadeVR.ini'):
        path = folder / name
        ini = configparser.ConfigParser(interpolation=None, strict=False)
        ini.optionxform = str
        ini.read(path, encoding='utf-8-sig')
        if not ini.has_section('Phoenix'):
            ini.add_section('Phoenix')
        ini['Phoenix'].update(Backend=str(backend), Comparison='0', ComparisonLabels='0',
                              ComparisonLines='0', NeuralUplift='1', OverrideStrengths='0',
                              Tone='1', Structure='1', Skin='-1', AutoMask='0',
                              NativeOptions='0', Intensity='1', ResolutionMode='0',
                              Upscaler='0', RefinementPasses='1')
        with path.open('w', encoding='utf-8') as stream:
            ini.write(stream)


class Mailbox:
    def __init__(self, folder, process):
        self.folder, self.process = folder, process
        self.mail = None
        self.endpoint = {}
        self.helpers = {}
        self.kernel = ctypes.WinDLL('kernel32')
        self.kernel.GetTickCount64.restype = ctypes.c_ulonglong

    def discover(self):
        for path in (self.folder / 'PhoenixOutput').glob('bridge*/endpoint.json'):
            endpoint = read(path)
            if endpoint.get('pid') == self.process.pid:
                self.endpoint, self.mail = endpoint, path.parent
                return True
        return False

    def command(self, op='status', timeout=1.5):
        if not self.mail and not self.discover():
            return {}
        token = uuid.uuid4().hex
        request = dict(schema='phoenix-control/1', session=self.endpoint['session'],
                       pid=self.process.pid, id=token, op=op,
                       expires_tick_ms=self.kernel.GetTickCount64() + 2500)
        temp = self.mail / 'benchmark-request.tmp'
        temp.write_text(json.dumps(request), encoding='utf-8')
        os.replace(temp, self.mail / 'request.json')
        until = time.monotonic() + timeout
        while self.process.poll() is None and time.monotonic() < until:
            value = read(self.mail / 'response.json')
            if value.get('id') == token:
                snapshot = value.get('snapshot', {})
                pid = snapshot.get('helper_pid')
                if pid and pid not in self.helpers:
                    try:
                        proc = psutil.Process(pid)
                        if proc.name().lower() == 'phoenix_graphics_host.exe':
                            self.helpers[pid] = proc.create_time()
                    except psutil.Error:
                        pass
                return value
            time.sleep(.025)
        return {}

    def stop_helpers(self):
        for pid, created in self.helpers.items():
            try:
                proc = psutil.Process(pid)
                if proc.create_time() == created and proc.name().lower() == 'phoenix_graphics_host.exe':
                    proc.wait(3)
            except psutil.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(3)
                except psutil.TimeoutExpired:
                    proc.kill()
            except psutil.Error:
                pass


def compact(snapshot):
    info = snapshot.get('in_process') or snapshot.get('helper') or {}
    return {key: snapshot.get(key) for key in (
        'enabled', 'phase', 'status', 'execution_mode', 'fallback_reason', 'helper_pid',
        'delivered', 'presented', 'selection_revision', 'presented_revision',
        'applied_settings')} | {'nvidia': info.get('nvidia'), 'error': info.get('error'),
                              'gpu_timing': info.get('gpu_timing')}


def ready(snapshot, backend):
    info = snapshot.get('in_process') or snapshot.get('helper') or {}
    nv = info.get('nvidia') or snapshot.get('nvidia') or {}
    return (snapshot.get('enabled') is True and snapshot.get('phase') != 5 and snapshot.get('delivered', 0) > 0
            and snapshot.get('presented', 0) > 0
            and snapshot.get('presented_revision') == snapshot.get('selection_revision')
            and snapshot.get('applied_settings', {}).get('Backend') == backend
            and (backend != 1 or nv.get('ready') and nv.get('evaluates', 0) > 0))


def close_fixture(process):
    if process.poll() is not None:
        return
    user = ctypes.WinDLL('user32')
    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def close(hwnd, _):
        pid = ctypes.c_ulong()
        user.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        if pid.value == process.pid:
            user.PostMessageW(ctypes.c_void_p(hwnd), 0x10, 0, 0)
        return True
    user.EnumWindows(callback(close), 0)
    try:
        process.wait(8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(5)


def fixture_command(exe, backend, output):
    command = [str(exe), '--background', '--windowed', '--width', str(WIDTH), '--height', str(HEIGHT),
               '--mode', 'showcase', '--fixed-time', '--seconds', '0',
               '--warmup-seconds', str(WARMUP_SECONDS), '--measure-seconds', str(MEASURE_SECONDS),
               '--output', str(output)]
    return command + (['--capture-at', str(WARMUP_SECONDS + MEASURE_SECONDS), '--capture-after-measure']
                      if backend == 'native' else ['--no-capture'])


def _run_case(game, backend, folder, output, seconds, environment, reference_folder):
    number = {'native': 0, 'nvidia': 1, 'phoenix': 3}[backend]
    exe = folder / Path(game['executable']).name
    result = dict(id=game['id'], backend=backend, executable=str(exe),
                  executable_sha256=digest(exe), requested_seconds=seconds,
                  passed=None, profile=PROFILE, warmup_seconds=WARMUP_SECONDS,
                  width=WIDTH, height=HEIGHT, vsync=False,
                  timing_scope='20 measured seconds after 5s warmup; capture excluded',
                  source_suite='clean' if backend == 'native' else 'working',
                  capture_source='fixture_readback' if number == 0 else 'phoenix_presented_output')
    output.mkdir(parents=True, exist_ok=True)
    # A retry replaces this runner's own current case, not named historic output.
    for path in output.iterdir():
        if path.is_file() and (path.suffix.lower() in ('.png', '.ppm') or path.name in
                              ('status.json', 'fps.json', 'fps.csv', 'captures.json', 'processing.json')):
            path.unlink()
    write(output / 'result.json', result)
    captures, snapshots, pending = [], [], None
    times = (WARMUP_SECONDS + seconds,)
    command = fixture_command(exe, backend, output)
    environment = environment.copy()
    environment.update(DXVK_LOG_PATH=str(output), DXVK_STATE_CACHE_PATH=str(output),
                       VKD3D_SHADER_CACHE_PATH=str(output))
    process = None
    mail = None
    try:
        started = time.monotonic()
        with (output / 'process.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=folder, env=environment,
                                       stdout=log, stderr=subprocess.STDOUT)
            mail = Mailbox(folder, process)
            next_poll, next_capture = 0, 0
            while process.poll() is None and time.monotonic() - started < seconds + 45:
                if (ROOT / 'runs/latest-x64-backends/STOP').exists():
                    result['error'] = 'Benchmark stopped by request'
                    break
                runtime = read(output / 'status.json')
                if runtime.get('pid') != process.pid:
                    runtime = {}
                benchmark = runtime.get('benchmark', {})
                tick = benchmark.get('render_start_tick_ms', 0)
                elapsed = (mail.kernel.GetTickCount64() - tick) / 1000 if tick else 0
                measurement = read(output / 'measurement.json')
                if not number and measurement.get('complete') and len(read(output / 'captures.json').get('captures') or []) == 1:
                    break
                now = time.monotonic()
                if number and now >= next_poll:
                    response = mail.command()
                    snapshot = response.get('snapshot', {})
                    if snapshot:
                        snapshot_seconds = (snapshot.get('tick_ms', mail.kernel.GetTickCount64()) - tick) / 1000 if tick else 0
                        snapshots.append(dict(seconds=snapshot_seconds, **compact(snapshot)))
                        if snapshot.get('phase') == 5:
                            result['error'] = snapshot.get('status') or 'Phoenix processing failed'
                            break
                        if ready(snapshot, number):
                            result.setdefault('first_ready_render_seconds', elapsed)
                        if pending:
                            screenshot = snapshot.get('screenshot') or {}
                            if screenshot.get('path') == str(pending[0]) and not screenshot.get('pending') and pending[0].is_file():
                                destination = output / f'presented-{len(captures)+1:02}.png'
                                with Image.open(pending[0]) as image:
                                    image.convert('RGB').save(destination)
                                captures.append(dict(png=destination.name, requested_seconds=pending[1],
                                                     elapsed_seconds=elapsed, source='phoenix_presented_output',
                                                     processing_ready=ready(snapshot, number)))
                                pending[0].unlink()
                                pending = None
                        if not pending and next_capture < len(times) and measurement.get('complete') and ready(snapshot, number):
                            shot = mail.command('screenshot')
                            if shot.get('screenshot_path'):
                                path = Path(shot['screenshot_path'])
                                if not path.resolve().is_relative_to((folder / 'PhoenixOutput').resolve()):
                                    raise RuntimeError('Screenshot API returned a path outside its output root')
                                pending = (path, times[next_capture])
                            next_capture += 1
                        if measurement.get('complete') and len(captures) == 1:
                            break
                    if elapsed >= 12 and not mail.mail:
                        result['error'] = 'ReShade/Phoenix control endpoint did not load'
                        break
                    if elapsed >= 20 and 'first_ready_render_seconds' not in result:
                        result['error'] = 'No enhanced presentation within 20 render seconds'
                        break
                    if now - started >= 25 and not mail.mail:
                        result['error'] = 'ReShade/Phoenix did not initialize within 25 startup seconds'
                        break
                    next_poll = now + .5
                time.sleep(.05)
            measurement = read(output / 'measurement.json')
            if process.poll() is None and not measurement.get('complete'):
                result['error'] = result.get('error') or 'Fixture exceeded bounded startup/render deadline'
            close_fixture(process)
        result['exit_code'] = process.returncode
        runtime = read(output / 'status.json')
        fps = read(output / 'fps.json')
        measurement = fps.get('measurement') or {}
        if runtime.get('renderer_details', {}).get('uncapped_available') is False:
            result['error'] = 'This renderer could not disable refresh-synchronized presentation'
        if (runtime.get('width'), runtime.get('height')) != (WIDTH, HEIGHT):
            result['error'] = 'Fixture did not render at the requested 1920x1080 resolution'
        if number:
            # Do not let the dashboard substitute the fixture's unenhanced readback.
            write(output / 'captures.json', {'captures': captures})
            for path in output.glob('capture*.png'):
                path.rename(path.with_name('input-' + path.name))
            write(output / 'processing.json', {'snapshots': snapshots})
            live = [s for s in snapshots if ready(s, number) and
                    measurement.get('start_render_seconds', 0) <= s['seconds'] <= measurement.get('end_render_seconds', 0)]
            result['processing'] = snapshots[-1] if snapshots else {}
            if len(live) > 1:
                delta = live[-1]['seconds'] - live[0]['seconds']
                if delta > 0:
                    result['neural_fps'] = (live[-1]['delivered'] - live[0]['delivered']) / delta
            if not live:
                result['error'] = result.get('error') or 'No verified enhanced presentation in the measured window'
            if len(captures) != len(times):
                result['error'] = result.get('error') or 'Presented screenshot capture incomplete'
        else:
            captures = read(output / 'captures.json').get('captures', [])
            modules = runtime.get('render_loaded_modules') or runtime.get('loaded_modules') or []
            if any(Path(path).suffix.lower() == '.addon64' or Path(path).name.lower().startswith('reshade')
                   and Path(path).suffix.lower() == '.dll' for path in modules):
                result['error'] = 'Clean baseline unexpectedly loaded ReShade or an addon'
        result['passed'] = (process.returncode == 0 and runtime.get('state') == 'complete'
                            and measurement.get('complete') is True and fps.get('elapsed_seconds', 0) >= seconds
                            and len(captures) == len(times) and not result.get('error')
                            and all(c.get('processing_ready', True) for c in captures))
        if not result['passed'] and not result.get('error'):
            result['error'] = runtime.get('error') or 'Incomplete fixture duration or screenshots'
        result['average_fps'] = fps.get('average_fps')
        result['elapsed_seconds'] = fps.get('elapsed_seconds')
        result['measurement'] = measurement
        if measurement.get('complete'):
            # Publish measured samples, not the fixture's whole-lifetime CSV.
            with (output / 'fps.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=['elapsed_seconds', 'frames', 'interval_seconds', 'fps', 'average_fps'])
                writer.writeheader()
                writer.writerows({key:sample.get(key) for key in writer.fieldnames} for sample in fps.get('samples') or [])
        if number:
            native = reference_folder
            reference = read(native / 'captures.json').get('captures', [])
            differences = []
            for capture, original in zip(captures, reference):
                a, b = output / capture['png'], native / original['png']
                with Image.open(a) as ai, Image.open(b) as bi:
                    aa, bb = np.asarray(ai.convert('RGB')).astype(float), np.asarray(bi.convert('RGB')).astype(float)
                if aa.shape == bb.shape:
                    # Ignore startup badges and overlay text in edge regions.
                    h,w = aa.shape[:2]
                    delta = np.abs(aa[h//4:3*h//4,w//4:3*w//4]-bb[h//4:3*h//4,w//4:3*w//4])
                    differences.append(dict(central_mae=float(delta.mean()),
                                            changed_fraction_gt2=float((delta.max(axis=2)>2).mean())))
            result['pixel_comparison'] = differences
            if len(differences) != len(times):
                result['passed'] = False
                result['error'] = result.get('error') or 'Matching clean baseline images are unavailable'
            elif not all(d['central_mae'] > .25 and d['changed_fraction_gt2'] > .01 for d in differences):
                result['passed'] = False
                result['error'] = 'Enhanced output not measurably different from original in central image'
    except Exception as error:
        result['passed'] = False
        result['error'] = str(error)
    finally:
        if process:
            close_fixture(process)
        if mail:
            mail.stop_helpers()
        if pending and pending[0].is_file():
            pending[0].unlink()
        log = folder / 'ReShade.log'
        if number and log.is_file():
            (output / 'ReShade.log').write_bytes(log.read_bytes())
        write(output / 'result.json', result)
    return result


def failure_record(result):
    """Failures carry identity and diagnostics, never images or timing samples."""
    fields = ('id', 'backend', 'executable', 'executable_sha256', 'requested_seconds',
              'source_suite', 'capture_source', 'exit_code', 'error', 'profile',
              'width', 'height', 'warmup_seconds', 'vsync')
    failure = {key:result[key] for key in fields if key in result}
    failure.update(passed=False, state='error')
    processing = result.get('processing') or {}
    failure['diagnostics'] = {key:processing[key] for key in
                              ('phase', 'status', 'execution_mode', 'fallback_reason', 'error')
                              if key in processing}
    return failure


def run_case(game, backend, folder, output, seconds, environment):
    output.mkdir(parents=True, exist_ok=True)
    if not output.resolve().is_relative_to(ROOT / 'runs/latest-x64-backends'):
        raise RuntimeError('Benchmark output escaped its owned current run')
    for path in output.iterdir():
        if path.is_symlink() or path.is_junction() or path.is_dir():
            raise RuntimeError('Unexpected directory or link in benchmark case')
        path.unlink()
    write(output / 'result.json', dict(id=game['id'], backend=backend, passed=None, state='running',
                                       capture_source='pending', requested_seconds=seconds,
                                       profile=PROFILE, width=WIDTH, height=HEIGHT,
                                       warmup_seconds=WARMUP_SECONDS, vsync=False))
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='backend-run-', dir=ROOT / 'build') as temporary:
        staged = Path(temporary)
        result = _run_case(game, backend, folder, staged, seconds, environment, output.parent / 'native')
        if result.get('passed'):
            records = read(staged / 'captures.json').get('captures') or []
            for record in records:
                original = staged / record['png']
                name = f"{game['id']}-{backend}-1920x1080.png"
                shutil.copyfile(original, output / name)
                record.pop('ppm', None)
                record.update(png=name, backend=backend, fixture_id=game['id'],
                              executable_sha256=result['executable_sha256'], source_suite=result['source_suite'],
                              profile=PROFILE, after_measurement=True)
            write(output / 'captures.json', dict(captures=records))
            for name in ('fps.json', 'fps.csv', 'status.json', 'processing.json'):
                path = staged / name
                if path.is_file():
                    shutil.copyfile(path, output / name)
        else:
            result = failure_record(result)
        write(output / 'result.json', result)
    emit({key: result[key] for key in ('id', 'backend', 'passed', 'average_fps', 'neural_fps', 'error') if key in result})
    return result


def current_pass(path, game):
    result = read(path)
    return (result.get('passed') is True and result.get('profile') == PROFILE
            and result.get('executable_sha256') == game['sha256'])


def clear_history():
    """Clear generated result history only, never baseline programs or assets."""
    roots = [ROOT / 'runs']
    for base in (ROOT / 'games', ROOT / 'clean/games'):
        roots.extend(path / 'run' for path in base.iterdir() if path.is_dir())
    names = {'fps.json', 'fps.csv', 'status.json', 'result.json', 'result.jsn',
             'captures.json', 'verification.json', 'processing.json', 'summary.json', 'summary.md'}
    count = 0
    for root in roots:
        if not root.exists():
            continue
        if root.is_symlink() or root.is_junction() or not root.resolve().is_relative_to(ROOT):
            raise RuntimeError('Refusing history cleanup through linked directory')
        for directory, folders, files in os.walk(root, followlinks=False):
            for name in folders:
                path = Path(directory) / name
                if path.is_symlink() or path.is_junction():
                    raise RuntimeError('Refusing history cleanup through linked directory')
            for name in files:
                path = Path(directory) / name
                if path.is_symlink() or path.is_junction():
                    raise RuntimeError('Refusing history cleanup through linked file')
                if path.suffix.lower() in ('.png', '.bmp', '.jpg', '.jpeg', '.webp', '.ppm') or name.lower() in names:
                    path.unlink()
                    count += 1
    # Screenshots requested from the addon live here until copied into a run.
    for game in (ROOT / 'games').iterdir():
        folder = game / 'PhoenixOutput'
        if not folder.is_dir() or folder.is_symlink() or folder.is_junction():
            continue
        for path in folder.glob('*.png'):
            if path.is_symlink() or path.is_junction():
                raise RuntimeError('Refusing screenshot cleanup through a link')
            path.unlink()
            count += 1
    emit({'cleared_generated_history_files': count})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--only', nargs='+')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--clear-history', action='store_true', help='Explicitly clear previous generated image/result history')
    parser.add_argument('--seconds', type=float, default=MEASURE_SECONDS)
    args = parser.parse_args()
    if args.seconds != MEASURE_SECONDS:
        parser.error('Comparable backend sweep requires exactly 20 measured seconds after 5s warmup')
    if args.clear_history and args.resume:
        parser.error('--clear-history cannot be combined with --resume')
    if args.clear_history:
        clear_history()
    output = ROOT / 'runs/latest-x64-backends'
    if not args.resume:
        output = latest_output(None, 'latest-x64-backends')
    output.mkdir(parents=True, exist_ok=True)
    if args.resume and (output / 'STOP').is_file():
        (output / 'STOP').unlink()
    if args.clear_history:
        from dashboard import export_snapshot
        export_snapshot()
    games = [g for g in read(ROOT / 'matrix.json')['games'] if g['architecture'] == 'x64'
             and (not args.only or g['id'] in args.only)]
    # This is test order only; detection and installation always use the real CLI.
    games.sort(key=lambda g: (g['id'] != 'dx12-x64', g['id']))
    for game in games:
        if (output / 'STOP').exists():
            break
        exe, folder = ROOT / game['executable'], ROOT / game['install_directory']
        if game.get('fixture_version', 0) < 7:
            raise RuntimeError('Rebuild this x64 fixture for uncapped measurement first: ' + game['id'])
        if not folder.resolve().is_relative_to(ROOT / 'games') or exe.resolve().parent != folder.resolve():
            raise RuntimeError('Fixture is outside the working games set')
        if digest(exe) != game['sha256']:
            raise RuntimeError('Fixture executable hash differs from matrix: ' + game['id'])
        clean = ROOT / 'clean' / game['executable']
        if not clean.resolve().is_relative_to(ROOT / 'clean/games') or digest(clean) != game['sha256']:
            raise RuntimeError('Clean/working fixture builds differ: ' + game['id'])
        if any(clean.parent.glob('*.addon64')) or (clean.parent / 'Phoenix.json').exists():
            raise RuntimeError('Clean fixture contains Phoenix components: ' + game['id'])
        case = output / game['id']
        case.mkdir(exist_ok=True)
        def cli(arguments, name):
            run = subprocess.run([str(args.installer.resolve()), *map(str, arguments)],
                                 cwd=args.installer.resolve().parent, capture_output=True, text=True, timeout=180)
            (case / (name + '.log')).write_text(run.stdout + '\n' + run.stderr, encoding='utf-8')
            return run
        inventory = case / 'inventory.json'
        inspection = cli(['--inspect', exe, '--output', inventory, '--payload', args.payload.resolve()], 'inspect')
        if inspection.returncode:
            raise RuntimeError('Installer inspection failed: ' + inspection.stderr)
        inv = read(inventory)
        plan = (inv.get('Plans') or [{}])[0]
        candidate = (inv.get('Games') or [{}])[0]
        root = Path(candidate.get('Root', folder))
        if not root.resolve().is_relative_to(folder.resolve()):
            raise RuntimeError('Installer root extends outside selected fixture: ' + str(root))
        manifest = root / '_DLSS5_Compat_Backup/manifest.json'
        native_result = case / 'native/result.json'
        if not (args.resume and current_pass(native_result, game)):
            run_case(game, 'native', clean.parent, case / 'native', args.seconds, os.environ.copy())
        if all(args.resume and current_pass(case / mode / 'result.json', game) for mode in ('nvidia', 'phoenix')):
            continue
        installed = cli(['--install', exe, '--offline', '--payload', args.payload.resolve()], 'install')
        environment = os.environ.copy()
        if installed.returncode == 0:
            # Layer selection comes from the installer's transactional manifest.
            data = read(manifest)
            environment.update(data.get('VulkanLaunchEnvironment') or data.get('vulkanLaunchEnvironment') or {})
        for mode, number in (('nvidia', 1), ('phoenix', 3)):
            if (output / 'STOP').exists():
                break
            if args.resume and current_pass(case / mode / 'result.json', game):
                continue
            target = case / mode
            if installed.returncode:
                target.mkdir(exist_ok=True)
                failure = dict(id=game['id'], backend=mode, passed=False, state='error', source_suite='working',
                               profile=PROFILE, requested_seconds=MEASURE_SECONDS,
                               width=WIDTH, height=HEIGHT, warmup_seconds=WARMUP_SECONDS, vsync=False,
                               executable=str(exe), executable_sha256=game['sha256'],
                               error=installed.stderr.strip() or installed.stdout.strip() or plan.get('Preflight', {}).get('DisplayText') or 'Installer rejected this route')
                write(target / 'result.json', failure)
                emit(failure)
                continue
            ini_backend(folder, number)
            run_case(game, mode, folder, target, args.seconds, environment)
    from dashboard import export_snapshot
    data = export_snapshot()
    from summarize_backends import summarize
    summarize()
    emit({'dashboard_runs': len(data['runs']), 'output': str(output)})


if __name__ == '__main__':
    main()
