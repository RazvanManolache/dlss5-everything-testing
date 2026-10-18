"""Check saved benchmark evidence; integrity success does not mean all routes work."""
import argparse
import collections
import json
import math
from pathlib import Path

from PIL import Image
from run_backends import ROOT, desired_extent, digest, read, write
from run_execution_sweep import VARIANTS


OUTPUT=ROOT/'runs/latest-x64-backends'
FORBIDDEN=('average_fps','neural_fps','game_fps','measurement','samples','elapsed_seconds')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--include-dos',action='store_true')
    args=parser.parse_args()
    hashes=read(args.candidate/'FILES_SHA256.json')
    problems=[];counts=collections.Counter();images=[]
    def check(value,message):
        if not value:problems.append(message)
    for game in read(ROOT/'matrix.json')['games']:
        cases=[('native','baseline','native')]
        cases+=([(b,'auto',b) for b in ('nvidia','phoenix')] if game['architecture']=='x64' else
            [(b,v,b+'-'+v) for v in VARIANTS for b in ('nvidia','phoenix')])
        check(digest(ROOT/'clean'/game['executable'])==game['sha256'],game['id']+': changed clean executable')
        for backend,variant,name in cases:
            folder=OUTPUT/game['id']/name;r=read(folder/'result.json');key=game['id']+'/'+name
            applicable=not (backend=='nvidia' and variant=='x86-driver')
            check(r.get('id')==game['id'] and r.get('backend')==backend,key+': missing or wrong result identity')
            check(r.get('execution_variant')==variant,key+': missing or wrong variant')
            check(r.get('applicable',True)==applicable,key+': incorrect applicability')
            if not applicable or r.get('passed') is False:
                counts['failed' if applicable else 'not_applicable']+=1
                check(bool(r.get('error')),key+': missing failure reason')
                check(not any(k in r for k in FORBIDDEN),key+': failed/unavailable result contains scores')
                check(not any(folder.glob('*.png')) and not (folder/'fps.json').exists() and
                    not (folder/'fps.csv').exists() and not (folder/'captures.json').exists(),key+': failed/unavailable result retains images or FPS')
                continue
            if r.get('passed') is not True:
                counts['missing_or_pending']+=1;problems.append(key+': not completed');continue
            counts['passed']+=1
            check(r.get('executable_sha256')==game['sha256'],key+': wrong executable build')
            check((r.get('width'),r.get('height'))==desired_extent(game),key+': wrong resolution')
            check(r.get('warmup_seconds')==5 and r.get('requested_seconds')==20 and r.get('vsync') is False,key+': wrong timing/presentation profile')
            window=r.get('measurement') or {}
            # Software renderers can take several seconds for one frame. Their
            # window closes on a frame boundary, never by inventing a partial frame.
            fixture_window=read(folder/'fps.json').get('game_measurement') or window
            tolerance=max(0,fixture_window.get('maximum_frame_seconds',0))+.5
            check(window.get('complete') is True and 19.9<=r.get('elapsed_seconds',0)<=20+tolerance,key+': incomplete measured window')
            captures=read(folder/'captures.json').get('captures') or []
            check(len(captures)==1 and len(list(folder.glob('*.png')))==1,key+': not exactly one image')
            if len(captures)==1:
                path=folder/captures[0]['png']
                check(path.is_file(),key+': missing PNG')
                if path.is_file():
                    with Image.open(path) as image:check(image.size==desired_extent(game),key+': wrong PNG dimensions')
                    images.append(path.relative_to(ROOT).as_posix())
                check(captures[0].get('execution_variant')==variant,key+': unlabelled image')
            if backend=='native':continue
            addon='Phoenix.addon32' if game['architecture']=='x86' else 'Phoenix.addon64'
            check(r.get('addon_sha256')==hashes.get(addon),key+': stale addon build')
            if game['architecture']=='x86':
                check(r.get('execution_runtime_sha256')==hashes.get('PhoenixRuntime/wow64/bootstrap.json'),key+': stale optional runtime')
                check(r.get('execution_mode')==VARIANTS[variant][2],key+': wrong observed execution route')
            rate=r.get('neural_fps')
            check(isinstance(rate,(int,float)) and not isinstance(rate,bool) and math.isfinite(rate) and rate>0,key+': invalid processed FPS')
            check(r.get('average_fps')==rate,key+': average FPS is not fresh-output FPS')
            proc=r.get('processing') or {}
            settings=proc.get('applied_settings') or {}
            check(settings.get('Backend')==(1 if backend=='nvidia' else 3) and settings.get('Comparison')==0 and
                settings.get('NeuralUplift') is True and settings.get('Intensity')==1 and settings.get('ResolutionMode')==0,
                key+': enhancement/comparison controls changed')
            if backend=='phoenix':
                check(settings.get('TransformerBlocks')==8 and settings.get('Experimental') is False and
                    settings.get('AutomaticBudget') is False and settings.get('RefinementPasses')==1 and
                    all(settings.get(f'Block{i}Repeats')==1 for i in range(1,9)),key+': unequal neural workload')
            check(proc.get('inference_pid')==(proc.get('helper_pid') if r.get('execution_mode')=='helper' else r.get('fixture_pid')),key+': incorrect inference PID')
            if backend=='nvidia':
                nv=proc.get('nvidia') or {}
                check(nv.get('ready') is True and nv.get('evaluates',0)>0,key+': no verified NVIDIA evaluations')
            check(all(v.get('central_mae',0)>.25 and v.get('changed_fraction_gt2',0)>.01 for v in r.get('pixel_comparison',[])) and
                bool(r.get('pixel_comparison')),key+': missing enhanced-pixel evidence')
    if args.include_dos:
        for backend in ('native','nvidia','phoenix'):
            folder=OUTPUT/'dos-vga'/backend;r=read(folder/'result.json');key='dos-vga/'+backend
            check(r.get('passed') in (True,False),key+': missing DOS result')
            if r.get('passed'):
                counts['dos_passed']+=1
                check(len(read(folder/'captures.json').get('captures') or [])==1,key+': not exactly one DOS image')
            else:
                counts['dos_failed']+=1
                check(not any(folder.glob('*.png')) and not any(k in r for k in FORBIDDEN),key+': failed DOS result retains scores/images')
    check(len(images)==len(set(images)),'Capture paths collide across cases')
    report=dict(results_integrity_passed=not problems,counts=dict(counts),unique_windows_captures=len(images),
        gpu_used=False,fixtures_launched=False,problems=problems,
        note='Integrity validation checks evidence completeness and identity. Failed routes remain failures; this does not certify game compatibility or equal visual quality.')
    write(OUTPUT/'execution-integrity.json',report)
    print(json.dumps(report))
    raise SystemExit(0 if not problems else 1)


if __name__=='__main__':main()
