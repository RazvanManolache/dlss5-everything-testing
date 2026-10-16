"""Extract fresh installer targets without copying prior addon/proxy/config leftovers."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,re,shutil,zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('name',help='New case name, for example installer-v1');p.add_argument('--games',nargs='+',required=True,help='Explicit subset only; portable cases duplicate assets');p.add_argument('--destination',type=Path,default=ROOT/'cases');a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}',a.name) or a.name.endswith(('.', ' ')):p.error('Use a simple case name without directory separators or a trailing period/space')
    target=a.destination.resolve()/a.name
    if target.exists():p.error(f'Case already exists: {target}. Choose a fresh name; existing installs are never overwritten.')
    archive=ROOT/'pristine.zip';expected=(ROOT/'pristine.zip.sha256').read_text().split()[0]
    with archive.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    if actual!=expected:raise RuntimeError('Clean baseline archive checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        baseline=json.loads(z.read('baseline.json'));matrix=baseline['matrix'];games=matrix['games'];valid={g['id'] for g in games};selected=set(a.games or valid)
        if not selected<=valid:p.error('Unknown game(s): '+', '.join(sorted(selected-valid)))
        matrix['games']=[g for g in games if g['id'] in selected]
        common=sum(pin['bytes'] for name,pin in baseline['files'].items() if name.startswith('common/'))
        needed=common*len(selected)+sum(pin['bytes'] for name,pin in baseline['files'].items() if name.startswith('games/') and name.split('/')[1] in selected)
        probe=target.parent
        while not probe.exists():probe=probe.parent
        free=shutil.disk_usage(probe).free
        if needed+1024**3>free:p.error(f'Independent copies need {needed/1e9:.1f} GB; {free/1e9:.1f} GB is free. Select a subset with --games or use --destination on another drive.')
        target.mkdir(parents=True)
        for game in matrix['games']:
            key=game['id'];folder=target/'games'/key
            for name,pin in baseline['files'].items():
                prefix='common/' if name.startswith('common/') else f'games/{key}/'
                if not name.startswith(prefix):continue
                rel=PurePosixPath(name[len(prefix):]);dest=folder/str(rel)
                if rel.is_absolute() or '..' in rel.parts or not dest.resolve().is_relative_to(folder.resolve()):raise RuntimeError('Invalid baseline member')
                data=z.read(name)
                if len(data)!=pin['bytes'] or hashlib.sha256(data).hexdigest()!=pin['sha256']:raise RuntimeError('Baseline member checksum mismatch: '+name)
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            print(folder/game['executable'].split('/')[-1])
        (target/'matrix.json').write_text(json.dumps(matrix,indent=2))
        (target/'case.json').write_text(json.dumps({'name':a.name,'baseline_sha256':expected,'games':sorted(selected)},indent=2))
    print('Created',len(selected),'clean, independent installer target(s) in',target)

if __name__=='__main__':main()
