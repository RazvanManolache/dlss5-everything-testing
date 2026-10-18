"""Index existing benchmark output and serve the read-only local dashboard. Never runs fixtures."""
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, unquote
import argparse, csv, datetime, hashlib, json, math, mimetypes, os, socket, threading, webbrowser
from benchmark_errors import failure_reason

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'dashboard'
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def image_dimensions(path):
    try:
        from PIL import Image
        with Image.open(path) as image: return image.size
    except (ImportError, OSError, ValueError): return None, None


def read_json(path, warnings=None):
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as error:
        if warnings is not None:
            warnings.append({'path': path.relative_to(ROOT).as_posix(), 'message': str(error)[:180]})
        return {}


def finite(*values):
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            return value
    return None


def group_for(game):
    key = game['id']
    if key == 'dos-vga': return 'DOS / VGA'
    if key.startswith('warp_'): return 'Software / WARP'
    if key.startswith('dgvoodoo_'): return 'dgVoodoo wrappers'
    if key.startswith('dxvk_'): return 'DXVK wrappers'
    if key.startswith('gles'): return 'OpenGL ES / ANGLE'
    if key.startswith('glide'): return '3dfx Glide'
    if key.startswith('ddraw'): return 'DirectDraw 2D'
    if key.startswith('glcore'): return 'OpenGL core'
    if key.startswith('opengl'): return 'OpenGL classic'
    if key.startswith('vulkan'): return 'Vulkan'
    if key.startswith('d3d11on12'): return 'D3D11 on D3D12'
    if game.get('api') in ('dx2', 'dx3', 'dx5', 'dx6', 'dx7', 'dx8'): return 'Legacy DirectX'
    return 'Modern DirectX'


def image_url(path):
    from urllib.parse import quote
    return '../' + quote(path.relative_to(ROOT).as_posix(), safe='/')


def walk_safe(root):
    if not root.is_dir() or root.is_symlink() or root.is_junction(): return
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = sorted(name for name in folders if not (Path(directory) / name).is_symlink()
                            and not (Path(directory) / name).is_junction())
        yield Path(directory), files


def collect_samples(fps, runtime, folder):
    samples = []
    for row in fps.get('samples', runtime.get('samples', [])) or []:
        if not isinstance(row, dict): continue
        t = finite(row.get('elapsed_seconds')); value = finite(row.get('fps'))
        if t is not None and value is not None:
            samples.append({'seconds': t, 'fps': value})
    if not samples and (folder / 'FPS.CSV').is_file():
        try:
            previous = None
            with (folder / 'FPS.CSV').open(encoding='utf-8-sig', newline='') as stream:
                for row in csv.DictReader(stream):
                    if len(samples) >= 2000: break
                    try:
                        t = float(row.get('elapsed_seconds', 'nan'))
                        if not math.isfinite(t) or t < 0: continue
                        if row.get('fps'):
                            v = float(row['fps'])
                            if math.isfinite(v) and v >= 0: samples.append({'seconds': t, 'fps': v})
                        elif row.get('frame'):
                            frame = int(row['frame'])
                            if previous and t - previous[0] >= 1:
                                samples.append({'seconds': t, 'fps': (frame - previous[1]) / (t - previous[0])})
                                previous = (t, frame)
                            elif previous is None: previous = (t, frame)
                    except (ValueError, TypeError): continue
        except OSError: pass
    if len(samples) > 1000:
        stride = math.ceil(len(samples) / 1000)
        samples = samples[::stride]
    return samples


def make_data():
    warnings = []
    matrix = read_json(ROOT / 'matrix.json', warnings)
    fixtures = []
    for original in matrix.get('games', []):
        game = dict(original)
        game['group'] = group_for(game)
        game['label'] = game['id'].rsplit('-', 1)[0].replace('_', ' ').upper()
        game['transport'] = game.get('render_transport', game.get('api', 'Unknown'))
        fixtures.append(game)
    dos = read_json(ROOT / 'games/dos-vga/test-game.json', warnings)
    if dos:
        dos.update(id='dos-vga', label='DOS VGA', group='DOS / VGA', api='vga', transport='CPU / VGA', architecture='i386')
        fixtures.append(dos)
    by_id = {game['id']: game for game in fixtures}
    candidates = set()
    image_names = {'capture.png', 'CAPTURE.BMP'}
    roots = [ROOT / 'runs']
    for suite in (ROOT, ROOT / 'clean'):
        for game in fixtures:
            roots.append(suite / 'games' / game['id'] / 'run')
    for root in roots:
        for folder, files in walk_safe(root):
            lower = {name.lower() for name in files}
            if lower & {'status.json', 'fps.json', 'result.json', 'result.jsn', 'captures.json'} or any(
                name in image_names or name.lower().startswith('capture-') or
                (name.upper().startswith('CAP') and name.upper().endswith('.BMP')) for name in files):
                candidates.add(folder)
    runs = []
    captures = []
    for folder in sorted(candidates):
        status = read_json(folder / 'status.json', warnings)
        fps = read_json(folder / 'fps.json', warnings)
        verify = read_json(folder / 'verification.json', warnings)
        result = read_json(folder / 'result.json', warnings)
        runtime = status or read_json(folder / 'RESULT.JSN', warnings) or result.get('runtime', result) or verify.get('runtime', {})
        if not isinstance(runtime, dict): runtime = {}
        if not fps and isinstance(runtime.get('benchmark'), dict): fps = runtime['benchmark']
        key = result.get('id') or verify.get('id') or runtime.get('id')
        if key not in by_id:
            key = next((part for part in reversed(folder.relative_to(ROOT).parts) if part in by_id), None)
        is_dos = (folder / 'MUSEUM.EXE').is_file() or (folder / 'RESULT.JSN').is_file()
        if is_dos: key = 'dos-vga'
        if key not in by_id:
            api = runtime.get('api'); arch = runtime.get('architecture')
            choices = [g['id'] for g in fixtures if g.get('api') == api and g.get('architecture') == arch]
            if len(choices) == 1: key = choices[0]
        game = by_id.get(key, {})
        suite = 'unknown'
        relative = folder.relative_to(ROOT).as_posix()
        if relative.startswith('clean/games/'): suite = 'clean'
        elif relative.startswith('games/'): suite = 'working'
        source_exe = verify.get('executable', result.get('executable', ''))
        command = verify.get('command', [])
        if isinstance(command, list) and '--suite' in command:
            index = command.index('--suite')
            if index + 1 < len(command): source_exe = str(command[index + 1]) + '/games/'
        if source_exe:
            normalized = str(source_exe).replace('\\', '/').lower()
            if '/clean/games/' in normalized: suite = 'clean'
            elif '/games/' in normalized: suite = 'working'
        recorded_hash = verify.get('sha256') or verify.get('executable_sha256') or result.get('sha256') or result.get('executable_sha256')
        if is_dos and (folder / 'MUSEUM.EXE').is_file():
            recorded_hash = hashlib.sha256((folder / 'MUSEUM.EXE').read_bytes()).hexdigest()
        expected = game.get('sha256')
        fresh = 'current' if expected and recorded_hash == expected else 'stale' if expected and recorded_hash else 'unverified'
        passed = verify.get('passed', result.get('passed'))
        state = runtime.get('state')
        outcome = 'not_applicable' if result.get('applicable') is False else 'failed' if state == 'error' or passed is False else 'complete' if state == 'complete' else 'incomplete'
        mode = result.get('backend') or runtime.get('mode') or verify.get('mode') or result.get('mode') or 'unknown'
        samples = collect_samples(fps, runtime, folder)
        game_fps = finite(fps.get('game_fps'), fps.get('average_fps'), runtime.get('average_fps'))
        neural_fps = finite(result.get('neural_fps'))
        enhanced = mode in ('nvidia','phoenix') and key != 'dos-vga'
        game_samples = [{'seconds':s.get('elapsed_seconds'), 'fps':s.get('fps')}
                        for s in fps.get('game_samples', [])] if 'game_samples' in fps else list(samples)
        if enhanced and fps.get('counter') != 'delivered':
            samples = []  # Old game-loop samples are not fresh-output samples.
        rid = relative
        item = {'id': rid, 'fixture_id': key, 'label': game.get('label', folder.name),
                'group': game.get('group', 'Unassigned'), 'api': game.get('application_api', game.get('api', 'unknown')),
                'transport': game.get('transport', 'unknown'), 'architecture': game.get('architecture', 'unknown'),
                'suite': suite, 'mode': mode, 'status': outcome, 'freshness': fresh,
                'timestamp': datetime.datetime.fromtimestamp(folder.stat().st_mtime).astimezone().isoformat(),
                'fps': neural_fps if enhanced else finite(fps.get('average_fps'), runtime.get('average_fps')),
                'game_fps': game_fps, 'game_samples': game_samples,
                'minimum_fps': finite(fps.get('minimum_sample_fps')) if not enhanced or fps.get('counter') == 'delivered' else None,
                'maximum_fps': finite(fps.get('maximum_sample_fps')) if not enhanced or fps.get('counter') == 'delivered' else None,
                'seconds': finite(fps.get('elapsed_seconds'), runtime.get('seconds')),
                'frames': finite(fps.get('frames_rendered'), runtime.get('frames')),
                'width': runtime.get('width', result.get('width')),
                'height': runtime.get('height', result.get('height')), 'samples': samples,
                'background': runtime.get('background', verify.get('headless')),
                'software': game.get('software_renderer', False) or is_dos,
                'gpu': runtime.get('gpu'), 'controls': runtime.get('controls', {}),
                'neural_fps': neural_fps,
                'fps_scope': 'Fresh completed enhanced outputs / host wall seconds' if enhanced else fps.get('fps_scope', result.get('fps_scope')),
                'neural_fps_scope': fps.get('neural_fps_scope'),
                'processing': result.get('processing', {}), 'scene_mode': runtime.get('mode'),
                'execution_mode': result.get('execution_mode') or result.get('processing', {}).get('execution_mode') or result.get('diagnostics', {}).get('execution_mode'),
                'execution_variant': result.get('execution_variant'),
                'execution_label': result.get('execution_label'),
                'requested_execution_mode': result.get('requested_execution_mode'),
                'first_ready_render_seconds': result.get('first_ready_render_seconds'),
                'startup_in_measurement': (enhanced and isinstance(result.get('first_ready_render_seconds'), (int, float))
                    and result['first_ready_render_seconds'] > result.get('warmup_seconds', 5)),
                'captured_api': result.get('processing', {}).get('api'),
                'benchmark_profile': result.get('profile'),
                'addon_sha256': result.get('addon_sha256'),
                'comparison_batch': '/'.join(folder.relative_to(ROOT).parts[:2]) if relative.startswith('runs/') else None,
                'requested_seconds': result.get('requested_seconds'),
                'warmup_seconds': result.get('warmup_seconds'),
                'vsync': result.get('vsync'),
                'measurement_complete': (result.get('measurement') or fps.get('measurement') or {}).get('complete'),
                'benchmark_warnings': result.get('benchmark_warnings') or [],
                'error': str(failure_reason(result) or runtime.get('error', ''))[:500], 'captures': [],
                'executable_sha256': recorded_hash, 'expected_sha256': expected,
                'checks_passed': sum(value is True for value in verify.get('checks', {}).values()),
                'checks_total': len(verify.get('checks', {})), 'reference': False}
        failed_backend = result.get('backend') in ('native', 'nvidia', 'phoenix') and result.get('passed') is False
        if failed_backend:
            for field in ('fps', 'game_fps', 'minimum_fps', 'maximum_fps', 'neural_fps', 'seconds', 'frames'):
                item[field] = None
            item['samples'] = []
            item['game_samples'] = []
            item['processing'] = {}
        manifest = read_json(folder / 'captures.json', warnings)
        presented_only = result.get('capture_source') == 'phoenix_presented_output'
        records = [] if failed_backend else (manifest.get('captures') or []) if presented_only else manifest.get('captures') or fps.get('captures') or runtime.get('captures') or []
        selected = []
        for record in records:
            if not isinstance(record, dict): continue
            for field in ('png', 'bmp'):
                name = record.get(field)
                if not isinstance(name, str): continue
                # Capture manifests may name files only, never follow external paths.
                if Path(name).name != name: continue
                image = folder / name
                if image.is_file() and image.suffix.lower() in IMAGES and not image.is_symlink():
                    selected.append((image, record)); break
        if not selected and not presented_only and not failed_backend:
            images = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGES and not p.is_symlink())
            preferred = [p for p in images if p.stem.lower().startswith('capture-') or (p.stem.upper().startswith('CAP') and p.stem[3:].isdigit())]
            if preferred: images = preferred
            elif (folder / 'capture.png').is_file(): images = [folder / 'capture.png']
            elif (folder / 'CAPTURE.BMP').is_file(): images = [folder / 'CAPTURE.BMP']
            selected = [(p, {}) for p in images]
        unique_images = {}
        for image, record in selected:
            cid = image.relative_to(ROOT).as_posix()
            occurrence = {'id': cid, 'name': image.name,
                          'requested_seconds': finite(record.get('requested_seconds')),
                          'seconds': finite(record.get('elapsed_seconds')), 'frame': record.get('frame')}
            digest = hashlib.sha256(image.read_bytes()).digest()
            if digest in unique_images:
                existing = unique_images[digest]
                if not any(saved['id'] == cid for saved in existing['occurrences']):
                    existing['occurrences'].append(occurrence)
                continue
            capture = {'id': cid, 'run_id': rid, 'src': image_url(image), 'name': image.name,
                       'requested_seconds': finite(record.get('requested_seconds')),
                       'seconds': finite(record.get('elapsed_seconds')), 'frame': record.get('frame'),
                       'shared_frame': bool(record.get('shared_frame')), 'bytes': image.stat().st_size,
                       'occurrences': [occurrence]}
            capture['width'], capture['height'] = image_dimensions(image)
            unique_images[digest] = capture
            captures.append(capture); item['captures'].append(cid)
        runs.append(item)
    reference = ROOT / 'state/matched-reference.png'
    if reference.is_file() and not any(r['id'].startswith('runs/latest-x64-backends/') for r in runs):
        runs.append({'id': 'reference', 'fixture_id': 'dx11-x64', 'label': 'Matched reference',
                     'group': 'Modern DirectX', 'api': 'dx11', 'transport': 'dx11', 'architecture': 'x64',
                     'suite': 'reference', 'mode': 'matched', 'status': 'reference', 'freshness': 'unverified',
                     'timestamp': datetime.datetime.fromtimestamp(reference.stat().st_mtime).astimezone().isoformat(),
                     'fps': None, 'samples': [], 'captures': ['state/matched-reference.png'], 'reference': True,
                     'controls': {}, 'background': None, 'error': ''})
        captures.append({'id': 'state/matched-reference.png', 'run_id': 'reference', 'src': image_url(reference),
                         'name': 'Matched reference', 'seconds': None, 'requested_seconds': None,
                         'frame': None, 'shared_frame': False, 'bytes': reference.stat().st_size})
        captures[-1]['width'], captures[-1]['height'] = image_dimensions(reference)
    groups = sorted(set(g['group'] for g in fixtures))
    return {'schema': 1, 'generated_at': datetime.datetime.now().astimezone().isoformat(),
            'fixtures': fixtures, 'runs': runs, 'captures': captures, 'groups': groups, 'warnings': warnings,
            'build': read_json(ROOT / 'state/controls-build.json'),
            'notes': ['Only existing local results are indexed. This dashboard never launches tests.',
                      'Hidden-window FPS, WARP/CPU rendering and DOS emulation measure different workloads.',
                      'DOS stays at 320x200: native FPS uses the guest clock; enhanced presentation and processed FPS use host wall time. These are distinct rates, not a matched native-loss comparison.',
                      'Stale or unverified captures do not validate the current build. Missing FPS is never shown as zero.']}


def export_snapshot():
    data = make_data()
    DASH.mkdir(exist_ok=True)
    (DASH / 'data.js').write_text('window.BENCH_DATA = ' + json.dumps(data, ensure_ascii=True).replace('<', '\\u003c') + ';\n', encoding='utf-8')
    return data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        host = self.headers.get('Host', '').split(':', 1)[0].lower()
        if host not in ('127.0.0.1', 'localhost'):
            self.send_error(403); return
        route = unquote(urlsplit(self.path).path)
        if route in ('/', '/dashboard', '/dashboard/'):
            self.send_response(302); self.send_header('Location', '/dashboard/index.html'); self.end_headers(); return
        if route == '/api/data':
            try:
                body = json.dumps(make_data(), ensure_ascii=True).encode()
                self.send_body(body, 'application/json; charset=utf-8')
            except Exception:
                self.send_error(500, 'Could not index benchmark results')
            return
        relative = Path(route.lstrip('/'))
        if relative.is_absolute() or '..' in relative.parts or '\\' in route or ':' in route:
            self.send_error(403); return
        allowed_static = {'dashboard/index.html', 'dashboard/app.js', 'dashboard/performance.js', 'dashboard/styles.css', 'dashboard/data.js', 'dashboard/favicon.svg'}
        allowed_image = relative.suffix.lower() in IMAGES and relative.parts and relative.parts[0] in ('runs', 'games', 'clean', 'state')
        if relative.as_posix() not in allowed_static and not allowed_image:
            self.send_error(404); return
        path = ROOT / relative
        try:
            if not path.resolve().is_relative_to(ROOT.resolve()) or not path.is_file():
                self.send_error(404); return
            for part in [path, *list(path.parents)[:len(relative.parts) - 1]]:
                if part.is_symlink() or part.is_junction():
                    self.send_error(403); return
            self.send_body(path.read_bytes(), mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        except OSError:
            self.send_error(404)

    def send_body(self, body, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass


class DashboardServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can bind two listeners to the same port, mixing versions.
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', action='store_true', help='Refresh the offline snapshot and exit')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true', help='Open the dashboard in the default browser')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535: parser.error('Invalid port')
    data = export_snapshot()
    print(f"Indexed {len(data['fixtures'])} fixtures, {len(data['runs'])} result sets, {len(data['captures'])} images. No tests launched.", flush=True)
    if args.export: return
    try: server = DashboardServer(('127.0.0.1', args.port), Handler)
    except OSError as error: parser.error(f'Could not start local dashboard: {error}. Try --port 8766.')
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_port}/dashboard/index.html'
    print('Dashboard: ' + url, flush=True)
    if args.open: threading.Timer(.3, lambda: webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
