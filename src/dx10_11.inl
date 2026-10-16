#include "shader.h"
#if BACKEND==10
#ifdef USE_DX10_1
#include <d3d10_1.h>
#else
#include <d3d10.h>
#endif
#ifdef USE_DX10_1
using Device=ID3D10Device1;
#else
using Device=ID3D10Device;
#endif
using Context=ID3D10Device;using Tex=ID3D10Texture2D;using SRV=ID3D10ShaderResourceView;using Buffer=ID3D10Buffer;using RTV=ID3D10RenderTargetView;using DSV=ID3D10DepthStencilView;using VS=ID3D10VertexShader;using PS=ID3D10PixelShader;using Layout=ID3D10InputLayout;using Sampler=ID3D10SamplerState;using Raster=ID3D10RasterizerState;
#define API(x) D3D10_##x
#else
#include <d3d11.h>
using Device=ID3D11Device;using Context=ID3D11DeviceContext;using Tex=ID3D11Texture2D;using SRV=ID3D11ShaderResourceView;using Buffer=ID3D11Buffer;using RTV=ID3D11RenderTargetView;using DSV=ID3D11DepthStencilView;using VS=ID3D11VertexShader;using PS=ID3D11PixelShader;using Layout=ID3D11InputLayout;using Sampler=ID3D11SamplerState;using Raster=ID3D11RasterizerState;
#define API(x) D3D11_##x
#endif
ComPtr<Device> device;ComPtr<Context> context;ComPtr<IDXGISwapChain> swapchain;ComPtr<Tex> back,depth;ComPtr<RTV> rtv;ComPtr<DSV> dsv;ComPtr<Buffer> vb,cb;ComPtr<VS> vs;ComPtr<PS> ps;ComPtr<Layout> layout;ComPtr<Sampler> sampler;ComPtr<Raster> raster;std::vector<ComPtr<SRV>> gpuTextures;
#ifdef USE_D3D11ON12
#include "on12_setup.inl"
#endif
void initRenderer(){DXGI_SWAP_CHAIN_DESC sc{};sc.BufferDesc.Width=W;sc.BufferDesc.Height=H;sc.BufferDesc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;sc.SampleDesc.Count=1;sc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;sc.BufferCount=2;sc.OutputWindow=windowHandle;sc.Windowed=TRUE;sc.SwapEffect=DXGI_SWAP_EFFECT_DISCARD;
#if BACKEND==10
#ifdef USE_WARP
constexpr auto driver=D3D10_DRIVER_TYPE_WARP;
#else
constexpr auto driver=D3D10_DRIVER_TYPE_HARDWARE;
#endif
#ifdef USE_DX10_1
hr(D3D10CreateDevice1(nullptr,driver,nullptr,0,D3D10_FEATURE_LEVEL_10_1,D3D10_1_SDK_VERSION,&device),"D3D10CreateDevice1");
ComPtr<IDXGIDevice> x;hr(device.As(&x),"DXGI device 10.1");ComPtr<IDXGIAdapter> adapter10_1;hr(x->GetAdapter(&adapter10_1),"Adapter 10.1");ComPtr<IDXGIFactory> f;hr(adapter10_1->GetParent(IID_PPV_ARGS(&f)),"Factory 10.1");hr(f->CreateSwapChain(device.Get(),&sc,&swapchain),"Swapchain 10.1");rendererInfo["creation"]="D3D10CreateDevice1";rendererInfo["feature_level"]=device->GetFeatureLevel();
#else
hr(D3D10CreateDeviceAndSwapChain(nullptr,driver,nullptr,0,D3D10_SDK_VERSION,&sc,&swapchain,&device),"D3D10CreateDeviceAndSwapChain");
#endif
context=device;
#else
#ifdef USE_D3D11ON12
initOn12();
#else
#ifdef USE_WARP
constexpr auto driver=D3D_DRIVER_TYPE_WARP;
#else
constexpr auto driver=D3D_DRIVER_TYPE_HARDWARE;
#endif
hr(D3D11CreateDeviceAndSwapChain(nullptr,driver,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&sc,&swapchain,&device,nullptr,&context),"D3D11CreateDeviceAndSwapChain");
#endif
#endif
ComPtr<IDXGIDevice> dx;hr(device.As(&dx),"Query DXGI device");ComPtr<IDXGIAdapter> adapter;dx->GetAdapter(&adapter);DXGI_ADAPTER_DESC a{};adapter->GetDesc(&a);gpuName=fs::path(a.Description).u8string();
#ifdef USE_WARP
rendererInfo["software_renderer"]=true;rendererInfo["driver"]="WARP";
#endif
#ifdef USE_D3D11ON12
back=on12Wrapped[0];rtv=on12Views[0];
#else
hr(swapchain->GetBuffer(0,IID_PPV_ARGS(&back)),"GetBuffer");hr(device->CreateRenderTargetView(back.Get(),nullptr,&rtv),"CreateRenderTargetView");
#endif
API(TEXTURE2D_DESC) td{};td.Width=W;td.Height=H;td.MipLevels=1;td.ArraySize=1;td.Format=DXGI_FORMAT_D24_UNORM_S8_UINT;td.SampleDesc.Count=1;td.BindFlags=API(BIND_DEPTH_STENCIL);hr(device->CreateTexture2D(&td,nullptr,&depth),"CreateDepth");hr(device->CreateDepthStencilView(depth.Get(),nullptr,&dsv),"CreateDSV");
auto v=compileShader("vsMain","vs_4_0"),p=compileShader("psMain","ps_4_0");
#if BACKEND==10
hr(device->CreateVertexShader(v->GetBufferPointer(),v->GetBufferSize(),&vs),"CreateVS");hr(device->CreatePixelShader(p->GetBufferPointer(),p->GetBufferSize(),&ps),"CreatePS");
#else
hr(device->CreateVertexShader(v->GetBufferPointer(),v->GetBufferSize(),nullptr,&vs),"CreateVS");hr(device->CreatePixelShader(p->GetBufferPointer(),p->GetBufferSize(),nullptr,&ps),"CreatePS");
#endif
API(INPUT_ELEMENT_DESC) input[]={{"POSITION",0,DXGI_FORMAT_R32G32B32_FLOAT,0,0,API(INPUT_PER_VERTEX_DATA),0},{"COLOR",0,DXGI_FORMAT_R8G8B8A8_UNORM,0,12,API(INPUT_PER_VERTEX_DATA),0},{"TEXCOORD",0,DXGI_FORMAT_R32G32_FLOAT,0,16,API(INPUT_PER_VERTEX_DATA),0},{"NORMAL",0,DXGI_FORMAT_R32G32B32_FLOAT,0,24,API(INPUT_PER_VERTEX_DATA),0},{"TANGENT",0,DXGI_FORMAT_R32G32B32A32_FLOAT,0,36,API(INPUT_PER_VERTEX_DATA),0},{"COLOR",1,DXGI_FORMAT_R32G32B32_FLOAT,0,52,API(INPUT_PER_VERTEX_DATA),0},{"TEXCOORD",1,DXGI_FORMAT_R32G32B32A32_FLOAT,0,64,API(INPUT_PER_VERTEX_DATA),0}};hr(device->CreateInputLayout(input,7,v->GetBufferPointer(),v->GetBufferSize(),&layout),"CreateInputLayout");API(BUFFER_DESC) bd{};bd.ByteWidth=UINT(litVertices.size()*sizeof(LitVertex));bd.Usage=API(USAGE_DEFAULT);bd.BindFlags=API(BIND_VERTEX_BUFFER);API(SUBRESOURCE_DATA) initial{};initial.pSysMem=litVertices.data();hr(device->CreateBuffer(&bd,&initial,&vb),"CreateVB");bd.ByteWidth=sizeof(CameraConstants);bd.BindFlags=API(BIND_CONSTANT_BUFFER);hr(device->CreateBuffer(&bd,nullptr,&cb),"CreateCB");
for(auto& t:textures){td.Width=t.w;td.Height=t.h;td.Format=DXGI_FORMAT_R8G8B8A8_UNORM;td.BindFlags=API(BIND_SHADER_RESOURCE);initial.pSysMem=t.pixels.data();initial.SysMemPitch=t.w*4;ComPtr<Tex> tex;hr(device->CreateTexture2D(&td,&initial,&tex),"CreateTexture");ComPtr<SRV> srv;hr(device->CreateShaderResourceView(tex.Get(),nullptr,&srv),"CreateSRV");gpuTextures.push_back(srv);t.pixels.clear();t.pixels.shrink_to_fit();}API(SAMPLER_DESC) sd{};sd.Filter=showcase?API(FILTER_ANISOTROPIC):API(FILTER_MIN_MAG_MIP_LINEAR);sd.MaxAnisotropy=16;sd.AddressU=sd.AddressV=sd.AddressW=API(TEXTURE_ADDRESS_WRAP);sd.MaxLOD=API(FLOAT32_MAX);hr(device->CreateSamplerState(&sd,&sampler),"CreateSampler");API(RASTERIZER_DESC) rd{};rd.FillMode=API(FILL_SOLID);rd.CullMode=API(CULL_NONE);rd.DepthClipEnable=TRUE;hr(device->CreateRasterizerState(&rd,&raster),"CreateRasterizer");}
void drawFrame(bool capture){
#ifdef USE_D3D11ON12
on12Begin();
#endif
context->UpdateSubresource(cb.Get(),0,nullptr,&cameraConstants,0,0);RTV* rt=rtv.Get();context->OMSetRenderTargets(1,&rt,dsv.Get());float color[]={32/255.f,40/255.f,49/255.f,1};context->ClearRenderTargetView(rt,color);context->ClearDepthStencilView(dsv.Get(),API(CLEAR_DEPTH),1,0);API(VIEWPORT) viewport{};viewport.Width=decltype(viewport.Width)(W);viewport.Height=decltype(viewport.Height)(H);viewport.MaxDepth=1;context->RSSetViewports(1,&viewport);context->RSSetState(raster.Get());context->IASetInputLayout(layout.Get());context->IASetPrimitiveTopology(API(PRIMITIVE_TOPOLOGY_TRIANGLELIST));UINT stride=sizeof(LitVertex),offset=0;Buffer* b=vb.Get();context->IASetVertexBuffers(0,1,&b,&stride,&offset);b=cb.Get();context->VSSetConstantBuffers(0,1,&b);context->PSSetConstantBuffers(0,1,&b);Sampler* s=sampler.Get();context->PSSetSamplers(0,1,&s);
#if BACKEND==10
context->VSSetShader(vs.Get());context->PSSetShader(ps.Get());
#else
context->VSSetShader(vs.Get(),nullptr,0);context->PSSetShader(ps.Get(),nullptr,0);
#endif
for(auto& d:draws){SRV* srv[]={gpuTextures[d.texture*3].Get(),gpuTextures[d.texture*3+1].Get(),gpuTextures[d.texture*3+2].Get(),gpuTextures[72].Get()};context->PSSetShaderResources(0,4,srv);context->Draw(d.count,d.first);}
#if defined(USE_D3D11ON12) && defined(USE_WARP)
context->Flush();on12Wait();
#endif
if(capture||captureDueNow()){API(TEXTURE2D_DESC) desc{};back->GetDesc(&desc);desc.BindFlags=0;desc.MiscFlags=0;desc.Usage=API(USAGE_STAGING);desc.CPUAccessFlags=API(CPU_ACCESS_READ);ComPtr<Tex> cpu;hr(device->CreateTexture2D(&desc,nullptr,&cpu),"CreateReadback");context->CopyResource(cpu.Get(),back.Get());
#if BACKEND==10
D3D10_MAPPED_TEXTURE2D map{};hr(cpu->Map(0,D3D10_MAP_READ,0,&map),"MapReadback");saveCapture(static_cast<uint8_t*>(map.pData),map.RowPitch);cpu->Unmap(0);
#else
D3D11_MAPPED_SUBRESOURCE map{};hr(context->Map(cpu.Get(),0,D3D11_MAP_READ,0,&map),"MapReadback");saveCapture(static_cast<uint8_t*>(map.pData),map.RowPitch);context->Unmap(cpu.Get(),0);
#endif
}
#ifdef USE_D3D11ON12
on12End();
#endif
hr(swapchain->Present(0,0),"Present");}
void shutdownRenderer(){context->ClearState();context->Flush();
#ifdef USE_D3D11ON12
on12Wait();
#endif
}
#undef API
