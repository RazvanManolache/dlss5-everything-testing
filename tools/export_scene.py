"""Build one common museum snapshot from the original gallery, never a screenshot."""
from pathlib import Path
import json, math, struct, hashlib, shutil, subprocess
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
from build_dependencies import dependency,visual_studio_build
GALLERY=dependency('gallery')
BUILD=ROOT/'build'
OUT=BUILD/'scene'
VS=visual_studio_build()

def export_layout():
    original=(GALLERY/'android/app/src/main/cpp/museum.cpp').read_text()
    math_code=original[original.index('struct XMFLOAT3'):original.index('static AAssetManager')]
    cpp='''#include <algorithm>
#include <cmath>
#include <vector>
#include <fstream>
#include <stdexcept>
#include "json.hpp"
using Json=nlohmann::json;
constexpr float XM_PI=3.141592653589793f,XM_2PI=XM_PI*2,XM_PIDIV2=XM_PI/2;
'''+math_code+'''
struct Person{Json rig;std::vector<float> matrices,currentBones;unsigned boneCount;float stride;};
#include "catalogue.inc"
Person people[ActorCount];bool facialAnimation=true;
#include "gallery_animation.inc"
struct GalleryObject{Mat world;XMFLOAT4 material;unsigned mesh,lowMesh,animationKind=0;};
std::vector<GalleryObject> gallery;
unsigned assetMesh(unsigned a,unsigned lod){return a<4?6+a*2+std::min(lod,1u):14+(a-4)*4+lod;}
void add(unsigned mesh,unsigned low,Mat world,XMFLOAT4 material){gallery.push_back({world,material,mesh,low,0});}
#include "gallery_layout.inc"
int main(){makeGallery();Json out;out["objects"]=Json::array();
for(auto&o:gallery)out["objects"].push_back({{"world",std::vector<float>(o.world.m,o.world.m+16)},{"material",{o.material.x,o.material.y,o.material.z,o.material.w}},{"mesh",o.mesh},{"kind",o.animationKind}});
for(unsigned i=0;i<ActorCount;i++){auto s=visitorState(i,.9f);out["actors"].push_back({{"x",s.x},{"z",s.z},{"yaw",s.yaw},{"walk",s.walk},{"phase",s.phase}});}
std::ofstream("layout.json")<<out.dump(2);}
'''
    (BUILD/'export_layout.cpp').write_text(cpp)
    inc=GALLERY/'android/app/src/main/cpp'
    batch=f'''@echo off
call "{VS}/vcvars64.bat" >nul
cl /nologo /std:c++17 /EHsc /O2 /MT /I"{inc}" /I"{ROOT}/vendor" export_layout.cpp /Fe:export_layout.exe /Fo:export_layout.obj
if errorlevel 1 exit /b 1
export_layout.exe
'''
    (BUILD/'export_layout.cmd').write_text(batch)
    subprocess.run(['cmd','/c',str(BUILD/'export_layout.cmd')],cwd=BUILD,check=True)
    return json.loads((BUILD/'layout.json').read_text())

def mesh(path):
    b=path.read_bytes(); n=struct.unpack_from('<I',b)[0]
    return np.frombuffer(b, '<f4',offset=4).reshape(n,12).copy()

def cube():
    out=[]
    for n,t,b in [([0,0,1],[1,0,0],[0,1,0]),([0,0,-1],[-1,0,0],[0,1,0]),([1,0,0],[0,0,-1],[0,1,0]),([-1,0,0],[0,0,1],[0,1,0]),([0,1,0],[1,0,0],[0,0,-1]),([0,-1,0],[1,0,0],[0,0,1])]:
        n,t,b=map(np.array,(n,t,b))
        for k in [0,1,2,0,2,3]:
            u=float(k in (1,2)); v=float(k>=2)
            out.append([*(n*.5+t*(u-.5)+b*(v-.5)),*n,u,1-v,*t,-1])
    return np.array(out,np.float32)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'quality').mkdir(exist_ok=True)
    layout=export_layout(); catalog=json.loads((GALLERY/'gallery_people.json').read_text())
    names=['horse_statue_01','antique_ceramic_vase_01','chinese_armchair','vintage_video_camera']+[p['name'] for p in catalog['people']+catalog['animals']]
    focus=11; focus_name=names[focus+4]
    meshes={4:cube(),2:mesh(GALLERY/'base_assets/marble_high.mesh')}
    sources=[]
    head=None
    for i,name in enumerate(names):
        if i<4:
            path=GALLERY/f'assets/variety/{name}_high.mesh'; meshes[6+i*2]=mesh(path)
        else:
            person=i-4; folder=GALLERY/'assets/living_people'; rig=json.loads((folder/f'{name}_rig.json').read_text())
            lod=0
            n=rig['lod_counts'][lod]; offset=rig['lod_offsets'][lod]
            raw=(folder/f'{name}.skin').read_bytes()[offset*152:(offset+n)*152]
            dtype=np.dtype([('v','<f4',12),('ids','<u4',4),('weights','<f4',4),('face','<f4',18)])
            skin=np.frombuffer(raw,dtype=dtype)
            a=skin['v'].copy(); state=layout['actors'][person]
            count=rig['bone_count']; matrices=np.fromfile(folder/f'{name}.bones','<f4').reshape(-1,count,4,4)
            walk,idle=rig['clips'][:2]; wp=(state['phase']/max(.5,rig['stride'])%1)*walk['frames']
            clock=((.9+person*.37)%(idle['seconds']*2))/idle['seconds']; ip=(clock if clock<=1 else 2-clock)*(idle['frames']-1)
            ia=int(ip); wa=int(wp)%walk['frames']
            standing=matrices[idle['offset']+ia]*(1-(ip-ia))+matrices[idle['offset']+min(ia+1,idle['frames']-1)]*(ip-ia)
            walking=matrices[wa]*(1-(wp%1))+matrices[(wa+1)%walk['frames']]*(wp%1)
            bones=standing+(walking-standing)*state['walk']
            weights=skin['weights']; ids=skin['ids']; p=a[:,:3].copy()
            smile=.12+.08*math.sin(.9*.6+person); p+=skin['face'][:,6:9]*smile
            for start,w in [(0,1),(3,0),(8,0)]:
                values=np.c_[p if start==0 else a[:,start:start+3],np.full(n,w)]
                a[:,start:start+3]=sum(np.einsum('nij,nj->ni',bones[ids[:,k],:3,:],values)*weights[:,k,None] for k in range(4))
            meshes[14+person*4]=a
            if person==focus:
                head=(bones[rig['head_bone']]@np.r_[rig['head_anchor'],1])[:3]
        sources.append({'name':name,'actor':i>=4})
    textures=[]
    for i,name in enumerate(names+['marble']):
        folder=GALLERY/('base_assets' if name=='marble' else 'assets/people' if i>=4 else 'assets/variety')
        source=folder/f'{name}_color.rgba'; b=source.read_bytes(); w,h=struct.unpack_from('<II',b)
        im=Image.frombytes('RGBA',(w,h),b[8:]); size=2048
        (OUT/'quality'/f'texture_{i}.rgba').write_bytes(b)
        for kind in ['normal','rough']:
            (OUT/'quality'/f'{kind}_{i}.rgba').write_bytes((folder/f'{name}_{kind}.rgba').read_bytes())
        im.thumbnail((size,size),Image.Resampling.LANCZOS)
        (OUT/f'texture_{i}.rgba').write_bytes(struct.pack('<II',*im.size)+im.tobytes())
        textures.append({'file':f'texture_{i}.rgba','width':im.width,'height':im.height,'source':str(source.relative_to(GALLERY)),'source_sha256':hashlib.sha256(b).hexdigest()})
    # White fallback for untextured architecture.
    (OUT/'texture_23.rgba').write_bytes(struct.pack('<II',1,1)+bytes([255]*4))
    for kind,pixel in [('texture',bytes([255]*4)),('normal',bytes([128,128,255,255])),('rough',bytes([190]*3+[255]))]:
        (OUT/'quality'/f'{kind}_23.rgba').write_bytes(struct.pack('<II',1,1)+pixel)
    draws=[]; vertices=[]; attributes=[]; first=0
    light=np.array([-.35,.7,.65]); light/=np.linalg.norm(light)
    dtype=np.dtype([('p','<f4',3),('color','u1',4),('uv','<f4',2)])
    for obj in layout['objects']:
        kind=obj['kind']; mat=obj['material']; mid=obj['mesh']
        if kind>=100: continue # Hand props are hidden in this common frozen pose.
        world=np.array(obj['world']).reshape(4,4)
        if 10<=kind<28:
            i=kind-10; state=layout['actors'][i]; angle=state['yaw']; c,s=math.cos(angle),math.sin(angle)
            world=np.array([[c,0,-s,0],[0,1,0,0],[s,0,c,0],[state['x'],.26 if i>=16 else -.025,state['z'],1]])
            mid=14+i*4
        if mid not in meshes:
            mid=mid-1 if mid%2 and mid<14 else mid
        a=meshes[mid]; n=len(a)
        pos=(np.c_[a[:,:3],np.ones(n)]@world)[:,:3]
        normals=a[:,3:6]@np.linalg.inv(world[:3,:3]).T; normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-8)
        illumination=np.tile(np.array([.28,.32,.39]),(n,1))
        for lp,lc,power in [([-2.7,4.2,3.5],[1,.72,.48],9),([3.2,3.6,2],[.5,.72,1],8),([-5,4.8,-4],[1,.75,.5],14),([5,4.8,-4],[.5,.7,1],16),([-4.5,5,-8],[1,.7,.4],16),([4.5,5,-8],[.4,.65,1],16),([4.4,2.9,5.3],[1,.87,.72],5.8),([1.1,2.6,2.3],[.45,.65,1],3.4)]:
            delta=np.asarray(lp)-pos;distance=np.linalg.norm(delta,axis=1);direction=delta/np.maximum(distance[:,None],1e-8)
            intensity=np.maximum(np.sum(normals*direction,axis=1),0)*power/(1+distance*distance)
            illumination+=intensity[:,None]*np.asarray(lc)
        illumination=np.clip(illumination,0,1)**(1/2.2)
        mapped=mat[3]==1 or mat[3]>=6
        tint=np.ones(3) if mapped else np.power(np.clip(mat[:3],0,1),1/2.2)
        color=np.clip(illumination*tint*255,0,255).astype('u1')
        v=np.zeros(n,dtype);v['p']=pos;v['color'][:,:3]=color;v['color'][:,3]=255;v['uv']=a[:,6:8]
        tid=22 if mat[3]==1 else int(mat[3])-6 if mat[3]>=6 else 23
        tangents=a[:,8:11]@world[:3,:3];tangents-=normals*np.sum(normals*tangents,axis=1,keepdims=True);tangents/=np.maximum(np.linalg.norm(tangents,axis=1,keepdims=True),1e-8)
        params=np.tile([mat[3],.82 if mat[3]==4 else 0,.28 if mat[3]==4 else .65,1.0],(n,1))
        attributes.append(np.c_[normals,tangents,a[:,11],np.tile(tint,(n,1)),params].astype('<f4'))
        vertices.append(v); draws.append((first,n,tid)); first+=n
    state=layout['actors'][focus]; target=[state['x'],float(head[1]-.025),state['z']]
    angle=state['yaw']+.22; distance=.63
    eye=[target[0]+math.sin(angle)*distance,target[1]+.035,target[2]+math.cos(angle)*distance]
    data=np.concatenate(vertices)
    (OUT/'museum.bin').write_bytes(struct.pack('<4I',0x4D555345,len(data),len(draws),24)+np.array(eye+target,dtype='<f4').tobytes()+np.array(draws,dtype='<u4').tobytes()+data.tobytes())
    (OUT/'shading.bin').write_bytes(np.concatenate(attributes).tobytes())
    report={'source':'phoenix-gallery','pose_seconds':.9,'focus_person':focus,'focus_name':focus_name,'objects':len(draws),'triangles':len(data)//3,'eye':eye,'target':target,'textures':textures,'mesh_quality':'LOD0 for every actor and highest available exhibit meshes','showcase_textures':'Full original authored color, normal and roughness maps; device limits reported at runtime','matched_textures':'2048px color maps shared by all APIs','animation':'Slow camera sway at runtime; common skeletal and facial pose sampled at 0.9 seconds.'}
    (OUT/'provenance.json').write_text(json.dumps(report,indent=2))
    shutil.copy2(GALLERY/'CREDITS.md',OUT/'CREDITS.md')
    shutil.copytree(GALLERY/'licenses',OUT/'licenses',dirs_exist_ok=True)
    print(json.dumps({k:v for k,v in report.items() if k!='textures'},indent=2))

if __name__=='__main__': main()
