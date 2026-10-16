from pathlib import Path
import hashlib
def expected_imports(game,fallback):return game.get('import_dlls') or [fallback[game['api']]]
def inspect_variant(game,state,folder,allow_installed=False):
    checks={};details=state.get('renderer_details',{});api=game.get('application_api');modules=[Path(m).name.lower() for m in (state.get('render_loaded_modules') or state['loaded_modules'])]
    for rel,pin in ({} if allow_installed else game.get('runtime_files',{})).items():
        path=folder/rel;checks['seed_file_'+rel]=path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    if game.get('dependency') and not allow_installed:
        expected=game.get('import_dlls',[])
        if game.get('wrapper')=='dxvk':expected={'dx8':['d3d8.dll','d3d9.dll'],'dx9':['d3d9.dll'],'dx10':['dxgi.dll','d3d10core.dll','d3d11.dll'],'dx10_1':['dxgi.dll','d3d11.dll'],'dx11':['dxgi.dll','d3d11.dll']}[api]
        live={str(Path(m).resolve()).lower() for m in (state.get('render_loaded_modules') or state['loaded_modules'])}
        checks['seed_runtime_loaded']=all(str((folder/name).resolve()).lower() in live for name in expected)
    if api=='dx9ex':checks['device9ex_creation']=details.get('device_interface')=='IDirect3DDevice9Ex'
    if api=='dx10_1':checks['device10_1_creation']=details.get('creation')=='D3D10CreateDevice1' and details.get('feature_level')==0xA100
    if api=='opengl-core':checks['core_profile']=bool(details.get('profile_mask',0)&1) and details.get('requested_version')+' core'==game['profile']
    if api in ('gles2','gles3'):
        checks['egl_context']=details.get('context_api')=='EGL / ANGLE' and details.get('gles_requested')==int(api[-1])
        checks['angle_requested_backend']=game['render_transport'].lower() in details.get('renderer','').lower()
    if api=='directdraw-2d':checks['pure_2d_surface_path']=details.get('direct3d_device_created') is False and details.get('directdraw_version')==game['directdraw_version'] and details.get('surface_blt_calls',0)>0
    if api=='d3d11on12':checks['on12_wrapped_resources']=details.get('device_interface')=='ID3D11On12Device' and details.get('wrapped_resources')==2 and details.get('acquire_wrapped_calls')==state['frames_presented'] and details.get('release_wrapped_calls')==state['frames_presented']
    if api in ('glide1','glide2','glide3'):checks['glide_triangle_path']=details.get('glide_version')==int(api[-1]) and details.get('triangle_calls',0)>0
    if game.get('software_renderer'):checks['warp_device']=details.get('software_renderer') is True and 'microsoft' in state['gpu'].lower()
    if game.get('wrapper')=='dxvk' or (api or '').startswith('gles') and game['render_transport']=='vulkan':checks['vulkan_transport_loaded']='vulkan-1.dll' in modules
    if game.get('wrapper')=='dgvoodoo' or api in ('glide1','glide2','glide3'):checks['d3d11_transport_loaded']='d3d11.dll' in modules
    return checks
