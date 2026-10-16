"""Copy only declared fixture files, excluding wrapper logs/caches and prior installs."""
from pathlib import Path
import argparse,hashlib,json,shutil
from asset_paths import find_assets,point_assets
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('destination',type=Path);p.add_argument('--assets-source',type=Path);a=p.parse_args();source=a.source.resolve();dest=a.destination.resolve()
    if dest.exists():p.error('Choose a new staging directory; existing artifacts are retained')
    matrix=json.loads((source/'matrix.json').read_text());dest.mkdir(parents=True)
    for game in matrix['games']:
        original=source/game['install_directory'];folder=dest/game['install_directory'];folder.mkdir(parents=True)
        if digest(source/game['executable'])!=game['sha256']:raise RuntimeError('Executable changed: '+game['id'])
        owned={Path(game['executable']).name,'RUN.cmd','test-game.json'}|set(game.get('runtime_files',{}))
        for rel in owned:
            path=original/rel;target=folder/rel
            if not target.resolve().is_relative_to(folder):raise RuntimeError('Invalid fixture member')
            if rel in game.get('runtime_files',{}) and digest(path)!=game['runtime_files'][rel]['sha256']:raise RuntimeError('Seed runtime changed: '+rel)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        assets=a.assets_source.resolve() if a.assets_source else find_assets(original)
        if not (assets/'museum.bin').is_file():raise RuntimeError('Missing asset snapshot: '+str(assets))
        point_assets(dest,assets)
    shutil.copy2(source/'matrix.json',dest/'matrix.json');print('Prepared',len(matrix['games']),'clean fixture definitions:',dest,flush=True)
if __name__=='__main__':main()
