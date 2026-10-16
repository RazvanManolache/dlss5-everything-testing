// Original DirectDraw/Direct3D COM interfaces, with no translation DLL bundled.
#include <ddraw.h>
#include <d3d.h>
#include <array>
#if BACKEND==2
using DD=IDirectDraw;using Surface=IDirectDrawSurface;using Desc=DDSURFACEDESC;
using D3D=IDirect3D;using Device=IDirect3DDevice;using Viewport=IDirect3DViewport;
constexpr const char* ddInterface="IDirectDraw";constexpr const char* d3dInterface="IDirect3DDevice";
#elif BACKEND==3
using DD=IDirectDraw2;using Surface=IDirectDrawSurface;using Desc=DDSURFACEDESC;
using D3D=IDirect3D;using Device=IDirect3DDevice;using Viewport=IDirect3DViewport;
constexpr const char* ddInterface="IDirectDraw2";constexpr const char* d3dInterface="IDirect3DDevice";
#elif BACKEND==5
using DD=IDirectDraw2;using Surface=IDirectDrawSurface;using Desc=DDSURFACEDESC;
using D3D=IDirect3D2;using Device=IDirect3DDevice2;using Viewport=IDirect3DViewport2;
constexpr const char* ddInterface="IDirectDraw2";constexpr const char* d3dInterface="IDirect3DDevice2";
#elif BACKEND==6
using DD=IDirectDraw4;using Surface=IDirectDrawSurface4;using Desc=DDSURFACEDESC2;
using D3D=IDirect3D3;using Device=IDirect3DDevice3;using Viewport=IDirect3DViewport3;
constexpr const char* ddInterface="IDirectDraw4";constexpr const char* d3dInterface="IDirect3DDevice3";
#elif BACKEND==7
using DD=IDirectDraw7;using Surface=IDirectDrawSurface7;using Desc=DDSURFACEDESC2;
using D3D=IDirect3D7;using Device=IDirect3DDevice7;
constexpr const char* ddInterface="IDirectDraw7";constexpr const char* d3dInterface="IDirect3DDevice7";
#endif
DD* ddraw{};D3D* d3d{};Device* device{};Surface* primary{};Surface* target{};Surface* depth{};IDirectDrawClipper* clipper{};
std::vector<Surface*> gpuTextures;std::vector<D3DTEXTUREHANDLE> textureHandles;
#if BACKEND<=3
IDirect3DExecuteBuffer* executeBuffer{};
std::vector<IDirect3DTexture*> textureInterfaces;
#elif BACKEND==5
std::vector<IDirect3DTexture2*> textureInterfaces;
#endif
#if BACKEND<7
Viewport* viewport{};
#endif
DDPIXELFORMAT textureFormat{};unsigned zBits=0;uint64_t executeCalls=0,drawCalls=0,trianglesSubmitted=0;
void rendererStatus(){Json j={{"api",API_NAME},{"directdraw_interface",ddInterface},{"direct3d_device_interface",d3dInterface},{"device_type","HAL"},{"texture_handles",textureHandles},{"texture_count",gpuTextures.size()},{"texture_bits",textureFormat.dwRGBBitCount},{"texture_alpha_mask",textureFormat.dwRGBAlphaBitMask},{"depth_bits",zBits},{"execute_buffer_calls",executeCalls},{"draw_primitive_calls",drawCalls},{"triangles_submitted",trianglesSubmitted},{"vertex_processing","CPU homogeneous clipping and projection; native Direct3D perspective-correct textured triangle rasterization and depth testing"},{"presentation","DirectDraw primary-surface Blt"}};std::ofstream(output/"renderer.json")<<j.dump(2);}
int textureScore(const DDPIXELFORMAT& f){if(!(f.dwFlags&DDPF_RGB)||!(f.dwFlags&DDPF_ALPHAPIXELS)||f.dwFourCC)return -1;if(f.dwRGBBitCount==32&&f.dwRGBAlphaBitMask==0xFF000000&&f.dwRBitMask==0x00FF0000&&f.dwGBitMask==0x0000FF00&&f.dwBBitMask==0x000000FF)return 100;if(f.dwRGBBitCount==16&&f.dwRGBAlphaBitMask)return f.dwRGBAlphaBitMask==0x8000?60:50;return -1;}
HRESULT CALLBACK enumOldTexture(DDSURFACEDESC* d,void*){if(textureScore(d->ddpfPixelFormat)>textureScore(textureFormat))textureFormat=d->ddpfPixelFormat;return D3DENUMRET_OK;}
HRESULT CALLBACK enumNewTexture(DDPIXELFORMAT* d,void*){if(textureScore(*d)>textureScore(textureFormat))textureFormat=*d;return D3DENUMRET_OK;}
HRESULT CALLBACK enumDepth(DDPIXELFORMAT* d,void* result){auto& f=*static_cast<DDPIXELFORMAT*>(result);if((d->dwFlags&DDPF_ZBUFFER)&&!(d->dwFlags&DDPF_STENCILBUFFER)&&(f.dwSize==0||d->dwZBufferBitDepth>f.dwZBufferBitDepth))f=*d;return D3DENUMRET_OK;}
unsigned packChannel(unsigned value,DWORD mask){if(!mask)return 0;unsigned shift=0;while(!(mask&(1u<<shift)))++shift;unsigned max=mask>>shift;return ((value*max+127)/255)<<shift;}
void loadTextures(){
unsigned maxWidth=2048,maxHeight=2048;
#if BACKEND<7
D3DDEVICEDESC hal{},hel{};hal.dwSize=sizeof(hal);hel.dwSize=sizeof(hel);hr(device->GetCaps(&hal,&hel),"GetHALCaps");std::ofstream(output/"device-caps.json")<<Json({{"max_execute_buffer",hal.dwMaxBufferSize},{"max_vertex_count",hal.dwMaxVertexCount},{"flags",hal.dwFlags}}).dump(2);maxWidth=hal.dwMaxTextureWidth?hal.dwMaxTextureWidth:maxWidth;maxHeight=hal.dwMaxTextureHeight?hal.dwMaxTextureHeight:maxHeight;
#else
D3DDEVICEDESC7 hal{};hr(device->GetCaps(&hal),"GetHALCaps7");maxWidth=hal.dwMaxTextureWidth;maxHeight=hal.dwMaxTextureHeight;
#endif
for(unsigned i=0;i<textures.size();i++){limitTexture(textures[i],maxWidth,maxHeight);textureInventory[i]["applied_width"]=textures[i].w;textureInventory[i]["applied_height"]=textures[i].h;textureInventory[i]["device_max_width"]=maxWidth;textureInventory[i]["device_max_height"]=maxHeight;}

#if BACKEND<=5
hr(device->EnumTextureFormats(enumOldTexture,nullptr),"EnumTextureFormats");
#else
hr(device->EnumTextureFormats(enumNewTexture,nullptr),"EnumTextureFormats");
#endif
ensure(textureScore(textureFormat)>=0,"No native RGBA texture format");
for(auto& t:textures){Desc desc{};desc.dwSize=sizeof(desc);desc.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT|DDSD_PIXELFORMAT;desc.dwWidth=t.w;desc.dwHeight=t.h;desc.ddsCaps.dwCaps=DDSCAPS_TEXTURE|DDSCAPS_VIDEOMEMORY;desc.ddpfPixelFormat=textureFormat;Surface* texture=nullptr;hr(ddraw->CreateSurface(&desc,&texture,nullptr),"CreateTextureSurface");Desc map{};map.dwSize=sizeof(map);hr(texture->Lock(nullptr,&map,DDLOCK_WAIT,nullptr),"LockTexture");for(unsigned y=0;y<t.h;y++)for(unsigned x=0;x<t.w;x++){auto* src=t.pixels.data()+(size_t(y)*t.w+x)*4;DWORD pixel=packChannel(src[0],textureFormat.dwRBitMask)|packChannel(src[1],textureFormat.dwGBitMask)|packChannel(src[2],textureFormat.dwBBitMask)|packChannel(src[3],textureFormat.dwRGBAlphaBitMask);memcpy(static_cast<uint8_t*>(map.lpSurface)+size_t(y)*map.lPitch+x*(textureFormat.dwRGBBitCount/8),&pixel,textureFormat.dwRGBBitCount/8);}
hr(texture->Unlock(nullptr),"UnlockTexture");
#if BACKEND<=3
IDirect3DTexture* tex=nullptr;hr(texture->QueryInterface(IID_IDirect3DTexture,reinterpret_cast<void**>(&tex)),"QueryTexture1");D3DTEXTUREHANDLE handle{};hr(tex->GetHandle(device,&handle),"Texture1GetHandle");textureInterfaces.push_back(tex);textureHandles.push_back(handle);
#elif BACKEND==5
IDirect3DTexture2* tex=nullptr;hr(texture->QueryInterface(IID_IDirect3DTexture2,reinterpret_cast<void**>(&tex)),"QueryTexture2");D3DTEXTUREHANDLE handle{};hr(tex->GetHandle(device,&handle),"Texture2GetHandle");textureInterfaces.push_back(tex);textureHandles.push_back(handle);
#endif
gpuTextures.push_back(texture);}}
std::vector<std::pair<D3DRENDERSTATETYPE,DWORD>> commonStates(){return {{D3DRENDERSTATE_ZENABLE,TRUE},{D3DRENDERSTATE_ZWRITEENABLE,TRUE},{D3DRENDERSTATE_ZFUNC,D3DCMP_LESSEQUAL},{D3DRENDERSTATE_CULLMODE,D3DCULL_NONE},{D3DRENDERSTATE_SHADEMODE,D3DSHADE_GOURAUD},{D3DRENDERSTATE_TEXTUREPERSPECTIVE,TRUE},{D3DRENDERSTATE_ALPHABLENDENABLE,FALSE},{D3DRENDERSTATE_ALPHATESTENABLE,TRUE},{D3DRENDERSTATE_ALPHAREF,127},{D3DRENDERSTATE_ALPHAFUNC,D3DCMP_GREATER},{D3DRENDERSTATE_SPECULARENABLE,showcase?TRUE:FALSE},{D3DRENDERSTATE_FOGENABLE,showcase?TRUE:FALSE},{D3DRENDERSTATE_FOGCOLOR,0x00202c3a},{D3DRENDERSTATE_TEXTUREMAG,D3DFILTER_LINEAR},{D3DRENDERSTATE_TEXTUREMIN,D3DFILTER_LINEAR},{D3DRENDERSTATE_TEXTUREMAPBLEND,D3DTBLEND_MODULATE},{D3DRENDERSTATE_TEXTUREADDRESS,D3DTADDRESS_WRAP}};}
void initRenderer(){
// The system D3D1/2 rasterizer rejects render targets wider than 2048.
if(W>2048||H>2048){float scale=std::min(2048.f/W,2048.f/H);W=unsigned(W*scale);H=unsigned(H*scale);}

#if BACKEND==7
hr(DirectDrawCreateEx(nullptr,reinterpret_cast<void**>(&ddraw),IID_IDirectDraw7,nullptr),"DirectDrawCreateEx7");
#else
IDirectDraw* base=nullptr;hr(DirectDrawCreate(nullptr,&base,nullptr),"DirectDrawCreate");
#if BACKEND==2
ddraw=base;
#elif BACKEND==3 || BACKEND==5
hr(base->QueryInterface(IID_IDirectDraw2,reinterpret_cast<void**>(&ddraw)),"QueryDirectDraw2");base->Release();
#elif BACKEND==6
hr(base->QueryInterface(IID_IDirectDraw4,reinterpret_cast<void**>(&ddraw)),"QueryDirectDraw4");base->Release();
#endif
#endif
hr(ddraw->SetCooperativeLevel(windowHandle,DDSCL_NORMAL),"SetCooperativeLevel");
#if BACKEND<=3
hr(ddraw->QueryInterface(IID_IDirect3D,reinterpret_cast<void**>(&d3d)),"QueryDirect3D1");
#elif BACKEND==5
hr(ddraw->QueryInterface(IID_IDirect3D2,reinterpret_cast<void**>(&d3d)),"QueryDirect3D2");
#elif BACKEND==6
hr(ddraw->QueryInterface(IID_IDirect3D3,reinterpret_cast<void**>(&d3d)),"QueryDirect3D3");
#elif BACKEND==7
hr(ddraw->QueryInterface(IID_IDirect3D7,reinterpret_cast<void**>(&d3d)),"QueryDirect3D7");
#endif
Desc desc{};desc.dwSize=sizeof(desc);desc.dwFlags=DDSD_CAPS;desc.ddsCaps.dwCaps=DDSCAPS_PRIMARYSURFACE;hr(ddraw->CreateSurface(&desc,&primary,nullptr),"CreatePrimarySurface");hr(ddraw->CreateClipper(0,&clipper,nullptr),"CreateClipper");hr(clipper->SetHWnd(0,windowHandle),"SetClipperWindow");hr(primary->SetClipper(clipper),"SetPrimaryClipper");desc={};desc.dwSize=sizeof(desc);desc.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT;desc.dwWidth=W;desc.dwHeight=H;desc.ddsCaps.dwCaps=DDSCAPS_OFFSCREENPLAIN|DDSCAPS_3DDEVICE|DDSCAPS_VIDEOMEMORY;hr(ddraw->CreateSurface(&desc,&target,nullptr),"Create3DTarget");desc={};desc.dwSize=sizeof(desc);desc.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT;desc.dwWidth=W;desc.dwHeight=H;desc.ddsCaps.dwCaps=DDSCAPS_ZBUFFER|DDSCAPS_VIDEOMEMORY;
#if BACKEND<=5
desc.dwFlags|=DDSD_ZBUFFERBITDEPTH;desc.dwZBufferBitDepth=16;zBits=16;
#else
DDPIXELFORMAT format{};hr(d3d->EnumZBufferFormats(IID_IDirect3DHALDevice,enumDepth,&format),"EnumZBufferFormats");ensure(format.dwSize!=0,"No HAL depth format");desc.dwFlags|=DDSD_PIXELFORMAT;desc.ddpfPixelFormat=format;zBits=format.dwZBufferBitDepth;
#endif
hr(ddraw->CreateSurface(&desc,&depth,nullptr),"CreateDepthSurface");hr(target->AddAttachedSurface(depth),"AttachDepthSurface");
#if BACKEND<=3
hr(target->QueryInterface(IID_IDirect3DHALDevice,reinterpret_cast<void**>(&device)),"QueryHALDevice1");
#elif BACKEND==5
hr(d3d->CreateDevice(IID_IDirect3DHALDevice,target,&device),"CreateHALDevice2");
#elif BACKEND==6
hr(d3d->CreateDevice(IID_IDirect3DHALDevice,target,&device,nullptr),"CreateHALDevice3");
#elif BACKEND==7
hr(d3d->CreateDevice(IID_IDirect3DHALDevice,target,&device),"CreateHALDevice7");
#endif
gpuName="Native DirectDraw HAL";
#if BACKEND<7
hr(d3d->CreateViewport(&viewport,nullptr),"CreateViewport");hr(device->AddViewport(viewport),"AddViewport");D3DVIEWPORT v{};v.dwSize=sizeof(v);v.dwWidth=W;v.dwHeight=H;v.dvScaleX=W*.5f;v.dvScaleY=H*.5f;v.dvMaxX=v.dvMaxY=1;v.dvMaxZ=1;hr(viewport->SetViewport(&v),"SetViewport");
#if BACKEND>=5
hr(device->SetCurrentViewport(viewport),"SetCurrentViewport");
#endif
#else
D3DVIEWPORT7 v{0,0,W,H,0,1};hr(device->SetViewport(&v),"SetViewport7");
#endif
loadTextures();
#if BACKEND<=3
D3DEXECUTEBUFFERDESC ed{};ed.dwSize=sizeof(ed);ed.dwFlags=D3DDEB_BUFSIZE|D3DDEB_CAPS;ed.dwCaps=D3DDEBCAPS_SYSTEMMEMORY;ed.dwBufferSize=1023*sizeof(D3DTLVERTEX)+341*sizeof(D3DTRIANGLE)+4096;hr(device->CreateExecuteBuffer(&ed,&executeBuffer,nullptr),"CreateExecuteBuffer");
#else
for(auto s:commonStates()){
#if BACKEND==7
if(s.first==D3DRENDERSTATE_TEXTUREPERSPECTIVE||s.first==D3DRENDERSTATE_TEXTUREMAG||s.first==D3DRENDERSTATE_TEXTUREMIN||s.first==D3DRENDERSTATE_TEXTUREMAPBLEND||s.first==D3DRENDERSTATE_TEXTUREADDRESS)continue;
#endif
hr(device->SetRenderState(s.first,s.second),"SetRenderState");}
#if BACKEND>=6
hr(device->SetTextureStageState(0,D3DTSS_COLOROP,D3DTOP_MODULATE),"TextureColorOp");hr(device->SetTextureStageState(0,D3DTSS_COLORARG1,D3DTA_TEXTURE),"TextureColorArg1");hr(device->SetTextureStageState(0,D3DTSS_COLORARG2,D3DTA_DIFFUSE),"TextureColorArg2");hr(device->SetTextureStageState(0,D3DTSS_ALPHAOP,D3DTOP_SELECTARG1),"TextureAlphaOp");hr(device->SetTextureStageState(0,D3DTSS_ALPHAARG1,D3DTA_TEXTURE),"TextureAlphaArg");hr(device->SetTextureStageState(0,D3DTSS_MINFILTER,D3DTFN_LINEAR),"TextureMinFilter");hr(device->SetTextureStageState(0,D3DTSS_MAGFILTER,D3DTFG_LINEAR),"TextureMagFilter");
#endif
#endif
rendererStatus();}
// Clipping in homogeneous space keeps triangles crossing the near plane intact.
// This also lets the original D3D1 execute path use its COPY vertex opcode.
struct ClipVertex{XMFLOAT4 p;float c[4];float uv[2];float spec[4];};
std::vector<ClipVertex> clipVertices;
std::array<std::vector<D3DTLVERTEX>,24> batches;
float planeDistance(const ClipVertex& v,unsigned plane){switch(plane){case 0:return v.p.x+v.p.w;case 1:return v.p.w-v.p.x;case 2:return v.p.y+v.p.w;case 3:return v.p.w-v.p.y;case 4:return v.p.z;default:return v.p.w-v.p.z;}}
ClipVertex interpolate(const ClipVertex& a,const ClipVertex& b,float t){ClipVertex c;const float* x=reinterpret_cast<const float*>(&a);const float* y=reinterpret_cast<const float*>(&b);float* z=reinterpret_cast<float*>(&c);for(unsigned i=0;i<14;i++)z[i]=x[i]+(y[i]-x[i])*t;return c;}
D3DTLVERTEX screenVertex(const ClipVertex& v){D3DTLVERTEX out{};float inv=1/v.p.w;out.sx=(v.p.x*inv+1)*W*.5f;out.sy=(1-v.p.y*inv)*H*.5f;out.sz=std::clamp(v.p.z*inv,0.f,1.f);out.rhw=inv;auto ch=[&](unsigned i){return DWORD(std::clamp(v.c[i],0.f,255.f)+.5f);};out.color=(ch(3)<<24)|(ch(0)<<16)|(ch(1)<<8)|ch(2);out.specular=(DWORD(std::clamp(v.spec[3],0.f,255.f))<<24)|(DWORD(std::clamp(v.spec[0],0.f,255.f))<<16)|(DWORD(std::clamp(v.spec[1],0.f,255.f))<<8)|DWORD(std::clamp(v.spec[2],0.f,255.f));out.tu=v.uv[0];out.tv=v.uv[1];return out;}
void projectScene(){for(auto& b:batches)b.clear();clipVertices.resize(vertices.size());auto matrix=XMLoadFloat4x4(&vp);for(size_t i=0;i<vertices.size();i++){auto& in=vertices[i];auto& out=clipVertices[i];XMStoreFloat4(&out.p,XMVector4Transform(XMVectorSet(in.p[0],in.p[1],in.p[2],1),matrix));for(unsigned c=0;c<4;c++)out.c[c]=float((in.color>>(c*8))&255);out.uv[0]=in.uv[0];out.uv[1]=in.uv[1];uint32_t spec=showcase?vertexSpecular[i]:0;out.spec[0]=float((spec>>16)&255);out.spec[1]=float((spec>>8)&255);out.spec[2]=float(spec&255);out.spec[3]=float(spec>>24);}
for(auto& draw:draws){auto& batch=batches[draw.texture];for(unsigned t=0;t<draw.count;t+=3){ClipVertex polygon[12],temp[12];for(unsigned k=0;k<3;k++)polygon[k]=clipVertices[draw.first+t+k];unsigned count=3;for(unsigned p=0;p<6&&count;p++){unsigned n=0;for(unsigned i=0;i<count;i++){const auto& a=polygon[i];const auto& b=polygon[(i+1)%count];float da=planeDistance(a,p),db=planeDistance(b,p);bool inside=da>=0;if(inside)temp[n++]=a;if(inside!=(db>=0))temp[n++]=interpolate(a,b,da/(da-db));}count=n;memcpy(polygon,temp,n*sizeof(ClipVertex));}for(unsigned k=1;k+1<count;k++){batch.push_back(screenVertex(polygon[0]));batch.push_back(screenVertex(polygon[k]));batch.push_back(screenVertex(polygon[k+1]));}}}}
#if BACKEND<=3
void executeTriangles(const D3DTLVERTEX* v,unsigned count,D3DTEXTUREHANDLE texture){ensure(count<=1023&&count%3==0,"Execute batch size");D3DEXECUTEBUFFERDESC desc{};desc.dwSize=sizeof(desc);hr(executeBuffer->Lock(&desc),"LockExecuteBuffer");auto* base=static_cast<uint8_t*>(desc.lpData);memcpy(base,v,count*sizeof(D3DTLVERTEX));auto* at=base+count*sizeof(D3DTLVERTEX);auto header=[&](BYTE op,BYTE size,WORD n){D3DINSTRUCTION h{op,size,n};memcpy(at,&h,sizeof(h));at+=sizeof(h);};auto state=[&](D3DRENDERSTATETYPE key,DWORD value){header(D3DOP_STATERENDER,sizeof(D3DSTATE),1);D3DSTATE s{};s.drstRenderStateType=key;s.dwArg[0]=value;memcpy(at,&s,sizeof(s));at+=sizeof(s);};header(D3DOP_PROCESSVERTICES,sizeof(D3DPROCESSVERTICES),1);D3DPROCESSVERTICES process{D3DPROCESSVERTICES_COPY,0,0,count,0};memcpy(at,&process,sizeof(process));at+=sizeof(process);for(auto s:commonStates())state(s.first,s.second);state(D3DRENDERSTATE_TEXTUREHANDLE,texture);header(D3DOP_TRIANGLE,sizeof(D3DTRIANGLE),WORD(count/3));for(unsigned i=0;i<count;i+=3){D3DTRIANGLE tri{};tri.v1=WORD(i);tri.v2=WORD(i+1);tri.v3=WORD(i+2);tri.wFlags=D3DTRIFLAG_START;memcpy(at,&tri,sizeof(tri));at+=sizeof(tri);}header(D3DOP_EXIT,0,0);D3DEXECUTEDATA data{};data.dwSize=sizeof(data);data.dwVertexCount=count;data.dwInstructionOffset=count*sizeof(D3DTLVERTEX);data.dwInstructionLength=DWORD(at-base-data.dwInstructionOffset);hr(executeBuffer->Unlock(),"UnlockExecuteBuffer");hr(executeBuffer->SetExecuteData(&data),"SetExecuteData");hr(device->Execute(executeBuffer,viewport,D3DEXECUTE_CLIPPED),"Execute");++executeCalls;trianglesSubmitted+=count/3;}
#endif
void captureTarget(){Desc map{};map.dwSize=sizeof(map);hr(target->Lock(nullptr,&map,DDLOCK_WAIT|DDLOCK_READONLY,nullptr),"LockCapture");ensure(map.ddpfPixelFormat.dwRGBBitCount==32,"Expected 32-bit capture surface");saveCapture(static_cast<uint8_t*>(map.lpSurface),map.lPitch,true);hr(target->Unlock(nullptr),"UnlockCapture");}
void drawFrame(bool capture){projectScene();DDBLTFX fill{};fill.dwSize=sizeof(fill);fill.dwFillColor=0x00202831;hr(target->Blt(nullptr,nullptr,nullptr,DDBLT_COLORFILL|DDBLT_WAIT,&fill),"ClearColor");
#if BACKEND<=3
fill.dwFillDepth=zBits==16?0xFFFF:0xFFFFFFFF;hr(depth->Blt(nullptr,nullptr,nullptr,DDBLT_DEPTHFILL|DDBLT_WAIT,&fill),"ClearDepth");
#elif BACKEND<7
D3DRECT rect{0,0,LONG(W),LONG(H)};hr(viewport->Clear(1,&rect,D3DCLEAR_ZBUFFER),"ViewportClearDepth");
#else
hr(device->Clear(0,nullptr,D3DCLEAR_ZBUFFER,0,1,0),"ClearDepth7");
#endif
hr(device->BeginScene(),"BeginScene");for(unsigned texture=0;texture<24;texture++){auto& batch=batches[texture];if(batch.empty())continue;
#if BACKEND==5
hr(device->SetRenderState(D3DRENDERSTATE_TEXTUREHANDLE,textureHandles[texture]),"SetTextureHandle");
#elif BACKEND==6
IDirect3DTexture2* tex=nullptr;hr(gpuTextures[texture]->QueryInterface(IID_IDirect3DTexture2,reinterpret_cast<void**>(&tex)),"QueryTexture2");hr(device->SetTexture(0,tex),"SetTexture2");tex->Release();
#elif BACKEND==7
hr(device->SetTexture(0,gpuTextures[texture]),"SetTexture7");
#endif
for(unsigned offset=0;offset<batch.size();offset+=1023){unsigned n=std::min(1023u,unsigned(batch.size())-offset);
#if BACKEND<=3
executeTriangles(batch.data()+offset,n,textureHandles[texture]);
#elif BACKEND==5
hr(device->DrawPrimitive(D3DPT_TRIANGLELIST,D3DVT_TLVERTEX,batch.data()+offset,n,0),"DrawPrimitive2");++drawCalls;trianglesSubmitted+=n/3;
#else
hr(device->DrawPrimitive(D3DPT_TRIANGLELIST,D3DFVF_TLVERTEX,batch.data()+offset,n,0),"DrawPrimitive");++drawCalls;trianglesSubmitted+=n/3;
#endif
}}
hr(device->EndScene(),"EndScene");if(capture)captureTarget();POINT origin{0,0};ClientToScreen(windowHandle,&origin);RECT dest{origin.x,origin.y,origin.x+LONG(clientWidth),origin.y+LONG(clientHeight)};hr(primary->Blt(&dest,target,nullptr,DDBLT_WAIT,nullptr),"PresentBlt");if(frameNumber==0||frameNumber%120==0)rendererStatus();}
void shutdownRenderer(){rendererStatus();
#if BACKEND<=3
if(executeBuffer)executeBuffer->Release();
#endif
#if BACKEND<7
if(viewport){device->DeleteViewport(viewport);viewport->Release();}
#endif
#if BACKEND<=5
for(auto* t:textureInterfaces)t->Release();
#endif
if(device)device->Release();for(auto* t:gpuTextures)t->Release();if(depth)depth->Release();if(target)target->Release();if(primary)primary->Release();if(clipper)clipper->Release();if(d3d)d3d->Release();if(ddraw)ddraw->Release();}
