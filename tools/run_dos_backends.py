"""Validate DOS through the installer's DOSBox Enhanced preparation path.

DOS retains its native VGA extent. Its direct, in-process renderer does not use
ReShade, and guest/emulator frame rates are not Windows game FPS benchmarks.
"""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import numpy as np
from PIL import Image
from dos_fps import guest_fps, graphics_fps
from run_backends import ROOT, close_fixture, digest, emit, failure_record, read, write


class DosControl:
    def __init__(self, port, token):
        self.url = f'http://127.0.0.1:{port}/mcp'
        self.headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                        'Accept': 'application/json', 'MCP-Protocol-Version': '2025-11-25'}
        self.counter = 0
        self.rpc('initialize', {'protocolVersion':'2025-11-25', 'capabilities':{},
                                'clientInfo':{'name':'compatibility-check','version':'1'}})
        self.rpc('notifications/initialized', {}, notification=True)

    def rpc(self, method, params, notification=False):
        self.counter += 1
        body = dict(jsonrpc='2.0', method=method, params=params)
        if not notification:
            body['id'] = self.counter
        request = urllib.request.Request(self.url, json.dumps(body).encode(), self.headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            session = response.headers.get('Mcp-Session-Id')
            if session:
                self.headers['Mcp-Session-Id'] = session
            data = response.read()
        result = json.loads(data) if data else {}
        if 'error' in result:
            raise RuntimeError(str(result['error']))
        return result.get('result', {})

    def tool(self, name, **arguments):
        value = self.rpc('tools/call', dict(name=name, arguments=arguments))
        if value.get('isError'):
            raise RuntimeError(str(value.get('content')))
        return value

    def status(self):
        return json.loads(self.tool('dosbox_status')['content'][0]['text'])


def link_package(source, payload):
    target = payload / 'dosbox-enhanced'
    members = [Path('app/DosboxEnhanced.exe')]
    members += [Path('runtime') / name for name in
                ('dosbox_pure_libretro.dll', 'dosbox_nvngx.dll', 'phoenix_native.dll')]
    for folder in ('runtime/native', 'runtime/nvidia'):
        members += [path.relative_to(source) for path in (source / folder).rglob('*') if path.is_file()]
    for member in members:
        src, dst = source / member, target / member
        if src.is_symlink() or src.is_junction():
            raise RuntimeError('DOS package inputs must not be links')
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.link(src, dst)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--dos-package', type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / 'runs/latest-x64-backends/dos-vga'
    output.mkdir(parents=True, exist_ok=True)
    clean = ROOT / 'clean/games/dos-vga/MUSEUM.EXE'
    working = ROOT / 'games/dos-vga/MUSEUM.EXE'
    if digest(clean) != digest(working):
        raise RuntimeError('DOS clean and working executable builds differ')
    common = dict(id='dos-vga', executable_sha256=digest(clean), requested_seconds=20,
                  warmup_seconds=5, profile='dos-native-vga-compatibility-v1', width=320, height=200,
                  execution_mode='in_process', benchmark_note='320x200 DOS emulation; not comparable to Windows FPS')
    with tempfile.TemporaryDirectory(prefix='dos-backends-', dir=ROOT / 'build') as temporary:
        stage = Path(temporary)
        payload = stage / 'payload'
        payload.mkdir()
        os.link(args.payload.resolve() / 'nvngx_dlssnr.dll', payload / 'nvngx_dlssnr.dll')
        link_package(args.dos_package.resolve(), payload)
        reference = None
        for mode in ('native', 'nvidia', 'phoenix'):
            target = output / mode
            target.mkdir(exist_ok=True)
            for path in target.iterdir():
                if not path.is_file() or path.is_symlink():
                    raise RuntimeError('Unexpected member in owned DOS results')
                path.unlink()
            result = dict(common, backend=mode, executable=str(clean if mode == 'native' else working),
                          source_suite='clean' if mode == 'native' else 'working', passed=None)
            write(target / 'result.json', result)
            process = None
            try:
                if mode == 'native':
                    native = stage / 'native'
                    subprocess.run([sys.executable, str(ROOT / 'tools/run_dos.py'), '--suite', str(ROOT / 'clean'),
                                    '--background', '--seconds', '25', '--capture-at', '25', '--fixed-time',
                                    '--output', str(native)], cwd=ROOT, check=True, capture_output=True, timeout=300)
                    if not read(native / 'verification.json').get('passed'):
                        raise RuntimeError('Clean DOS baseline validation failed')
                    with Image.open(native / 'capture.png') as image:
                        frame = image.convert('RGB')
                    reference = np.asarray(frame).astype(float)
                    fps = guest_fps(native / 'FPS.CSV')
                    result.update(profile='dos-guest-clock-warmup5-measure20-v2', vsync=None)
                    result.update(passed=True, capture_source='emulated_vga_readback', execution_mode='native')
                else:
                    prepared = stage / (mode + '-session.json')
                    command = [str(args.installer.resolve()), '--prepare-dos', str(working),
                               '--payload', str(payload), '--output', str(prepared)]
                    run = subprocess.run(command, capture_output=True, text=True, timeout=90)
                    if run.returncode:
                        raise RuntimeError(run.stderr.strip() or 'Installer DOS preparation failed')
                    session = read(prepared)
                    runtime, profile_path = Path(session['runtime']), Path(session['profile'])
                    profile = read(profile_path)
                    guest = runtime / 'guest'
                    guest.mkdir()
                    for name in ('MUSEUM.EXE', 'CWSDPMI.EXE'):
                        shutil.copy2(working.parent / name, guest / name)
                    (guest / 'CHECK.BAT').write_text('@echo off\nMUSEUM.EXE --fixed-time --freeze --seconds 0 --capture-at 999999\n')
                    profile['Drives'] = [dict(Letter='C', Folder=str(guest), Type='dir'),
                                         dict(Letter='D', Folder=str(ROOT / 'dos/assets'), Type='dir')]
                    profile['Startup'] = 'C:\\CHECK.BAT'
                    profile['Effects'].update(Enabled=True, Renderer=mode, Intensity=1, Compare=False,
                                              NvidiaUpscaling=False, NvidiaFrameGeneration=False, InputResize=False)
                    profile['DosboxSettings'] = {'cpu':{'cycles':'max'}, 'sblaster':{'sbtype':'none'}}
                    write(profile_path, profile)
                    with socket.socket() as probe:
                        probe.bind(('127.0.0.1', 0))
                        port = probe.getsockname()[1]
                    token = secrets.token_hex(32)
                    (runtime / 'data').mkdir(exist_ok=True)
                    write(runtime / 'data/preferences.json', dict(Audio=dict(Volume=0, Muted=True),
                          Mcp=dict(Enabled=True, AllowRemote=False, AllowControl=True, Port=port, Token=token)))
                    process = subprocess.Popen([session['executable'], '--profile', str(profile_path)], cwd=runtime)
                    control, deadline = None, time.monotonic() + 35
                    while time.monotonic() < deadline and process.poll() is None:
                        try:
                            control = DosControl(port, token)
                            break
                        except OSError:
                            time.sleep(.2)
                    if not control:
                        raise RuntimeError('Prepared DOSBox Enhanced did not expose its control endpoint')
                    started = None
                    snapshots = []
                    deadline = time.monotonic() + 90
                    counter = 'nr_frames' if mode == 'nvidia' else 'phoenix_frames'
                    while time.monotonic() < deadline and process.poll() is None:
                        status = control.status()
                        graphics = status.get('graphics') or {}
                        if 'unavailable' in status.get('graphicsStatus', '').lower() or status.get('error'):
                            raise RuntimeError(status.get('error') or status['graphicsStatus'])
                        if status.get('ready') and (status.get('width'),status.get('height')) == (320,200) and graphics.get('renderer') == mode and graphics.get(counter,0)>0:
                            if started is None:
                                started = time.monotonic()
                            snapshots.append(dict(seconds=time.monotonic()-started, graphics=graphics))
                            if time.monotonic()-started >= 25:
                                break
                        time.sleep(.5)
                    if started is None or time.monotonic()-started < 25:
                        raise RuntimeError('No sustained native-resolution DOS enhancement')
                    if snapshots[-1]['graphics'].get('presented',0) <= snapshots[0]['graphics'].get('presented',0):
                        raise RuntimeError('DOS renderer did not continue presenting output')
                    fps = graphics_fps(snapshots, mode)
                    result.update(profile='dos-host-clock-warmup5-measure20-v2', vsync=True,
                                  neural_fps=fps['neural_fps'])
                    capture = control.tool('dosbox_screenshot', enhanced=True)
                    block = next(item for item in capture['content'] if item['type']=='image')
                    with Image.open(io.BytesIO(base64.b64decode(block['data']))) as image:
                        frame = image.convert('RGB')
                    if reference is None or frame.size != (320,200):
                        raise RuntimeError('Matching native DOS baseline is unavailable')
                    # Exclude the DOS fixture's changing FPS/status text at the edges.
                    delta = np.abs(np.asarray(frame).astype(float)[50:150,80:240]-reference[50:150,80:240])
                    if delta.mean() <= .25 or (delta.max(axis=2)>2).mean() <= .01:
                        raise RuntimeError('DOS enhanced pixels are unchanged from the clean baseline')
                    result.update(passed=True, capture_source='dosbox_enhanced_direct_output',
                                  processing=dict(execution_mode='in_process', api='DOSBox Enhanced / D3D12',
                                                  backend=mode, reshade_required=False, direct_renderer=True),
                                  central_mae=float(delta.mean()))
                    write(target / 'processing.json', dict(snapshots=snapshots))
                if np.asarray(frame).std() < 15:
                    raise RuntimeError('DOS screenshot is blank')
                name = f'dos-vga-{mode}-320x200.png'
                frame.save(target / name)
                result.update(average_fps=fps['average_fps'], elapsed_seconds=fps['elapsed_seconds'],
                              measurement=fps['measurement'], fps_scope=fps['fps_scope'])
                write(target / 'fps.json', fps)
                write(target / 'captures.json', dict(captures=[dict(png=name, backend=mode, source=result['capture_source'])]))
                write(target / 'status.json', dict(state='complete', width=320, height=200, api='DOS VGA',
                      mode='showcase', background=mode=='native', controls=dict(frozen=True)))
            except Exception as error:
                for path in target.iterdir():
                    if path.is_file():
                        path.unlink()
                result = failure_record(dict(result, passed=False, error=str(error)))
            finally:
                if process:
                    close_fixture(process)
            write(target / 'result.json', result)
            emit(result)
    from dashboard import export_snapshot
    export_snapshot()
    if (ROOT/'runs/latest-x64-backends/execution-sweep.json').is_file():
        from summarize_execution_sweep import summarize
    else:
        from summarize_backends import summarize
    summarize()


if __name__ == '__main__':
    main()
