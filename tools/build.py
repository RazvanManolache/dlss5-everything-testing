from pathlib import Path
import argparse,hashlib,json,re,shutil,struct,subprocess,time,sys
from variants import VARIANTS,import_dlls
from dependencies import prepare
from asset_paths import point_assets
from build_dependencies import dependency,visual_studio_build
from pe_exports import exports

ROOT=Path(__file__).resolve().parents[1]
VS=visual_studio_build()
DEPS=dependency('vulkan_dependencies')
MATRIX=[('dx2',2,['x86'],'ddraw.lib dxguid.lib'),('dx3',3,['x86'],'ddraw.lib dxguid.lib'),('dx5',5,['x86'],'ddraw.lib dxguid.lib'),('dx6',6,['x86'],'ddraw.lib dxguid.lib'),('dx7',7,['x86'],'ddraw.lib dxguid.lib'),('dx8',8,['x86'],'d3d8.lib'),('dx9',9,['x86','x64'],'d3d9.lib d3dcompiler.lib'),('dx10',10,['x86','x64'],'d3d10.lib dxgi.lib d3dcompiler.lib'),('dx11',11,['x86','x64'],'d3d11.lib dxgi.lib d3dcompiler.lib'),('dx12',12,['x86','x64'],'d3d12.lib dxgi.lib d3dcompiler.lib'),('opengl',20,['x86','x64'],'opengl32.lib gdi32.lib'),('vulkan',30,['x86','x64'],'vulkan-1.lib')]
def digest(path):
    for attempt in range(20):
        try:return hashlib.sha256(path.read_bytes()).hexdigest()
        except PermissionError:
            if attempt==19:raise
            time.sleep(.5)

def run_batch(text,path):
    path.write_text('@echo off\n'+text+'\nexit /b %errorlevel%\n')
    p=subprocess.run(['cmd','/c',str(path)],cwd=path.parent,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    path.with_suffix('.log').write_bytes(p.stdout)
    if p.returncode:print(path.with_suffix('.log').read_text(errors='replace'));raise RuntimeError(f'Build failed: {path}')

def main():
    args=argparse.ArgumentParser();args.add_argument('--validate',action='store_true',help='Opt in to game runtime checks');args.add_argument('--only',nargs='*');args.add_argument('--expand',action='store_true');args.add_argument('--metadata-only',action='store_true');args.add_argument('--refresh-runtimes',action='store_true');args.add_argument('--inherit-existing',action='store_true');args.add_argument('--assets',action='store_true');args.add_argument('--destination',type=Path);args.add_argument('--shared-assets',action='store_true',help='Use the common snapshot by a relative path; no links');args.add_argument('--test-seconds',type=float,default=30);args.add_argument('--test-capture-at',action='append');args.add_argument('--jobs',type=int,choices=range(1,5),default=3);opts=args.parse_args()
    if opts.destination is None:
        if opts.metadata_only or opts.refresh_runtimes:args.error('Metadata changes require an explicit staging --destination')
        command=[sys.executable,str(ROOT/'tools/build_sets.py')]
        if opts.validate:command+=['--validate']
        if opts.only:command+=['--only',*opts.only]
        if opts.assets:command+=['--assets']
        command+=['--test-seconds',str(opts.test_seconds),'--jobs',str(opts.jobs)]
        for group in opts.test_capture_at or []:command+=['--test-capture-at',group]
        subprocess.run(command,check=True);return
    destination=opts.destination.resolve();
    from publish_sets import load_config
    configured=load_config(ROOT/'build-sets.json')
    for suite in (configured['clean_suite'],configured['reshade_suite']):
        if destination==suite or destination.is_relative_to(suite/'games'):
            args.error('Published sets are updated together. Omit --destination, or choose a separate staging folder.')
    if opts.refresh_runtimes and (not opts.metadata_only or destination==ROOT):raise RuntimeError('Runtime refresh requires --metadata-only in a separate staging directory')
    destination.mkdir(parents=True,exist_ok=True)
    if not (ROOT/'vendor/vulkan/vulkan.h').exists():
        shutil.copytree(DEPS/'headers/include/vulkan',ROOT/'vendor/vulkan',dirs_exist_ok=True)
        shutil.copytree(DEPS/'headers/include/vk_video',ROOT/'vendor/vk_video',dirs_exist_ok=True)
        shutil.copy2(DEPS/'headers/LICENSE.md',ROOT/'vendor/Vulkan-Headers-LICENSE.md')
    if opts.assets or not (ROOT/'build/scene/museum.bin').exists():subprocess.run(['python',str(ROOT/'tools/export_scene.py')],check=True)
    subprocess.run(['python',str(ROOT/'tools/generate_shaders.py')],check=True)
    subprocess.run(['python',str(ROOT/'tools/generate_fullbench_shaders.py')],check=True)
    if (ROOT/'src/museum.vert').exists():
        for stage in ['vert','frag']:
            subprocess.run([str(DEPS/'glslang/bin/glslang.exe'),'-V','--target-env','vulkan1.0',str(ROOT/f'src/museum.{stage}'),'-o',str(ROOT/f'build/museum.{stage}.spv')],check=True)
    if opts.shared_assets or opts.inherit_existing:point_assets(destination,ROOT/'build/scene')
    entries=[]
    definitions=MATRIX+([(name,v['backend'],v['arches'],v['libraries']) for name,v in VARIANTS.items()] if opts.expand else [])
    previous={g['id']:g for g in json.loads((ROOT/'matrix.json').read_text())['games']} if opts.inherit_existing else {}
    for name,number,arches,libs in definitions:
        for arch in arches:
            key=f'{name}-{arch}';game=destination/'games'/key;build=destination/'objects'/key
            spec=VARIANTS.get(name);baseName=spec['application_api'] if spec else name
            proxy=('d3d9.dll' if baseName=='dx9ex' else 'dxgi.dll' if spec['render_transport']=='d3d11' else 'Vulkan layer (no local proxy required)' if spec['render_transport']=='vulkan' else 'opengl32.dll' if number==21 else 'ddraw.dll' if number==40 else 'dxgi.dll') if spec else ('ddraw.dll' if number<8 else {'dx8':'d3d8.dll','dx9':'d3d9.dll','dx10':'dxgi.dll','dx11':'dxgi.dll','dx12':'dxgi.dll','opengl':'opengl32.dll','vulkan':'Vulkan layer (no local proxy required)'}[name])
            entry={'id':key,'api':name,'architecture':arch,'executable':f'games/{key}/Museum_{name}_{arch}.exe','install_directory':f'games/{key}','expected_proxy':proxy,'addon_extension':'.addon64' if arch=='x64' else '.addon32'}
            entry.update(default_mode='showcase',default_window='maximized',modes=['matched','showcase'],fixture_version=7,background_test={'seconds':25,'warmup_seconds':5,'measurement_seconds':20,'capture_at_seconds':25,'capture_times_seconds':[25],'multiple_screenshots':False,'width':1920,'height':1080,'vsync':False})
            entry['controls']={'freeze':'F / Space','movement':'WASD / arrows; Q down, E up; Shift faster','look':'right-drag / IJKL','orbit':'O; wheel or W/S zoom','animations':'T lighting, B camera motion','menu':'Museum controls','command_line':['--freeze','--orbit','--camera free|orbit','--animations on|off','--camera-motion on|off']}
            if spec:
                entry.update(spec);entry.update(fixture_version=7,import_dlls=import_dlls(spec))
                entry.pop('backend',None);entry.pop('libraries',None);entry.pop('arches',None)
                if spec.get('glide_version'):
                    entry['background_test'].update(width=856,height=480,native_legacy_mode=True)
            if number<8:
                dd,device={2:('IDirectDraw','IDirect3DDevice'),3:('IDirectDraw2','IDirect3DDevice'),5:('IDirectDraw2','IDirect3DDevice2'),6:('IDirectDraw4','IDirect3DDevice3'),7:('IDirectDraw7','IDirect3DDevice7')}[number]
                entry.update(directdraw_interface=dd,direct3d_device_interface=device,submission='execute_buffers' if number<=3 else 'DrawPrimitive')
            if opts.inherit_existing and key in previous and (not opts.only or key not in opts.only):
                entry=previous[key].copy();game.mkdir(parents=True,exist_ok=True)
                for file in [Path(entry['executable']).name,'RUN.cmd','test-game.json']:shutil.copy2(ROOT/entry['install_directory']/file,game/file)
                # Inherited games use the staging root relative asset path.
            if spec and (opts.metadata_only or opts.only and key not in opts.only) and (game/'test-game.json').exists():
                prior=json.loads((game/'test-game.json').read_text())
                if 'runtime_files' in prior:entry['runtime_files']=prior['runtime_files']
            if opts.only and key not in opts.only and (game/'test-game.json').exists():
                entry=json.loads((game/'test-game.json').read_text())
            entries.append(entry)
            if opts.metadata_only:
                if not (destination/entry['executable']).exists():raise RuntimeError('Missing executable for metadata update: '+key)
                if spec:
                    if opts.refresh_runtimes:entry['runtime_files']=prepare(spec,arch,game)
                    (game/'test-game.json').write_text(json.dumps(entry,indent=2))
                continue
            if opts.only and key not in opts.only:continue
            game.mkdir(parents=True,exist_ok=True);build.mkdir(parents=True,exist_ok=True)
            vcvars='vcvars64.bat' if arch=='x64' else 'vcvars32.bat';setup=f'call "{VS/vcvars}" >nul\nif errorlevel 1 exit /b 1\n'
            if number==8:
                # A native DX8 import library; no translation wrapper is bundled.
                (build/'d3d8.def').write_text('LIBRARY d3d8.dll\nEXPORTS\nDirect3DCreate8\n')
                setup+=f'lib /nologo /def:d3d8.def /machine:{arch} /out:d3d8.lib\nif errorlevel 1 exit /b 1\n'
            if number==30:
                source=dependency('vulkan_loader_definition')
                shutil.copy2(source,build/'vulkan.def')
                setup+=f'lib /nologo /def:vulkan.def /machine:{arch} /out:vulkan-1.lib\nif errorlevel 1 exit /b 1\n'
            if spec and number in (22,41):
                sources={'libEGL':ROOT/'vendor/fullbench/angle'/arch/'libEGL.dll','libGLESv2':ROOT/'vendor/fullbench/angle'/arch/'libGLESv2.dll'} if number==22 else {f'glide{spec['glide_version']}':ROOT/'vendor/fullbench/dgvoodoo/3Dfx'/arch/{1:'Glide.dll',2:'Glide2x.dll',3:'Glide3x.dll'}[spec['glide_version']]}
                for lib,source in sources.items():
                    (build/(lib+'.def')).write_text('LIBRARY '+source.name+'\nEXPORTS\n'+'\n'.join(exports(source))+'\n');setup+=f'lib /nologo /def:{lib}.def /machine:{arch} /out:{lib}.lib\nif errorlevel 1 exit /b 1\n'
            exe=game/f'Museum_{name}_{arch}.exe' 
            # Each link contains only the selected graphics API and a unique version resource.
            rc=f'''#include <windows.h>
1 VERSIONINFO
FILEVERSION 1,0,0,0
PRODUCTVERSION 1,0,0,0
FILEOS VOS_NT_WINDOWS32
FILETYPE VFT_APP
BEGIN
BLOCK "StringFileInfo"
BEGIN
BLOCK "040904B0"
BEGIN
VALUE "FileDescription", "Museum {name.upper()} {arch} Graphics Test\\0"
VALUE "ProductName", "DLSS Everything Testing Grounds\\0"
VALUE "OriginalFilename", "{exe.name}\\0"
END
END
BLOCK "VarFileInfo"
BEGIN
VALUE "Translation", 0x409, 1200
END
END
'''
            (build/'game.rc').write_text(rc)
            setup+='rc /nologo /fo game.res game.rc\nif errorlevel 1 exit /b 1\n'
            defines=' '.join('/D'+flag for flag in (spec['defines'].split() if spec else []))
            compile=f'cl {defines} /nologo /std:c++17 /O2 /W3 /EHsc /MT /DUNICODE /D_UNICODE /DBACKEND={number} /DAPI_NAME=\\"{name}\\" /I"{ROOT}/vendor" /c "{ROOT}/src/main.cpp" /Fo:game.obj\nif errorlevel 1 exit /b 1\n'
            run_batch(setup+compile,build/'compile.cmd')
            aliases=''
            if number==41:
                dll=next(iter(sources.values()))
                for symbol in exports(dll):
                    if symbol.startswith('_gr') and '@' in symbol:
                        functionName=symbol[1:].split('@')[0];sourceSymbol='__imp__'+symbol if arch=='x86' else '__imp_'+symbol;targetSymbol='__imp_'+symbol if arch=='x86' else '__imp_'+functionName
                        if arch=='x86':aliases+=f' /alternatename:__imp_{symbol}={sourceSymbol}'
                        elif functionName not in exports(dll):aliases+=f' /alternatename:{targetSymbol}={sourceSymbol}'
            if arch=='x86' and number in (8,22,30):
                run_batch(f'call "{VS/vcvars}" >nul\ndumpbin /symbols game.obj > symbols.txt',build/'symbols.cmd')
                symbols=(build/'symbols.txt').read_text(errors='replace')
                for sym in sorted(set(re.findall(r'((?:__imp_)?_\w+@\d+)',symbols))):
                    if number==30 and re.match(r'(?:__imp_)?_vk',sym) or number==8 and 'Direct3DCreate8' in sym or number==22 and re.match(r'(?:__imp_)?_(?:egl|gl)',sym):
                        aliases+=f' /alternatename:{sym}={sym.split("@")[0]}'
            (build/'link.rsp').write_text(f'/nologo /SUBSYSTEM:WINDOWS /LARGEADDRESSAWARE /INCREMENTAL:NO /OUT:"{exe}" game.obj game.res /LIBPATH:. {libs} user32.lib shell32.lib ole32.lib windowscodecs.lib{aliases}')
            run_batch(f'call "{VS/vcvars}" >nul\nlink.exe @link.rsp',build/'link.cmd')
            asset_folder=ROOT/'build/scene' if opts.shared_assets else game/'assets'
            if not opts.shared_assets:shutil.copytree(ROOT/'build/scene',asset_folder,dirs_exist_ok=True)
            if number==30:
                for stage in ['vert','frag']:shutil.copy2(ROOT/f'build/museum.{stage}.spv',asset_folder/f'museum.{stage}.spv')
            if spec:entry['runtime_files']=prepare(spec,arch,game)
            (game/'test-game.json').write_text(json.dumps(entry,indent=2))
            (game/'RUN.cmd').write_text(f'@echo off\ncd /d "%~dp0"\nstart "" "{exe.name}" %*\n')
            try:entry['sha256']=digest(exe)
            except (OSError,PermissionError) as error:entry['build_error']=str(error)
            print('Built',key,flush=True)
    for entry in entries:
        path=destination/entry['executable']
        if path.exists():
            try:entry['sha256']=digest(path)
            except OSError as error:entry['build_error']=str(error)
    (destination/'matrix.json').write_text(json.dumps({'schema':2,'fixture_version':7,'games':entries,'unsupported':[{'api':'dx8','architecture':'x64','reason':'Windows provides the native Direct3D 8 runtime only for x86.'}]},indent=2))

if __name__=='__main__':main()
