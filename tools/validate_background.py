"""Parallel correctness checks; use run_background.py for sequential FPS comparisons."""
from pathlib import Path
import argparse,csv,json,os,shutil,subprocess,sys,time
from PIL import Image,ImageDraw,ImageFont,ImageOps
from capture_options import add_arguments,schedule,native_arguments
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',type=Path,required=True);p.add_argument('--only',nargs='+',required=True);p.add_argument('--matched-results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--jobs',type=int,default=3);p.add_argument('--seconds',type=float,default=30);add_arguments(p);a=p.parse_args()
    try:times=schedule(a.seconds,a.capture_at,a.capture_every)
    except ValueError as error:p.error(str(error))
    if not 1<=a.jobs<=4:p.error('Use one to four validation slots')
    if a.output.exists():p.error('Choose a new result directory')
    a.output.mkdir(parents=True);a.output=a.output.resolve();games=json.loads((a.suite/'matrix.json').read_text())['games'];wanted=set(a.only)
    if not wanted<={g['id'] for g in games}:p.error('Unknown fixture ID')
    pending=[g for g in games if g['id'] in wanted];active=[];results=[];softwareActive=False;lastWritten=-1
    context={'purpose':'Correctness validation under concurrent load. Use the sequential bench runner for FPS comparisons.','maximum_concurrent_runs':a.jobs,'maximum_concurrent_explicit_warp_runs':1}
    (a.output/'validation-context.json').write_text(json.dumps(context,indent=2))
    while pending or active:
        while len(active)<a.jobs and pending:
            index=next((i for i,g in enumerate(pending) if not g.get('software_renderer') or not softwareActive),None)
            if index is None:break
            game=pending.pop(index);key=game['id'];part=a.output/'parts'/key;part.parent.mkdir(exist_ok=True)
            log=(a.output/(key+'.runner.log')).open('w');command=[sys.executable,str(ROOT/'tools/run_background.py'),'--suite',str(a.suite.resolve()),'--only',key,'--matched-results',str(a.matched_results.resolve()),'--output',str(part),'--seconds',str(a.seconds),*native_arguments(times),'--fixed-time']
            proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);active.append((proc,game,part,log,time.monotonic()))
            if game.get('software_renderer'):softwareActive=True
            print('Started',key,flush=True)
        for item in list(active):
            proc,game,part,log,start=item
            if proc.poll() is None:
                if time.monotonic()-start<a.seconds+120:continue
                proc.kill();proc.wait()
            log.close();active.remove(item);key=game['id']
            if game.get('software_renderer'):softwareActive=False
            try:
                report=json.loads((part/'summary.json').read_text());result=report['results'][0]
                if proc.returncode!=0:result['passed']=False
                if (part/key).exists():shutil.copytree(part/key,a.output/key)
            except Exception as error:result={'id':key,'passed':False,'error':str(error),'checks':{}}
            result['validation_concurrency']=a.jobs;result['fps_measurement_context']='concurrent validation';result['original_result_directory']=str(part);results.append(result)
            print('Finished',key,'PASS' if result['passed'] else 'FAIL',f'{len(results)}/{len(wanted)}',result.get('error',''),flush=True)
        ordered=sorted(results,key=lambda r:next(i for i,g in enumerate(games) if g['id']==r['id']))
        report={'passed':len(ordered)==len(wanted) and all(r['passed'] for r in ordered),'tested_games':len(ordered),'planned_games':len(wanted),'mode':'showcase','seconds_per_game':a.seconds,'capture_at_seconds':times[0],'capture_times_seconds':times,'validation_context':context,'results':ordered}
        if len(ordered)!=lastWritten:
            (a.output/'verification.json').write_text(json.dumps(report,indent=2));(a.output/'summary.json').write_text(json.dumps(report,indent=2));lastWritten=len(ordered)
        time.sleep(.2)
    with (a.output/'summary.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['game','passed','frames','average_fps','screenshot_seconds','measurement_context'])
        for r in ordered:
            fps=r.get('fps',{});writer.writerow([r['id'],r['passed'],fps.get('frames_rendered'),fps.get('average_fps'),fps.get('capture_elapsed_seconds'),'concurrent validation'])
    canvas=Image.new('RGB',(1600,((len(ordered)+3)//4)*260+35),(18,22,28));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18);draw.text((8,3),'Concurrent correctness validation / FPS reflects concurrent load',font=font,fill=(230,220,170))
    for i,r in enumerate(ordered):
        x=(i%4)*400;y=(i//4)*260+35;draw.text((x+6,y+2),r['id']+' / '+('PASS' if r['passed'] else 'FAIL'),font=font,fill=(140,235,180) if r['passed'] else (255,120,100));path=a.output/r['id']/'capture.png'
        if path.exists():
            tile=ImageOps.contain(Image.open(path),(400,225));canvas.paste(tile,(x+(400-tile.width)//2,y+30+(225-tile.height)//2))
    canvas.save(a.output/'contact-sheet.jpg',quality=94)
    print('Completed',len(ordered),'timed validation runs:',report['passed'],flush=True)
    if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
