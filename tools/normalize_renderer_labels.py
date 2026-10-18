"""Mechanical display-name maintenance; identifiers, paths and vendor names stay put.

--apply records original Git blobs for naming-only review/publication. No builds,
games, inference or remote writes are performed by this tool.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPOS=('dlss5-everything-testing','dlss5-everything','dlss5-phoenix-addon',
       'dlss5-dosbox-enchanced','dlss5-phoenix-gallery')
PROTECTED=re.compile(r'```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`|https?://[^\s)<>"\']+|\[Phoenix\](?!\()')
STRINGS=re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\\r\n])*"|\'(?:\\.|[^\'\\\r\n])*\'')
VENDOR=re.compile(r"^(?:['’]s\s+(?:approach|early)|\s+(?:DLSS\b|GeForce\b|RTX\b|GPU\b|GPUs\b|hardware\b|driver\b|drivers\b|CUDA\b|NGX\b|SDK\b|Corporation\b|SR\b|FG\b|Frame Generation\b|Super Resolution\b|DLAA\b|graphics\b|adapter\b|adapters\b|Tensor\b|built\b|deserves\b|workgroup\b|Toolkit\b))",re.I)
VENDOR_CONTEXT=re.compile(r"^(?:['’]s\b|\s+(?:NVAPI\b|NGXCore\b|Streamline\b|Image Scaling\b|upscal\w*\b|presenter\b|status bits\b|describes\b|also\b|copyright\b|Vulkan\b|vendor\b|license\b|components\b|runtimes\b|executable code\b))",re.I)
BARE_UI={'PhoenixControlClient.cs','comparison_hud.h','comparison.h','shared_panel.h',
    'render_readme_benchmarks.py','render_vr_estimates.py','export_release_benchmarks.py','GameGallery.cs'}


def display(text):
    text=re.sub(r'\bNvidia\b','NVIDIA',text)
    text=re.sub(r'\bDLSS\s*5 Phoenix\b','Phoenix DLSS5',text)
    text=re.sub(r'\bDLSS\s*5 PHOENIX\b','PHOENIX DLSS5',text)
    text=re.sub(r'\b(Phoenix|NVIDIA) DLSS 5\b',r'\1 DLSS5',text)
    text=re.sub(r'\bNVIDIA (?:DLSS NR|NR)\b','NVIDIA DLSS5 NR',text)
    text=re.sub(r'\bPhoenix\b(?! DLSS5\b|[._][A-Za-z0-9_]|\\|-(?!(?:only|specific|based|compatible|powered)\b)|/[a-z]| (?:Link|Museum)\b)','Phoenix DLSS5',text)
    text=re.sub(r'\bPHOENIX\b(?! DLSS5\b|[_./\\-])','PHOENIX DLSS5',text)
    def nvidia(match):
        if VENDOR.match(text[match.end():]) or VENDOR_CONTEXT.match(text[match.end():]):return match.group()
        if re.search(r'(?:optimized |driver |vendor |GPU |from |by |of |with )$',text[max(0,match.start()-25):match.start()],re.I) and text[match.end():].startswith((')',',','.')):return match.group()
        if re.search(r'(?:unaffiliated with|endorsed by|independent of)\s*$',text[max(0,match.start()-35):match.start()],re.I):return match.group()
        return 'NVIDIA DLSS5'
    return re.sub(r'\bNVIDIA\b(?! DLSS5\b|[._][A-Za-z0-9_]|\\|-(?!(?:only|specific|based|compatible|powered)\b)|/[a-z])',nvidia,text)


def prose(text):
    output=[];previous=0
    for match in PROTECTED.finditer(text):
        output.extend((display(text[previous:match.start()]),match.group()))
        previous=match.end()
    output.append(display(text[previous:]))
    return ''.join(output)


def normalize(text,path):
    path=Path(path)
    if path.suffix.lower()=='.md':return prose(text)
    if path.suffix.lower() in ('.js','.html','.cjs') and 'dashboard' in path.as_posix():
        return display(text)
    def literal(match):
        value=match.group();quote=value[:3] if value.startswith(('"""',"'''")) else value[0];body=value[len(quote):-len(quote)]
        if body in ('Phoenix','NVIDIA') and path.name not in BARE_UI:
            line=text[text.rfind('\n',0,match.start())+1:text.find('\n',match.end()) if '\n' in text[match.end():] else len(text)]
            if not (path.name=='LanFrameView.cs' and 'Row(6,' in line or
                    path.name=='MainForm.Library.cs' and 'names.Replace' in line or
                    path.name=='MainActivity.java' and 'choice(' in line):return value
        return quote+prose(body)+quote
    return STRINGS.sub(literal,text)


def candidates(repo):
    names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode().split('\0')
    # Include maintained readmes even when an older source-only ignore excluded them.
    names+=['README.md','BUILDING.md','CHANGELOG.md','android/README.md',
            'tools/dashboard.py','tools/summarize_execution_sweep.py',
            'tools/run_execution_sweep.py']
    names += [p.relative_to(repo).as_posix() for p in (repo/'docs').rglob('*.md')
              if not any(x in p.relative_to(repo).parts for x in ('dashboard','screenshot-licenses'))]
    for name in sorted(set(filter(None,names))):
        p=Path(name)
        if any(part in p.parts for part in ('external','vendor','third_party','legacy','licenses','asset_licenses','bin','obj')):continue
        if p.name in ('AGENTS.md','LICENSE.md','THIRD_PARTY_NOTICES.md') or not (repo/p).is_file():continue
        if p.suffix.lower()=='.md' or p.suffix.lower() in ('.cs','.xaml','.cpp','.h','.java','.kt','.py','.js','.html','.cjs') and (
            name.startswith(('src/','source/','app/','android/','dashboard/','tests/')) or
            p.name in ('scene.cpp','render_readme_benchmarks.py','render_vr_estimates.py','export_release_benchmarks.py','dashboard.py','summarize_execution_sweep.py','run_execution_sweep.py') or
            name.startswith('tools/test_') and repo.name=='dlss5-phoenix-addon'):
            if name.startswith(('docs/dashboard/','dashboard/preview')) or p.name=='data.js':continue
            yield p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    receipt=ROOT/'state/renderer-naming-review.json'
    existing=json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else []
    originals={(item['repo'],item['path']):item for item in existing}
    changes=[]
    for name in REPOS:
        repo=ROOT.parent/name
        for relative in candidates(repo):
            path=repo/relative;original=path.read_bytes()
            try:text=original.decode('utf-8-sig')
            except UnicodeDecodeError:continue
            updated=normalize(text,relative)
            if updated==text:continue
            after=(b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b'')+updated.encode('utf-8')
            item=dict(repo=name,path=relative.as_posix())
            if args.apply:
                item['before']=originals.get((name,relative.as_posix()),{}).get('before') or subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=repo,input=original).decode().strip()
                path.write_bytes(after)
                item['after']=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=repo,input=after).decode().strip()
            changes.append(item)
    if args.apply:
        originals.update({(item['repo'],item['path']):item for item in changes})
        receipt.write_text(json.dumps(list(originals.values()),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(changed=len(changes),files=changes)))


if __name__=='__main__':main()
