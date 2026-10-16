"""Save only the current compact clean baseline for installer cases."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
from asset_paths import find_assets

ROOT=Path(__file__).resolve().parents[1]

def file_digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def replace_from(source):
    """Seal a clean staging build; retain only the current release."""
    source=source.resolve()
    if source==ROOT:raise RuntimeError('Replacement must use a separate clean staging directory')
    matrix=json.loads((source/'matrix.json').read_text())
    if not matrix['games']:raise RuntimeError('Empty fixture matrix')
    records={};mapping={};shared=None
    for game in matrix['games']:
        folder=source/game['install_directory'];exe=source/game['executable']
        if file_digest(exe)!=game['sha256']:raise RuntimeError('Executable changed: '+game['id'])
        assets=find_assets(folder)
        if shared is None:shared=assets
        if assets!=shared:raise RuntimeError('Replacement staging must use one shared asset snapshot')
        allowed={exe.name,'RUN.cmd','test-game.json'}|set(game.get('runtime_files',{}))
        actual=set()
        for child in folder.iterdir():
            if child.name=='assets':continue
            if child.is_file():actual.add(child.name)
            elif child.is_dir():actual.update(p.relative_to(folder).as_posix() for p in child.rglob('*') if p.is_file())
        if actual!=allowed:raise RuntimeError('Unexpected or missing staging files: '+str(folder)+' '+str(actual^allowed))
        for rel,pin in game.get('runtime_files',{}).items():
            path=folder/rel
            if path.stat().st_size!=pin['bytes'] or file_digest(path)!=pin['sha256']:raise RuntimeError('Seed runtime differs: '+str(path))
        for name in sorted(allowed):
            mapping[f"games/{game['id']}/{name}"]=folder/name
    for path in sorted(shared.rglob('*')):
        if path.is_file():
            if path.suffix.lower() in ('.exe','.dll','.ini','.addon32','.addon64'):raise RuntimeError('Unexpected asset: '+str(path))
            mapping['common/assets/'+path.relative_to(shared).as_posix()]=path
    for member,path in mapping.items():records[member]={'sha256':file_digest(path),'bytes':path.stat().st_size}
    target=ROOT/'pristine.zip';previous=file_digest(target)
    if previous!=(ROOT/'pristine.zip.sha256').read_text().split()[0]:raise RuntimeError('Previous baseline checksum mismatch')
    manifest={'schema':2,'files':records,'matrix':matrix,'previous_baseline_sha256':previous}
    temporary=ROOT/'pristine.pending.zip'
    if temporary.exists():raise RuntimeError('A pending baseline already exists; inspect it before sealing again')
    try:
        with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
            for member,path in mapping.items():z.write(path,member)
            z.writestr('baseline.json',json.dumps(manifest,indent=2))
        temporary.replace(target)
    finally:
        if temporary.exists():temporary.unlink()
    (ROOT/'baseline.json').write_text(json.dumps(manifest,indent=2))
    digest=file_digest(target);(ROOT/'pristine.zip.sha256').write_text(digest+'  pristine.zip\n')
    print('Saved',target,'bytes',target.stat().st_size,'SHA256',digest,flush=True)

def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group();group.add_argument('--extend',action='store_true',help='Add new game IDs to the current baseline without keeping an archive history');group.add_argument('--replace-from',type=Path,help='Seal a clean staging build and atomically replace the current archive');args=parser.parse_args()
    if args.replace_from:
        replace_from(args.replace_from);return
    target=ROOT/'pristine.zip'
    if target.exists() and not args.extend:raise RuntimeError('pristine.zip already exists. Use --extend to add new game IDs while preserving the old baseline.')
    if args.extend and not target.exists():raise RuntimeError('--extend requires an existing baseline')
    matrix=json.loads((ROOT/'matrix.json').read_text());records={};mapping={};old_ids=set();old_data={};previous=None
    if args.extend:
        previous=hashlib.sha256(target.read_bytes()).hexdigest()
        if previous!=(ROOT/'pristine.zip.sha256').read_text().split()[0]:raise RuntimeError('Previous baseline checksum mismatch')
        with zipfile.ZipFile(target) as z:
            original=json.loads(z.read('baseline.json'));records=original['files'];old_ids={g['id'] for g in original['matrix']['games']}
            current={g['id']:g for g in matrix['games']}
            for g in original['matrix']['games']:
                if g['id'] not in current or current[g['id']]['sha256']!=g['sha256']:raise RuntimeError('Existing fixture identity changed: '+g['id'])
            for member,pin in records.items():
                data=z.read(member)
                if len(data)!=pin['bytes'] or hashlib.sha256(data).hexdigest()!=pin['sha256']:raise RuntimeError('Previous baseline file checksum mismatch: '+member)
                old_data[member]=data
    for game in matrix['games']:
        folder=ROOT/game['install_directory'];key=game['id']
        # Existing game folders may have active installs. Read their clean files
        # exclusively from the previous sealed archive, never from those folders.
        if key in old_ids:continue
        for path in sorted(folder.rglob('*')):
            if not path.is_file():continue
            rel=path.relative_to(folder).as_posix()
            if rel.startswith('run/'):continue
            if path.suffix.lower() in ('.dll','.addon32','.addon64','.ini'):raise RuntimeError(f'Baseline already contains installer files: {path}')
            shared=rel.startswith('assets/') and not path.name.endswith('.spv')
            member=('common/'+rel) if shared else ('games/'+key+'/'+rel)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if member in records and records[member]['sha256']!=digest:raise RuntimeError(f'Scene differs between games: {member}')
            records[member]={'sha256':digest,'bytes':path.stat().st_size};mapping[member]=path
    if args.extend and len(matrix['games'])==len(old_ids):raise RuntimeError('No new game IDs to add')
    manifest={'schema':1,'files':records,'matrix':matrix}
    if previous:manifest['previous_baseline_sha256']=previous
    temporary=ROOT/'pristine.pending.zip'
    if temporary.exists():raise RuntimeError('A pending baseline already exists; inspect it before sealing again')
    try:
        with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for member,data in old_data.items():
                if member not in mapping:z.writestr(member,data)
            for member,path in mapping.items():z.write(path,member)
            z.writestr('baseline.json',json.dumps(manifest,indent=2))
        temporary.replace(target)
    finally:
        if temporary.exists():temporary.unlink()
    (ROOT/'baseline.json').write_text(json.dumps(manifest,indent=2))
    digest=hashlib.sha256(target.read_bytes()).hexdigest();(ROOT/'pristine.zip.sha256').write_text(digest+'  pristine.zip\n')
    print('Saved',target,'bytes',target.stat().st_size,'SHA256',digest)

if __name__=='__main__':main()
