// Encode the renderer's own readback without taking a desktop screenshot.
#include <wincodec.h>
#include <wrl/client.h>
void savePng(const uint8_t* pixels,size_t pitch,bool bgra,bool bottomUp,const fs::path& filename){
 using Microsoft::WRL::ComPtr;
 HRESULT apartment=CoInitializeEx(nullptr,COINIT_MULTITHREADED);
 ensure(SUCCEEDED(apartment)||apartment==RPC_E_CHANGED_MODE,"Initialize screenshot encoder");
 {
  ComPtr<IWICImagingFactory> factory;ComPtr<IWICStream> stream;ComPtr<IWICBitmapEncoder> encoder;ComPtr<IWICBitmapFrameEncode> frame;
  hr(CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(factory.GetAddressOf())),"PNG factory");
  hr(factory->CreateStream(stream.GetAddressOf()),"PNG stream");hr(stream->InitializeFromFilename((output/filename).c_str(),GENERIC_WRITE),"PNG output");
  hr(factory->CreateEncoder(GUID_ContainerFormatPng,nullptr,encoder.GetAddressOf()),"PNG encoder");hr(encoder->Initialize(stream.Get(),WICBitmapEncoderNoCache),"PNG initialize");
  hr(encoder->CreateNewFrame(frame.GetAddressOf(),nullptr),"PNG frame");hr(frame->Initialize(nullptr),"PNG frame initialize");hr(frame->SetSize(W,H),"PNG size");
  WICPixelFormatGUID format=GUID_WICPixelFormat24bppBGR;hr(frame->SetPixelFormat(&format),"PNG pixel format");ensure(IsEqualGUID(format,GUID_WICPixelFormat24bppBGR),"PNG BGR encoding");
  std::vector<uint8_t> row(size_t(W)*3);
  for(unsigned y=0;y<H;y++){
   const uint8_t* src=pixels+(bottomUp?H-1-y:y)*pitch;
   for(unsigned x=0;x<W;x++){row[x*3]=src[x*4+(bgra?0:2)];row[x*3+1]=src[x*4+1];row[x*3+2]=src[x*4+(bgra?2:0)];}
   hr(frame->WritePixels(1,W*3,W*3,row.data()),"PNG pixels");
  }
  hr(frame->Commit(),"PNG frame commit");hr(encoder->Commit(),"PNG commit");
 }
 if(SUCCEEDED(apartment))CoUninitialize();
}
