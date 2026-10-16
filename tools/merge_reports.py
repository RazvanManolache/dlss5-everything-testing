"""Merge passing, current executable checks while retaining original evidence."""
from pathlib import Path
import argparse,hashlib,json,shutil
def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',type=Path,required=True);p.add_argument('--only',nargs='+');p.add_argument('--inputs',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Choose a fresh evidence directory')
    games=json.loads((a.suite/'matrix.json').read_text())['games'];latest={};mode=None
    for directory in a.inputs:
        report=json.loads((directory/'verification.json').read_text())
        if mode is not None and mode!=report['mode']:p.error('Cannot merge different modes')
        mode=report['mode']
        for result in report['results']:latest[result['id']]=(directory,result)
    results=[];a.output.mkdir(parents=True)
    for game in games:
        if a.only and game['id'] not in a.only:continue
        directory,result=latest[game['id']];result=dict(result)
        if not result['passed'] or hashlib.sha256((a.suite/game['executable']).read_bytes()).hexdigest()!=result['sha256']:raise RuntimeError('Missing passing current evidence: '+game['id'])
        result['original_evidence_directory']=str(directory.resolve());results.append(result);dest=a.output/game['id'];dest.mkdir()
        for name in ('capture.png','status.json','renderer.json','device-caps.json','fps.json','fps.csv'):
            if (directory/game['id']/name).exists():shutil.copy2(directory/game['id']/name,dest/name)
    report={'passed':bool(results) and all(r['passed'] for r in results),'tested_games':len(results),'mode':mode,'results':results};(a.output/'verification.json').write_text(json.dumps(report,indent=2));print('Merged',len(results),'passing current',mode,'runs',flush=True)
if __name__=='__main__':main()
