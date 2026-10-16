"""Collect current, hash-matched native checks for both visual profiles."""
from pathlib import Path
import argparse,hashlib,json,shutil
from PIL import Image,ImageDraw,ImageFont,ImageOps

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',type=Path,required=True);p.add_argument('--matched',type=Path,nargs='+',required=True);p.add_argument('--showcase',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    matrix=json.loads((a.suite/'matrix.json').read_text());a.output.mkdir(parents=True,exist_ok=True);results=[]
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
    for mode in ('matched','showcase'):
        latest={}
        for directory in getattr(a,mode):
            report=json.loads((directory/'verification.json').read_text())
            if report['mode']!=mode:raise RuntimeError('Wrong mode report')
            for result in report['results']:latest[result['id']]=(directory,result)
        canvas=Image.new('RGB',(1920,((len(matrix['games'])+3)//4)*226),(18,22,28));draw=ImageDraw.Draw(canvas)
        for i,game in enumerate(matrix['games']):
            directory,result=latest[game['id']];result=dict(result);result['mode']=mode;result['source_evidence']=str(directory.resolve())
            current=hashlib.sha256((a.suite/game['executable']).read_bytes()).hexdigest()
            required='matching_scene_view' if mode=='matched' else 'showcase_changes_rendered_pixels'
            if result['sha256']!=current or current!=game['sha256'] or not result['passed'] or not result['checks'].get(required):raise RuntimeError('Missing current checks: '+game['id']+' '+mode)
            dest=a.output/mode/game['id'];dest.mkdir(parents=True,exist_ok=True)
            for name in ('capture.png','status.json','renderer.json','device-caps.json','fps.json','fps.csv'):
                src=directory/game['id']/name
                if src.exists():shutil.copy2(src,dest/name)
            x=(i%4)*480;y=(i//4)*226;draw.text((x+8,y+2),game['id']+' / '+mode,font=font,fill=(140,235,180))
            tile=ImageOps.contain(Image.open(dest/'capture.png'),(480,190));canvas.paste(tile,(x+(480-tile.width)//2,y+33+(190-tile.height)//2));results.append(result)
        canvas.save(a.output/(mode+'-contact-sheet.jpg'),quality=94)
    preview=Image.new('RGB',(1280,6*290),(18,22,28));draw=ImageDraw.Draw(preview)
    for i,key in enumerate(('dx2-x86','dx8-x86','dx9-x64','dx11-x64','opengl-x64','vulkan-x64')):
        for j,mode in enumerate(('matched','showcase')):
            x=j*640;y=i*290;draw.text((x+8,y+3),key+' / '+mode,font=font,fill=(140,235,180));tile=ImageOps.contain(Image.open(a.output/mode/key/'capture.png'),(640,252));preview.paste(tile,(x+(640-tile.width)//2,y+33+(252-tile.height)//2))
    preview.save(a.output/'modes-preview.jpg',quality=94)
    report={'passed':True,'tested_games':len(matrix['games']),'native_runs':len(results),'frame_counts':'See frames_presented in each runtime record','validation_scope':'Native API, architecture, highest-detail meshes, requested window visibility, completed frames, fresh GPU readback, matched-view parity and distinct showcase output. Addon installation/inference is separate.','results':results}
    (a.output/'verification.json').write_text(json.dumps(report,indent=2));print('PASS',len(results),'current native mode runs',flush=True)

if __name__=='__main__':main()
