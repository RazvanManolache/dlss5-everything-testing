"""Review an allowlisted public tree without changing the user's branch or index.

No push is performed. --commit creates one commit on the selected public base,
not on a private experimental branch. Review the returned hash before pushing.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ALLOWED=('.gitignore','.gitattributes','README.md','Dashboard.cmd','src','tools','tests','docs','vendor','dos')
FORBIDDEN_ROOTS=('games/','clean/','runs/','state/','build/','shared-assets/','cases/','evidence/')
FORBIDDEN_EXTENSIONS={'.exe','.dll','.addon32','.addon64','.pdb','.obj','.zip','.7z','.log',
    '.safetensors','.onnx','.cubin','.pt','.pth','.bin'}
PRIVATE=re.compile(r'(?i)(?:\b[de]:[\\/]|c:[\\/]+users[\\/]|/home/[A-Za-z0-9_.-]+/|/Users/[A-Za-z0-9_.-]+/)')
SECRET=re.compile(r'(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')


def git(*args,env=None,input=None):
    result=subprocess.run(['git',*args],cwd=ROOT,env=env,input=input,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-3000:])
    return result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='origin/main')
    parser.add_argument('--commit',action='store_true')
    args=parser.parse_args()
    snapshot=ROOT/'docs/dashboard'
    manifest=json.loads((snapshot/'manifest.json').read_text(encoding='utf-8'))
    if manifest['records']!=445 or manifest['capture_records']!=351 or manifest['unique_images']!=88:
        raise ValueError('Unexpected published result counts; review the snapshot contract')
    expected=set(manifest['files'])|{'manifest.json'}
    if expected!={p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file()}:
        raise ValueError('Unexpected public snapshot members')
    for name,sha in manifest['files'].items():
        if hashlib.sha256((snapshot/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Snapshot hash mismatch: '+name)
    for name in ('index.html','app.js','styles.css','performance.js','favicon.svg'):
        if (snapshot/name).read_bytes()!=(ROOT/'dashboard'/name).read_bytes():
            raise ValueError('Published dashboard source is stale: '+name)
    base=git('rev-parse',args.base).decode().strip()
    with tempfile.TemporaryDirectory(prefix='public-index-') as temporary:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temporary)/'index'))
        git('read-tree',base,env=env)
        git('add','--all','--',*ALLOWED,env=env)
        # Publish the UI source, never the machine-specific live index/previews.
        git('add','--','dashboard/index.html','dashboard/app.js','dashboard/performance.js',
            'dashboard/styles.css','dashboard/favicon.svg',env=env)
        entries=git('ls-files','--stage','-z',env=env).decode().split('\0')
        files=[];new_bytes=0
        for entry in filter(None,entries):
            metadata,name=entry.split('\t',1);mode,sha,stage=metadata.split()
            suffix=Path(name).suffix.lower()
            if mode=='120000' or name.startswith(FORBIDDEN_ROOTS) or suffix in FORBIDDEN_EXTENSIONS:
                raise ValueError('Forbidden public member: '+name)
            blob=git('cat-file','blob',sha)
            if len(blob)>50*1024*1024:raise ValueError('Unexpected large public blob: '+name)
            if suffix in ('.png','.webp'):
                if not (name=='docs/dashboard-preview.png' or name.startswith('docs/dashboard/images/')):
                    raise ValueError('Unexpected image: '+name)
            else:
                text=blob.decode('utf-8',errors='replace')
                if name=='dos/museum.c':
                    # This is a declared DOS guest mount, not a Windows host path.
                    text=text.replace('D'+':/GALLERY.DAT','DOS_GUEST_ASSET')
                if PRIVATE.search(text) or SECRET.search(text):
                    raise ValueError('Private path or credential pattern in public member: '+name)
            if name.startswith('docs/dashboard/') and name.removeprefix('docs/dashboard/') in manifest['files']:
                if hashlib.sha256(blob).hexdigest()!=manifest['files'][name.removeprefix('docs/dashboard/')]:
                    raise ValueError('Git normalization changed a snapshot receipt: '+name)
            files.append(name);new_bytes+=len(blob)
        tree=git('write-tree',env=env).decode().strip()
        report=dict(base=base,tree=tree,files=len(files),tree_bytes=new_bytes,
            public_images=manifest['unique_images'],capture_records=manifest['capture_records'],
            records=manifest['records'],privacy_scan_passed=True,
            private_history_included=False,working_branch_or_index_changed=False)
        if args.commit:
            commit=git('commit-tree',tree,'-p',base,input=b'Publish API comparison study and deduplicated benchmark dashboard\n').decode().strip()
            report['commit']=commit
        print(json.dumps(report))
        (ROOT/'state/publication-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
