"""Run separate native test games without showing or activating their windows."""
from pathlib import Path
import argparse,csv,ctypes,datetime,hashlib,json,os,subprocess,time
from ctypes import wintypes
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageOps
from verify import pe_info,EXPECTED
from fixture_checks import expected_imports,inspect_variant
from storage_policy import latest_output
from control_options import add_control_arguments,control_arguments
from capture_options import add_arguments,schedule,native_arguments,check_captures

ROOT=Path(__file__).resolve().parents[1]
user32=ctypes.WinDLL('user32',use_last_error=True)
user32.GetForegroundWindow.restype=wintypes.HWND
user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes=[wintypes.HWND]
CALLBACK=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
user32.EnumWindows.argtypes=[CALLBACK,wintypes.LPARAM]

def process_for_window(hwnd):
    pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));return pid.value

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',type=Path,default=ROOT);p.add_argument('--list',action='store_true');p.add_argument('--allow-installed',action='store_true');p.add_argument('--only',nargs='+');p.add_argument('--mode',choices=['matched','showcase'],default='showcase');p.add_argument('--seconds',type=float,default=30);add_arguments(p);p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=720);p.add_argument('--fixed-time',action='store_true');p.add_argument('--matched-results',type=Path);p.add_argument('--output',type=Path,default=None);add_control_arguments(p);a=p.parse_args()
    try:
        if a.seconds<=0:raise ValueError('Timed runs require positive --seconds')
        a.capture_times=schedule(a.seconds,a.capture_at,a.capture_every);a.capture_at=a.capture_times[0]
    except ValueError as error:p.error(str(error))
    if not 320<=a.width<=3840 or not 240<=a.height<=2160:p.error('Invalid render dimensions')
    games=json.loads((a.suite/'matrix.json').read_text())['games'];ids={g['id'] for g in games}
    if a.only and not set(a.only)<=ids:p.error('Unknown game requested')
    if a.list:
        for g in games:
            if not a.only or g['id'] in a.only:print(g['id'],'|',g.get('application_api',g['api']),'->',g.get('render_transport',g['api']))
        return
    a.output=latest_output(a.output,'latest-windows')
    if a.output.exists() and any(a.output.iterdir()):p.error('Choose a new empty output directory to keep evidence fresh')
    a.output.mkdir(parents=True,exist_ok=True);results=[]
    for game in games:
        key=game['id']
        if a.only and key not in a.only:continue
        out=(a.output/key).resolve();out.mkdir();exe=(a.suite/game['executable']).resolve();checks={};result={'id':key,'mode':a.mode,'passed':False,'checks':checks,'executable':str(exe)}
        proc=None;start=time.perf_counter();visible_windows=set();foreground_hits=0;samples=0
        try:
            result['sha256']=hashlib.sha256(exe.read_bytes()).hexdigest();info=pe_info(exe);result.update(info)
            command=[str(exe),'--background','--mode',a.mode,'--seconds',str(a.seconds),*native_arguments(a.capture_times),'--width',str(a.width),'--height',str(a.height),'--output',str(out)]
            command+=control_arguments(a)
            if a.fixed_time:command+=['--fixed-time']
            result['command']=command;print('Running',key,a.mode,f'{a.seconds:g}s / screenshots {a.capture_times}',flush=True)
            env=os.environ.copy();env.update(DXVK_LOG_PATH=str(out),DXVK_STATE_CACHE_PATH=str(out),DXVK_SHADER_CACHE_PATH=str(out));proc=subprocess.Popen(command,env=env)
            @CALLBACK
            def inspect_window(hwnd,_):
                if process_for_window(hwnd)==proc.pid and user32.IsWindowVisible(hwnd):visible_windows.add(int(hwnd))
                return True
            while proc.poll() is None:
                if time.perf_counter()-start>a.seconds+90:raise TimeoutError('Background run exceeded duration plus startup timeout')
                if process_for_window(user32.GetForegroundWindow())==proc.pid:foreground_hits+=1
                user32.EnumWindows(inspect_window,0);samples+=1;time.sleep(.05)
            state=json.loads((out/'status.json').read_text());fps=json.loads((out/'fps.json').read_text());result['runtime']=state;checks.update(inspect_variant(game,state,exe.parent,a.allow_installed));result['fps']=fps;result['exit_code']=proc.returncode
            png=Image.open(out/'capture.png').convert('RGB');ppm=Image.open(out/'capture.ppm').convert('RGB');image=np.asarray(png)
            checks.update(correct_architecture=info['architecture']==game['architecture'],current_executable=result['sha256']==game['sha256'],native_api_import=all(dll in info['imports'] for dll in expected_imports(game,EXPECTED)),native_runtime_loaded=all(dll in [Path(m).name.lower() for m in (state.get('render_loaded_modules') or state['loaded_modules'])] for dll in expected_imports(game,EXPECTED)),completed=proc.returncode==0 and state['state']=='complete' and fps['frames_rendered']>0,correct_mode=state['mode']==a.mode,hidden_window=state['background'] and (not state['window_visible'] or state.get('background_isolated',False)) and not visible_windows,never_took_focus=foreground_hits==0 and samples>0,requested_duration=a.seconds<=fps['elapsed_seconds']<a.seconds+max(5,fps.get('maximum_frame_seconds',0)+1),timed_screenshot=a.capture_at<=fps['capture_elapsed_seconds']<a.capture_at+max(5,fps.get('maximum_frame_seconds',0)+1),nonblank_capture=float(image.std())>15,correct_dimensions=png.size==(state['width'],state['height']) and (state['client_width'],state['client_height'])==(a.width,a.height),png_matches_gpu_readback=png.size==ppm.size and np.array_equal(image,np.asarray(ppm)),fps_summary=fps['average_fps']>0 and abs(fps['average_fps']-fps['frames_rendered']/fps['elapsed_seconds'])<.001,fps_samples=fps['sample_count']==len(fps['samples']) and fps['sample_count']>=1 and all(sample['fps']>0 and sample['interval_seconds']>0 for sample in fps['samples']))
            rows=list(csv.DictReader((out/'fps.csv').open()));checks['fps_csv']=len(rows)==fps['sample_count']
            records=fps.get('captures',[{'requested_seconds':a.capture_at,'elapsed_seconds':fps['capture_elapsed_seconds'],'png':'capture.png','ppm':'capture.ppm'}])
            checks.update(check_captures(out,a.capture_times,records,max(5,fps.get('maximum_frame_seconds',0)+1)))
            if a.mode=='showcase' and a.matched_results:
                reference=Image.open(a.matched_results/key/'capture.png').convert('RGB').resize(png.size,Image.Resampling.LANCZOS)
                difference=float(np.abs(image.astype(float)-np.asarray(reference).astype(float)).mean());result['mean_absolute_difference_from_matched']=difference;checks['showcase_changes_rendered_pixels']=difference>1
            result['passed']=all(checks.values());result['window_observation']={'samples':samples,'interval_seconds':.05,'visible_windows':sorted(visible_windows),'foreground_hits':foreground_hits}
        except Exception as error:
            result['error']=str(error)
            if proc is not None and proc.poll() is None:proc.kill();proc.wait()
        result['wall_seconds']=time.perf_counter()-start;results.append(result)
        fps=result.get('fps',{});print(key,'PASS' if result['passed'] else 'FAIL','average FPS',round(fps.get('average_fps',0),2),result.get('error',''),flush=True)
        report={'passed':bool(results) and all(r['passed'] for r in results),'tested_games':len(results),'mode':a.mode,'seconds_per_game':a.seconds,'capture_at_seconds':a.capture_at,'capture_times_seconds':a.capture_times,'seed_integrity_enforced':not a.allow_installed,'scope':'Hidden native renderer runs and pre-presentation GPU screenshots. FPS measures the hidden render loop, not visible display throughput or addon inference.','results':results}
        (a.output/'summary.json').write_text(json.dumps(report,indent=2));(a.output/'verification.json').write_text(json.dumps(report,indent=2))
    with (a.output/'summary.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['game','mode','passed','seconds','frames','average_fps','minimum_sample_fps','maximum_sample_fps','screenshot_seconds'])
        for r in results:
            fps=r.get('fps',{});writer.writerow([r['id'],a.mode,r['passed'],*[fps.get(k,'') for k in ('elapsed_seconds','frames_rendered','average_fps','minimum_sample_fps','maximum_sample_fps','capture_elapsed_seconds')]])
    if results:
        canvas=Image.new('RGB',(4*400,((len(results)+3)//4)*260),(18,22,28));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
        for i,r in enumerate(results):
            x=(i%4)*400;y=(i//4)*260;fps=r.get('fps',{});draw.text((x+6,y+2),f"{r['id']} / {fps.get('average_fps',0):.1f} FPS / {'PASS' if r['passed'] else 'FAIL'}",font=font,fill=(140,235,180) if r['passed'] else (255,120,100));path=a.output/r['id']/'capture.png'
            if path.exists():
                tile=ImageOps.contain(Image.open(path),(400,225));canvas.paste(tile,(x+(400-tile.width)//2,y+30+(225-tile.height)//2))
        canvas.save(a.output/'contact-sheet.jpg',quality=94)
    print('Results:',a.output.resolve(),flush=True)
    if not results or not all(r['passed'] for r in results):raise SystemExit(1)

if __name__=='__main__':main()
