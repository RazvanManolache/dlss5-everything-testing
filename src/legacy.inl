#if BACKEND==8
#include "d3d8.h"
using D3D=IDirect3D8;using Device=IDirect3DDevice8;using Tex=IDirect3DTexture8;using Surface=IDirect3DSurface8;using Buffer=IDirect3DVertexBuffer8;
extern "C" __declspec(dllimport) IDirect3D8* WINAPI Direct3DCreate8(UINT);
#else
#include <d3d9.h>
#ifdef USE_DX9EX
using D3D=IDirect3D9Ex;using Device=IDirect3DDevice9Ex;
#else
using D3D=IDirect3D9;using Device=IDirect3DDevice9;
#endif
using Tex=IDirect3DTexture9;using Surface=IDirect3DSurface9;using Buffer=IDirect3DVertexBuffer9;
#endif
D3D* d3d{};Device* device{};Buffer* vertexBuffer{};std::vector<Tex*> gpuTextures;
struct LegacyVertex{float p[3];DWORD color,specular;float uv[2];};
std::vector<LegacyVertex> converted;
#if defined(USE_DX9EX)
constexpr D3DPOOL fixturePool=D3DPOOL_DEFAULT;
#else
constexpr D3DPOOL fixturePool=D3DPOOL_MANAGED;
#endif
#if BACKEND==9
#include "dx9_runtime.inl"
#endif
constexpr DWORD FVF=D3DFVF_XYZ|D3DFVF_DIFFUSE|D3DFVF_SPECULAR|D3DFVF_TEX1;
void initRenderer(){
#if BACKEND==8
d3d=Direct3DCreate8(220);
#else
#ifdef USE_DX9EX
hr(Direct3DCreate9Ex(D3D_SDK_VERSION,&d3d),"Direct3DCreate9Ex");
#else
d3d=Direct3DCreate9(D3D_SDK_VERSION);
#endif
#endif
ensure(d3d!=nullptr,"Direct3DCreate");
#if BACKEND==8
D3DADAPTER_IDENTIFIER8 id{};
#else
D3DADAPTER_IDENTIFIER9 id{};
#endif
hr(d3d->GetAdapterIdentifier(0,0,&id),"GetAdapterIdentifier");gpuName=id.Description;
#if BACKEND==8
D3DPRESENT_PARAMETERS8 p{};
#else
D3DPRESENT_PARAMETERS p{};
#endif
#ifdef USE_DX9EX
constexpr DWORD textureUsage=D3DUSAGE_DYNAMIC;
#else
constexpr DWORD textureUsage=0;
#endif
p.BackBufferWidth=W;p.BackBufferHeight=H;p.BackBufferFormat=D3DFMT_X8R8G8B8;p.BackBufferCount=1;p.SwapEffect=D3DSWAPEFFECT_DISCARD;p.hDeviceWindow=windowHandle;p.Windowed=TRUE;p.EnableAutoDepthStencil=TRUE;p.AutoDepthStencilFormat=D3DFMT_D24S8;
#if BACKEND==9
p.PresentationInterval=D3DPRESENT_INTERVAL_IMMEDIATE;
#endif
#ifdef USE_DX9EX
hr(d3d->CreateDeviceEx(0,D3DDEVTYPE_HAL,windowHandle,D3DCREATE_HARDWARE_VERTEXPROCESSING,&p,nullptr,&device),"CreateDeviceEx");rendererInfo={{"creation","Direct3DCreate9Ex / CreateDeviceEx"},{"device_interface","IDirect3DDevice9Ex"}};
#else
hr(d3d->CreateDevice(0,D3DDEVTYPE_HAL,windowHandle,D3DCREATE_HARDWARE_VERTEXPROCESSING,&p,&device),"CreateDevice");
#endif
converted.resize(vertices.size());for(size_t i=0;i<vertices.size();i++){auto& v=vertices[i];memcpy(converted[i].p,v.p,12);converted[i].color=(v.color&0xFF00FF00)|((v.color&255)<<16)|((v.color>>16)&255);converted[i].specular=0;memcpy(converted[i].uv,v.uv,8);}
#if BACKEND==8
hr(device->CreateVertexBuffer(UINT(converted.size()*sizeof(LegacyVertex)),D3DUSAGE_WRITEONLY,FVF,fixturePool,&vertexBuffer),"CreateVertexBuffer");BYTE* dst=nullptr;
#else
hr(device->CreateVertexBuffer(UINT(converted.size()*sizeof(LegacyVertex)),D3DUSAGE_WRITEONLY,FVF,fixturePool,&vertexBuffer,nullptr),"CreateVertexBuffer");void* dst=nullptr;
#endif
hr(vertexBuffer->Lock(0,0,&dst,0),"Vertex lock");memcpy(dst,converted.data(),converted.size()*sizeof(LegacyVertex));vertexBuffer->Unlock();
for(auto& t:textures){Tex* tex=nullptr;
#if BACKEND==8
hr(device->CreateTexture(t.w,t.h,1,textureUsage,D3DFMT_A8R8G8B8,fixturePool,&tex),"CreateTexture");
#else
hr(device->CreateTexture(t.w,t.h,1,textureUsage,D3DFMT_A8R8G8B8,fixturePool,&tex,nullptr),"CreateTexture");
#endif
D3DLOCKED_RECT lock{};hr(tex->LockRect(0,&lock,nullptr,0),"Texture lock");for(unsigned y=0;y<t.h;y++)for(unsigned x=0;x<t.w;x++){auto* s=t.pixels.data()+(size_t(y)*t.w+x)*4;auto* d=static_cast<uint8_t*>(lock.pBits)+size_t(y)*lock.Pitch+x*4;d[0]=s[2];d[1]=s[1];d[2]=s[0];d[3]=s[3];}tex->UnlockRect(0);gpuTextures.push_back(tex);}
device->SetRenderState(D3DRS_SPECULARENABLE,showcase?TRUE:FALSE);device->SetRenderState(D3DRS_FOGENABLE,showcase?TRUE:FALSE);device->SetRenderState(D3DRS_FOGCOLOR,0x00202c3a);device->SetRenderState(D3DRS_LIGHTING,FALSE);device->SetRenderState(D3DRS_CULLMODE,D3DCULL_NONE);device->SetRenderState(D3DRS_ZENABLE,TRUE);device->SetRenderState(D3DRS_ALPHATESTENABLE,TRUE);device->SetRenderState(D3DRS_ALPHAREF,127);device->SetRenderState(D3DRS_ALPHAFUNC,D3DCMP_GREATER);
device->SetTextureStageState(0,D3DTSS_COLOROP,D3DTOP_MODULATE);device->SetTextureStageState(0,D3DTSS_COLORARG1,D3DTA_TEXTURE);device->SetTextureStageState(0,D3DTSS_COLORARG2,D3DTA_DIFFUSE);device->SetTextureStageState(0,D3DTSS_ALPHAOP,D3DTOP_SELECTARG1);device->SetTextureStageState(0,D3DTSS_ALPHAARG1,D3DTA_TEXTURE);
#if BACKEND==8
device->SetTextureStageState(0,D3DTEXTURESTAGESTATETYPE(D3DTSS_MINFILTER),D3DTEXF_LINEAR);device->SetTextureStageState(0,D3DTEXTURESTAGESTATETYPE(D3DTSS_MAGFILTER),D3DTEXF_LINEAR);device->SetVertexShader(FVF);device->SetStreamSource(0,vertexBuffer,sizeof(LegacyVertex));
#else
device->SetSamplerState(0,D3DSAMP_MINFILTER,D3DTEXF_LINEAR);device->SetSamplerState(0,D3DSAMP_MAGFILTER,D3DTEXF_LINEAR);device->SetFVF(FVF);device->SetStreamSource(0,vertexBuffer,0,sizeof(LegacyVertex));
#endif
auto identity=XMMatrixIdentity();XMFLOAT4X4 m;XMStoreFloat4x4(&m,identity);device->SetTransform(D3DTS_WORLD,reinterpret_cast<const D3DMATRIX*>(&m));device->SetTransform(D3DTS_VIEW,reinterpret_cast<const D3DMATRIX*>(&m));
#if BACKEND==9
if(showcase)initShader9();
#endif

}
void drawFrame(bool capture){if(showcase && BACKEND==8){for(size_t i=0;i<vertices.size();i++){auto color=vertices[i].color;converted[i].color=(color&0xFF00FF00)|((color&255)<<16)|((color>>16)&255);converted[i].specular=vertexSpecular[i];}
#if BACKEND==8
BYTE* mapped=nullptr;
#else
void* mapped=nullptr;
#endif
hr(vertexBuffer->Lock(0,0,&mapped,0),"UpdateLitVertices");memcpy(mapped,converted.data(),converted.size()*sizeof(LegacyVertex));vertexBuffer->Unlock();}hr(device->Clear(0,nullptr,D3DCLEAR_TARGET|D3DCLEAR_ZBUFFER,0xFF202831,1,0),"Clear");device->SetTransform(D3DTS_PROJECTION,reinterpret_cast<const D3DMATRIX*>(&vp));hr(device->BeginScene(),"BeginScene");
#if BACKEND==9
if(showcase)bindShader9();
#endif
for(auto& d:draws){
#if BACKEND==9
if(showcase){for(unsigned k=0;k<3;k++)device->SetTexture(k,gpuTextures[d.texture*3+k]);device->SetTexture(3,gpuTextures[72]);}else device->SetTexture(0,gpuTextures[d.texture*3]);
#else
device->SetTexture(0,gpuTextures[d.texture]);
#endif
hr(device->DrawPrimitive(D3DPT_TRIANGLELIST,d.first,d.count/3),"DrawPrimitive");}hr(device->EndScene(),"EndScene");if(capture||captureDueNow()){Surface* back=nullptr;Surface* cpu=nullptr;
#if BACKEND==8
hr(device->GetBackBuffer(0,D3DBACKBUFFER_TYPE_MONO,&back),"GetBackBuffer");hr(device->CreateImageSurface(W,H,D3DFMT_X8R8G8B8,&cpu),"CreateImageSurface");hr(device->CopyRects(back,nullptr,0,cpu,nullptr),"CopyRects");
#else
hr(device->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back),"GetBackBuffer");hr(device->CreateOffscreenPlainSurface(W,H,D3DFMT_X8R8G8B8,D3DPOOL_SYSTEMMEM,&cpu,nullptr),"CreateOffscreenPlainSurface");hr(device->GetRenderTargetData(back,cpu),"GetRenderTargetData");
#endif
D3DLOCKED_RECT lock{};hr(cpu->LockRect(&lock,nullptr,D3DLOCK_READONLY),"Capture lock");saveCapture(static_cast<uint8_t*>(lock.pBits),lock.Pitch,true);cpu->UnlockRect();cpu->Release();back->Release();}hr(device->Present(nullptr,nullptr,nullptr,nullptr),"Present");}
void shutdownRenderer(){
#if BACKEND==9
shutdownShader9();
#endif
for(auto* t:gpuTextures)t->Release();if(vertexBuffer)vertexBuffer->Release();if(device)device->Release();if(d3d)d3d->Release();}
