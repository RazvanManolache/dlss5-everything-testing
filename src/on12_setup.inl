#include <d3d12.h>
#include <d3d11on12.h>
#include <dxgi1_4.h>
ComPtr<ID3D12Device> on12Base;
ComPtr<ID3D12CommandQueue> on12Queue;
ComPtr<ID3D11On12Device> on12Device;
ComPtr<IDXGISwapChain3> on12Swap;
ComPtr<ID3D12Resource> on12Buffers[2];
ComPtr<Tex> on12Wrapped[2];ComPtr<RTV> on12Views[2];
unsigned on12Current=0;uint64_t on12Acquires=0,on12Releases=0;
void initOn12(){
 ComPtr<IDXGIFactory4> factory;hr(CreateDXGIFactory1(IID_PPV_ARGS(&factory)),"On12 factory");ComPtr<IDXGIAdapter1> adapter;
#ifdef USE_WARP
 hr(factory->EnumWarpAdapter(IID_PPV_ARGS(&adapter)),"On12 WARP adapter");hr(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&on12Base)),"On12 WARP device");
#else
 for(UINT i=0;factory->EnumAdapters1(i,&adapter)!=DXGI_ERROR_NOT_FOUND;i++){DXGI_ADAPTER_DESC1 a{};adapter->GetDesc1(&a);if(!(a.Flags&DXGI_ADAPTER_FLAG_SOFTWARE)&&SUCCEEDED(D3D12CreateDevice(adapter.Get(),D3D_FEATURE_LEVEL_11_0,IID_PPV_ARGS(&on12Base))))break;adapter.Reset();}
#endif
 ensure(on12Base!=nullptr,"On12 underlying device");D3D12_COMMAND_QUEUE_DESC q{};q.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;hr(on12Base->CreateCommandQueue(&q,IID_PPV_ARGS(&on12Queue)),"On12 queue");IUnknown* queues[]={on12Queue.Get()};D3D_FEATURE_LEVEL level;
 hr(D3D11On12CreateDevice(on12Base.Get(),D3D11_CREATE_DEVICE_BGRA_SUPPORT,nullptr,0,queues,1,0,&device,&context,&level),"D3D11On12CreateDevice");hr(device.As(&on12Device),"ID3D11On12Device");
 DXGI_SWAP_CHAIN_DESC1 s{};s.Width=W;s.Height=H;s.Format=DXGI_FORMAT_R8G8B8A8_UNORM;s.SampleDesc.Count=1;s.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;s.BufferCount=2;s.SwapEffect=DXGI_SWAP_EFFECT_FLIP_DISCARD;ComPtr<IDXGISwapChain1> temp;hr(factory->CreateSwapChainForHwnd(on12Queue.Get(),windowHandle,&s,nullptr,nullptr,&temp),"On12 swapchain");hr(temp.As(&on12Swap),"On12 swapchain3");hr(temp.As(&swapchain),"On12 swapchain base");factory->MakeWindowAssociation(windowHandle,DXGI_MWA_NO_ALT_ENTER);
 D3D11_RESOURCE_FLAGS flags{};flags.BindFlags=D3D11_BIND_RENDER_TARGET;
 for(unsigned i=0;i<2;i++){hr(swapchain->GetBuffer(i,IID_PPV_ARGS(&on12Buffers[i])),"On12 backbuffer");hr(on12Device->CreateWrappedResource(on12Buffers[i].Get(),&flags,D3D12_RESOURCE_STATE_RENDER_TARGET,D3D12_RESOURCE_STATE_PRESENT,IID_PPV_ARGS(&on12Wrapped[i])),"CreateWrappedResource");hr(device->CreateRenderTargetView(on12Wrapped[i].Get(),nullptr,&on12Views[i]),"On12 view");}
 rendererInfo={{"creation","D3D11On12CreateDevice"},{"device_interface","ID3D11On12Device"},{"wrapped_resources",2},{"feature_level",level}};
}
void on12Begin(){on12Current=on12Swap->GetCurrentBackBufferIndex();back=on12Wrapped[on12Current];rtv=on12Views[on12Current];ID3D11Resource* resources[]={back.Get()};on12Device->AcquireWrappedResources(resources,1);rendererInfo["acquire_wrapped_calls"]=++on12Acquires;}
void on12End(){context->OMSetRenderTargets(0,nullptr,nullptr);ID3D11Resource* resources[]={back.Get()};on12Device->ReleaseWrappedResources(resources,1);context->Flush();rendererInfo["release_wrapped_calls"]=++on12Releases;}
void on12Wait(){ComPtr<ID3D12Fence> fence;hr(on12Base->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_PPV_ARGS(&fence)),"On12 fence");hr(on12Queue->Signal(fence.Get(),1),"On12 signal");HANDLE e=CreateEvent(nullptr,FALSE,FALSE,nullptr);ensure(e!=nullptr,"On12 fence event");hr(fence->SetEventOnCompletion(1,e),"On12 completion");DWORD waited=WaitForSingleObject(e,30000);CloseHandle(e);ensure(waited==WAIT_OBJECT_0,"On12 GPU timeout");}
