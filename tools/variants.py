"""Compile-time fixture definitions; no executable can switch graphics APIs."""
VARIANTS={}
def add(name,backend,libs,defines='',arches=('x86','x64'),application=None,transport=None,**extra):
    VARIANTS[name]={'backend':backend,'libraries':libs,'defines':defines,'arches':list(arches),'application_api':application or name,'render_transport':transport or name,**extra}

add('dx9ex',9,'d3d9.lib d3dcompiler.lib','USE_DX9EX',application='dx9ex',transport='dx9')
add('dx10_1',10,'d3d10_1.lib dxgi.lib d3dcompiler.lib','USE_DX10_1',transport='dx10_1')
for major,minor in [(3,3),(4,6)]:add(f'glcore{major}{minor}',21,'opengl32.lib gdi32.lib',f'GL_CORE_MAJOR={major} GL_CORE_MINOR={minor}',application='opengl-core',transport='opengl',profile=f'{major}.{minor} core')
for version in (2,3):
    for driver in ('d3d11','vulkan'):add(f'gles{version}_angle_{driver}',22,'libEGL.lib libGLESv2.lib gdi32.lib',f'USE_EGL GLES_VERSION={version} ANGLE_{driver.upper()}',application=f'gles{version}',transport=driver,dependency='angle')
for version in (1,2,4,7):add(f'ddraw{version}_2d',40,'ddraw.lib dxguid.lib',f'LEGACY_MATERIALS DD_VERSION={version}',application='directdraw-2d',transport='directdraw',directdraw_version=version)
for version in (1,2,3):add(f'glide{version}',41,f'glide{version}.lib',f'LEGACY_MATERIALS ISOLATE_BACKGROUND GLIDE_VERSION={version}',application=f'glide{version}',transport='d3d11',dependency='dgvoodoo-glide',glide_version=version,matched_tolerance=15.0)
add('d3d11on12',11,'d3d11.lib d3d12.lib dxgi.lib d3dcompiler.lib','USE_D3D11ON12',application='d3d11on12',transport='d3d12')
for api,backend,libs,flags in [('dx10',10,'d3d10.lib dxgi.lib d3dcompiler.lib',''),('dx10_1',10,'d3d10_1.lib dxgi.lib d3dcompiler.lib','USE_DX10_1'),('dx11',11,'d3d11.lib dxgi.lib d3dcompiler.lib',''),('dx12',12,'d3d12.lib dxgi.lib d3dcompiler.lib',''),('d3d11on12',11,'d3d11.lib d3d12.lib dxgi.lib d3dcompiler.lib','USE_D3D11ON12')]:
    add('warp_'+api,backend,libs,flags+' USE_WARP',application=api,transport=api,software_renderer=True)
for api,backend,libs in [('dx2',2,'ddraw.lib dxguid.lib'),('dx3',3,'ddraw.lib dxguid.lib'),('dx5',5,'ddraw.lib dxguid.lib'),('dx6',6,'ddraw.lib dxguid.lib'),('dx7',7,'ddraw.lib dxguid.lib'),('dx8',8,'d3d8.lib'),('dx9',9,'d3d9.lib d3dcompiler.lib')]:
    add('dgvoodoo_'+api,backend,libs,'ISOLATE_BACKGROUND',arches=('x86','x64') if api=='dx9' else ('x86',),application=api,transport='d3d11',dependency='dgvoodoo-ms',wrapper='dgvoodoo')
for version in (1,2,4,7):add(f'dgvoodoo_ddraw{version}_2d',40,'ddraw.lib dxguid.lib',f'LEGACY_MATERIALS ISOLATE_BACKGROUND DD_VERSION={version}',arches=('x86',),application='directdraw-2d',transport='d3d11',dependency='dgvoodoo-ms',wrapper='dgvoodoo',directdraw_version=version)
for api,backend,libs,flags in [('dx8',8,'d3d8.lib',''),('dx9',9,'d3d9.lib d3dcompiler.lib',''),('dx10',10,'d3d10.lib dxgi.lib d3dcompiler.lib',''),('dx10_1',10,'d3d10_1.lib dxgi.lib d3dcompiler.lib','USE_DX10_1'),('dx11',11,'d3d11.lib dxgi.lib d3dcompiler.lib','')]:
    add('dxvk_'+api,backend,libs,flags,application=api,transport='vulkan',dependency='dxvk',wrapper='dxvk')

def import_dlls(spec):
    n=spec['backend']
    return ['libegl.dll','libglesv2.dll'] if n==22 else [{2:'ddraw.dll',3:'ddraw.dll',5:'ddraw.dll',6:'ddraw.dll',7:'ddraw.dll',8:'d3d8.dll',9:'d3d9.dll',10:'d3d10_1.dll' if 'USE_DX10_1' in spec['defines'] else 'd3d10.dll',11:'d3d11.dll',12:'d3d12.dll',21:'opengl32.dll',40:'ddraw.dll',41:{1:'glide.dll',2:'glide2x.dll',3:'glide3x.dll'}[spec.get('glide_version',1)]}[n]]
