"""Launch the DOS gallery in DOSBox Staging, optionally without any visible window."""
from pathlib import Path
import argparse,datetime,json,os,shutil,subprocess,time,hashlib,ctypes
from ctypes import wintypes
from PIL import Image
from publish_sets import ROOT,load_config,write_json
from capture_options import add_arguments,schedule,check_captures
from asset_paths import find_assets
from storage_policy import latest_output
from control_options import control_arguments


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',type=Path,default=ROOT)
    p.add_argument('--background',action='store_true')
    p.add_argument('--room',action='store_true')
    p.add_argument('--tour',action='store_true')
    p.add_argument('--fixed-time',action='store_true')
    p.add_argument('--freeze',action='store_true')
    p.add_argument('--orbit',action='store_true')
    p.add_argument('--camera',choices=['free','orbit'])
    p.add_argument('--animations',choices=['on','off'])
    p.add_argument('--camera-motion',choices=['on','off'])
    p.add_argument('--no-animations',action='store_true')
    p.add_argument('--mode',choices=['matched','showcase'],default='showcase')
    p.add_argument('--seconds',type=float)
    add_arguments(p)
    p.add_argument('--frames',type=int)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    seconds=a.seconds if a.seconds is not None else 30 if a.background and not a.frames else 0
    if a.background and seconds<=0 and not a.frames:p.error('A background run needs positive --seconds or a frame limit')
    try:times=schedule(seconds,a.capture_at,a.capture_every,default=not a.frames or seconds>0)
    except ValueError as error:p.error(str(error))
    capture=times[0] if times else -1
    if a.frames is not None and a.frames<1:p.error('--frames must be positive')
    output=latest_output(a.output,'latest-dos')
    if output.exists() and any(output.iterdir()):p.error('Choose a new empty output folder')
    output.mkdir(parents=True,exist_ok=True)
    folder=a.suite.resolve()/'games/dos-vga'
    # A fresh mounted DOS directory keeps captures/logs out of the installed set.
    for name in ('MUSEUM.EXE','CWSDPMI.EXE'):shutil.copy2(folder/name,output/name)
    assets=find_assets(folder,dos=True)
    exe=next((ROOT/'vendor/dos/dosbox').rglob('dosbox.exe'))
    command='museum --mode '+a.mode
    if seconds:command+=' --seconds '+str(seconds)
    if times:
        (output/'SHOTS.TXT').write_text('\n'.join(format(t,'.12g') for t in times)+'\n')
        command+=' --capture-file SHOTS.TXT'
    if a.frames:command+=' --frames '+str(a.frames)
    command+=' '+ ' '.join(control_arguments(a))
    for flag in ('room','tour','fixed_time'):
        if getattr(a,flag):command+=' --'+flag.replace('_','-')
    args=[str(exe),'--noprimaryconf','--nolocalconf','--set','output=texture',
          '--set','texture_renderer=software','--set','cpu_cycles=max',
          '--set','cpu_cycles_protected=auto','--set','memsize=64','--set','nosound=true',
          '--set','sbtype=none','--set','oplmode=none','--set','mididevice=none',
          '--set','windowresolution=desktop','--exit','-c','mount c "'+str(output)+'"',
          '-c','mount d "'+str(assets)+'"','-c','c:','-c',command]
    env=os.environ.copy()
    if a.background:env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    start=time.perf_counter()
    user32=ctypes.WinDLL('user32');user32.GetForegroundWindow.restype=wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes=[wintypes.HWND]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    user32.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
    visible=set();foreground_hits=0;maximized=set();samples=0
    def window_pid(hwnd):
        pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));return pid.value
    with (output/'emulator.log').open('w') as log:
        proc=subprocess.Popen(args,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        @callback_type
        def observe(hwnd,_):
            if window_pid(hwnd)==proc.pid and user32.IsWindowVisible(hwnd):
                visible.add(int(hwnd))
                if not a.background and int(hwnd) not in maximized:
                    user32.ShowWindow(hwnd,3);maximized.add(int(hwnd))
            return True
        deadline=max(180,seconds*8+90) if seconds or a.frames else None
        while proc.poll() is None:
            user32.EnumWindows(observe,0);samples+=1
            if window_pid(user32.GetForegroundWindow())==proc.pid:foreground_hits+=1
            if deadline and time.perf_counter()-start>deadline:
                proc.kill();proc.wait();raise TimeoutError('DOS emulator exceeded timeout')
            time.sleep(.04)
    state_path=output/'RESULT.JSN'
    if not state_path.exists():raise RuntimeError('DOS program did not finish; see '+str(output/'emulator.log'))
    state=json.loads(state_path.read_text());image=Image.open(output/'CAPTURE.BMP').convert('RGB')
    image.save(output/'capture.png')
    image.resize((640,480),Image.Resampling.NEAREST).save(output/'preview.png')
    records=state.get('captures',[])
    for i,record in enumerate(records,1):
        record['png']=f'capture-{i:05d}.png'
        Image.open(output/record['bmp']).convert('RGB').save(output/record['png'])
    write_json(output/'captures.json',{'requested_times':times,'captures':records,'pending':state.get('pending_captures',0)})
    import numpy as np
    checks={'emulator_exited':proc.returncode==0,'dos_completed':state['state']=='complete',
            'vga_mode':state['renderer']=='CPU / VGA mode 13h' and image.size==(320,200),
            'rendered_geometry':state['submitted_triangles']>0 and state['pixel_writes']>0,
            'nonblank':float(np.asarray(image).std())>15,'correct_view':state['room']==a.room,
            'correct_mode':state['mode']==a.mode,'fps_recorded':state['average_fps']>0 and (output/'FPS.CSV').stat().st_size>30,
            'actual_emulator_vga_mode':'256-colour graphics mode 13h' in (output/'emulator.log').read_text(errors='replace')}
    if seconds:checks['duration']=seconds<=state['seconds']<seconds+10;checks['timed_capture']=capture<=state['capture_seconds']<capture+10
    if a.frames:checks['frame_limit']=state['frames']==a.frames
    if a.background:checks['never_visible']=not visible;checks['never_took_focus']=foreground_hits==0 and samples>0
    if times:checks.update(check_captures(output,times,records,max(5,state.get('maximum_frame_seconds',0)+1)))
    result={'passed':all(checks.values()),'checks':checks,'runtime':state,
            'requested_seconds':seconds,'capture_times_seconds':times,'command':args,
            'emulator':'DOSBox Staging 0.83.0','host_seconds':time.perf_counter()-start,
            'executable_sha256':hashlib.sha256((output/'MUSEUM.EXE').read_bytes()).hexdigest(),
            'asset_sha256':hashlib.sha256((assets/'GALLERY.DAT').read_bytes()).hexdigest(),
            'window_observation':{'samples':samples,'visible_windows':sorted(visible),'foreground_hits':foreground_hits},
            'headless':a.background,'scope':'DOS guest rendering and a readback of the emulated VGA framebuffer; FPS is emulated guest throughput, not physical DOS hardware performance'}
    write_json(output/'verification.json',result);write_json(output/'result.json',state)
    print('DOS gallery','PASS' if result['passed'] else 'FAIL',state['frames'],'frames',round(state['average_fps'],2),'FPS',output,flush=True)
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
