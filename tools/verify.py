"""Run real windows on the GPU, inspect native imports/modules, and compare captures."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,struct,subprocess,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont

from fixture_checks import expected_imports,inspect_variant
from storage_policy import latest_output

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={'dx2':'ddraw.dll','dx3':'ddraw.dll','dx5':'ddraw.dll','dx6':'ddraw.dll','dx7':'ddraw.dll','dx8':'d3d8.dll','dx9':'d3d9.dll','dx10':'d3d10.dll','dx11':'d3d11.dll','dx12':'d3d12.dll','opengl':'opengl32.dll','vulkan':'vulkan-1.dll'}

def pe_info(path):
    b=path.read_bytes();pe=struct.unpack_from('<I',b,60)[0];machine,sections,_,_,_,size,_=struct.unpack_from('<HHIIIHH',b,pe+4);opt=pe+24
    magic=struct.unpack_from('<H',b,opt)[0];dd=opt+(112 if magic==0x20b else 96)
    imp=struct.unpack_from('<I',b,dd+8)[0];table=opt+size
    def offset(rva):
        for i in range(sections):
            at=table+i*40;vs,va,rawsz,raw=struct.unpack_from('<4I',b,at+8)
            if va<=rva<va+max(vs,rawsz):return raw+rva-va
        raise ValueError(f'Unmapped RVA {rva}')
    imports=[]
    if imp:
        at=offset(imp)
        while any(b[at:at+20]):
            name=offset(struct.unpack_from('<I',b,at+12)[0]);imports.append(b[name:b.index(0,name)].decode().lower());at+=20
    return {'architecture':{0x14c:'x86',0x8664:'x64'}.get(machine,hex(machine)),'imports':imports}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='*');parser.add_argument('--allow-installed',action='store_true');parser.add_argument('--suite',type=Path,default=ROOT);parser.add_argument('--frames',type=int,default=90);parser.add_argument('--output',type=Path,default=None);parser.add_argument('--reference',type=Path);parser.add_argument('--mode',choices=['matched','showcase'],default='matched');parser.add_argument('--matched-results',type=Path);parser.add_argument('--windowed',action='store_true');parser.add_argument('--background',action='store_true');parser.add_argument('--room',action='store_true');args=parser.parse_args()
    if args.frames<30:parser.error('--frames must be at least 30 so a fresh capture is produced')
    args.output=latest_output(args.output,'latest-verify')
    args.output.mkdir(parents=True,exist_ok=True);games=json.loads((args.suite/'matrix.json').read_text())['games'];results=[]
    if args.only and not set(args.only)<={g['id'] for g in games}:parser.error('Unknown game requested')
    for game in games:
        key=game['id']
        if args.only and key not in args.only:continue
        exe=args.suite.resolve()/game['executable'];out=args.output/key;out.mkdir(parents=True,exist_ok=True)
        # Fresh evidence directories prevent a stale image/status from passing a failed run.
        if any(out.iterdir()):
            prior=out/'history'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');prior.mkdir(parents=True)
            for p in list(out.iterdir()):
                if p.is_file():p.rename(prior/p.name)
        result={'id':key,'passed':False,'checks':{},'executable':str(exe)};start=time.perf_counter()
        try:
            info=pe_info(exe);result.update(info);result['sha256']=hashlib.sha256(exe.read_bytes()).hexdigest()
            result['checks']['correct_architecture']=info['architecture']==game['architecture'];result['checks']['native_api_import']=all(dll in info['imports'] for dll in expected_imports(game,EXPECTED))
            command=[str(exe),'--frames',str(args.frames),'--capture-frame','30','--fixed-time','--output',str(out.resolve())]
            if game.get('fixture_version',1)>=2:command+=['--mode',args.mode]
            if args.windowed:command+=['--windowed']
            if args.background:command+=['--background']
            if args.room:command+=['--room']
            env=os.environ.copy();env.update(DXVK_LOG_PATH=str(out.resolve()),DXVK_STATE_CACHE_PATH=str(out.resolve()),DXVK_SHADER_CACHE_PATH=str(out.resolve()))
            proc=subprocess.run(command,env=env,timeout=240 if game.get('software_renderer') else 90);result['exit_code']=proc.returncode
            state=json.loads((out/'status.json').read_text());result['runtime']=state;result['checks'].update(inspect_variant(game,state,exe.parent,args.allow_installed))
            if game.get('fixture_version',1)>=2:
                result['checks']['correct_mode']=state['mode']==args.mode
                result['checks']['starts_maximized']=state['maximized']==(not (args.windowed or args.background)) or args.background and state.get('background_isolated',False)
                result['checks']['full_detail_mesh']=state['triangles']>=432749
                if args.background:result['checks']['hidden_window']=state['background'] and (not state['window_visible'] or state.get('background_isolated',False))
            result['checks']['completed']=proc.returncode==0 and state['state']=='complete' and state['frames_presented']==args.frames
            modules=[Path(p).name.lower() for p in (state.get('render_loaded_modules') or state['loaded_modules'])];result['checks']['native_runtime_loaded']=all(dll in modules for dll in expected_imports(game,EXPECTED))
            if 'direct3d_device_interface' in game:
                detail=json.loads((out/'renderer.json').read_text());result['renderer']=detail
                result['checks']['correct_directdraw_interface']=detail['directdraw_interface']==game['directdraw_interface']
                result['checks']['correct_direct3d_interface']=detail['direct3d_device_interface']==game['direct3d_device_interface']
                counter='execute_buffer_calls' if game['submission']=='execute_buffers' else 'draw_primitive_calls'
                result['checks']['native_triangle_submission']=detail[counter]>0 and detail['triangles_submitted']>0 and detail['texture_count']==24
                result['checks']['legacy_3d_runtime_loaded']=('d3d11.dll' if game.get('wrapper')=='dgvoodoo' else 'd3dim700.dll' if game['api']=='dx7' else 'd3dim.dll') in modules
            im=Image.open(out/'capture.ppm').convert('RGB');im.save(out/'capture.png');a=np.asarray(im);result['image_stddev']=float(a.std());result['checks']['nonblank_capture']=float(a.std())>15
            result['checks']['correct_capture_dimensions']=im.size==(state['width'],state['height'])
            result['passed']=all(result['checks'].values())
        except Exception as e:result['error']=str(e)
        result['wall_seconds']=round(time.perf_counter()-start,3);results.append(result);print(key,'PASS' if result['passed'] else 'FAIL',result.get('error',result['checks']),flush=True)
        (args.output/'verification.json').write_text(json.dumps({'passed':all(r['passed'] for r in results),'results':results},indent=2))
    reference=args.reference or args.output/'dx11-x64/capture.png'
    if args.mode=='matched' and reference.exists():
        ref=np.asarray(Image.open(reference)).astype(float)
        for result in results:
            path=args.output/result['id']/'capture.png'
            if path.exists():
                image=Image.open(path).resize((ref.shape[1],ref.shape[0]),Image.Resampling.LANCZOS);a=np.asarray(image).astype(float);result['mean_absolute_difference_vs_dx11_x64']=float(np.abs(a-ref).mean())
                result['checks']['matching_scene_view']=result['mean_absolute_difference_vs_dx11_x64']<next(g for g in games if g['id']==result['id']).get('matched_tolerance',3.0)
                result['passed']=all(result['checks'].values())
    if args.mode=='showcase' and args.matched_results:
        for result in results:
            current=args.output/result['id']/'capture.png';matched=args.matched_results/result['id']/'capture.png'
            if current.exists() and matched.exists():
                im=Image.open(current);prior=Image.open(matched).resize(im.size,Image.Resampling.LANCZOS)
                difference=float(np.abs(np.asarray(im).astype(float)-np.asarray(prior).astype(float)).mean())
                result['mean_absolute_difference_from_matched']=difference
                result['checks']['showcase_changes_rendered_pixels']=difference>1.0
                result['passed']=all(result['checks'].values())
    canvas=Image.new('RGB',(4*384,((len(results)+3)//4)*248),(18,22,28));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
    for i,result in enumerate(results):
        x=(i%4)*384;y=(i//4)*248;path=args.output/result['id']/'capture.png'
        draw.text((x+8,y+6),result['id']+(' - PASS' if result['passed'] else ' - FAIL'),font=font,fill=(130,235,175) if result['passed'] else (255,120,110))
        if path.exists():canvas.paste(Image.open(path).resize((384,216)),(x,y+30))
    canvas.save(args.output/'contact-sheet.jpg',quality=94)
    report={'passed':len(results)>0 and all(r['passed'] for r in results),'tested_games':len(results),'mode':args.mode,'view':'room' if args.room else 'face','validation_scope':'Native renderer startup, imports, architecture, presented frames, loaded runtime and pre-Present GPU readbacks. Installer/addon/inference validation must be run separately.','results':results}
    (args.output/'verification.json').write_text(json.dumps(report,indent=2))
    print('FINAL',args.mode,'PASS' if report['passed'] else 'FAIL',len(results),'games',flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
