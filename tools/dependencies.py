from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];VENDOR=ROOT/'vendor/fullbench'
def prepare(spec,arch,folder):
    files=[];dependency=spec.get('dependency');api=spec['application_api']
    def copy(source,name=None):
        name=name or source.name;dest=folder/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);files.append(name)
    if dependency=='angle':
        for name in ('libEGL.dll','libGLESv2.dll','d3dcompiler_47.dll')+ (('vulkan-1.dll',) if spec['render_transport']=='vulkan' else ()):copy(VENDOR/'angle'/arch/name)
        for name in ('LICENSE','LICENSES.chromium.html'):copy(VENDOR/'angle'/arch/name,'licenses/ANGLE-'+name)
    elif dependency and dependency.startswith('dgvoodoo'):
        base=VENDOR/'dgvoodoo'
        if dependency=='dgvoodoo-glide':copy(base/'3Dfx'/arch/{1:'Glide.dll',2:'Glide2x.dll',3:'Glide3x.dll'}[spec['glide_version']])
        else:
            names=['D3D9.dll'] if api=='dx9' else ['D3D8.dll'] if api=='dx8' else ['DDraw.dll','D3DImm.dll']
            for name in names:copy(base/'MS'/arch/name)
        # dgVoodoo 2.87's tiny API DLLs load their shared implementation from the CPL.
        copy(base/'dgVoodooCpl.exe')
        config=(base/'dgVoodoo.conf').read_text()
        import re
        for key,value in [('OutputAPI','d3d11_fl11_0'),('FullScreenMode','false'),('CaptureMouse','false'),('dgVoodooWatermark','false'),('ForceVerticalSync','false')]:config=re.sub(r'(?m)^'+key+r'\s*=.*$',key+' = '+value,config)
        (folder/'dgVoodoo.conf').write_text(config);files.append('dgVoodoo.conf')
    elif dependency=='dxvk':
        base=VENDOR/'dxvk/dxvk-3.1.1'/('x64' if arch=='x64' else 'x32')
        names={'dx8':['d3d8.dll','d3d9.dll'],'dx9':['d3d9.dll'],'dx10':['dxgi.dll','d3d10core.dll','d3d11.dll'],'dx10_1':['dxgi.dll','d3d11.dll'],'dx11':['dxgi.dll','d3d11.dll']}[api]
        for name in names:copy(base/name)
        copy(VENDOR/'DXVK-LICENSE','licenses/DXVK-LICENSE')
        (folder/'dxvk.conf').write_text('dxgi.enableHDR = False\ndxgi.syncInterval = 0\nd3d9.presentInterval = 0\ndxgi.maxFrameRate = 0\nd3d9.maxFrameRate = 0\n');files.append('dxvk.conf')
    if dependency:
        meta=json.loads((VENDOR/'dependencies.json').read_text());(folder/'runtime-provenance.json').write_text(json.dumps({'dependency':dependency,'application_api':api,'render_transport':spec['render_transport'],'packages':meta},indent=2));files.append('runtime-provenance.json')
    return {name:{'bytes':(folder/name).stat().st_size,'sha256':hashlib.sha256((folder/name).read_bytes()).hexdigest()} for name in files}
