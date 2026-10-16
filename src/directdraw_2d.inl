// Pure surface application: the CPU rasterizes the scene; no Direct3D device exists.
#include <ddraw.h>
#include "cpu_projection.inl"
#if DD_VERSION==1
using DD=IDirectDraw;using Surface=IDirectDrawSurface;using Desc=DDSURFACEDESC;
#elif DD_VERSION==2
using DD=IDirectDraw2;using Surface=IDirectDrawSurface;using Desc=DDSURFACEDESC;
#elif DD_VERSION==4
using DD=IDirectDraw4;using Surface=IDirectDrawSurface4;using Desc=DDSURFACEDESC2;
#else
using DD=IDirectDraw7;using Surface=IDirectDrawSurface7;using Desc=DDSURFACEDESC2;
#endif
DD* ddraw{};Surface* primary{};Surface* target{};IDirectDrawClipper* ddClipper{};
std::vector<Texture> cpuTextures;std::vector<uint8_t> rasterPixels;std::vector<float> rasterDepth;uint64_t surfaceBlits=0;
void initRenderer(){
#if DD_VERSION==7
 hr(DirectDrawCreateEx(nullptr,reinterpret_cast<void**>(&ddraw),IID_IDirectDraw7,nullptr),"2D DirectDrawCreateEx");
#else
 IDirectDraw* base{};hr(DirectDrawCreate(nullptr,&base,nullptr),"2D DirectDrawCreate");
#if DD_VERSION==1
 ddraw=base;
#elif DD_VERSION==2
 hr(base->QueryInterface(IID_IDirectDraw2,reinterpret_cast<void**>(&ddraw)),"2D Query DirectDraw2");base->Release();
#else
 hr(base->QueryInterface(IID_IDirectDraw4,reinterpret_cast<void**>(&ddraw)),"2D Query DirectDraw4");base->Release();
#endif
#endif
 hr(ddraw->SetCooperativeLevel(windowHandle,DDSCL_NORMAL),"2D cooperative level");Desc d{};d.dwSize=sizeof(d);d.dwFlags=DDSD_CAPS;d.ddsCaps.dwCaps=DDSCAPS_PRIMARYSURFACE;hr(ddraw->CreateSurface(&d,&primary,nullptr),"2D primary");hr(ddraw->CreateClipper(0,&ddClipper,nullptr),"2D clipper");hr(ddClipper->SetHWnd(0,windowHandle),"2D clipper window");hr(primary->SetClipper(ddClipper),"2D primary clipper");
 d={};d.dwSize=sizeof(d);d.dwFlags=DDSD_CAPS|DDSD_WIDTH|DDSD_HEIGHT|DDSD_PIXELFORMAT;d.dwWidth=W;d.dwHeight=H;d.ddsCaps.dwCaps=DDSCAPS_OFFSCREENPLAIN|DDSCAPS_SYSTEMMEMORY;d.ddpfPixelFormat.dwSize=sizeof(DDPIXELFORMAT);d.ddpfPixelFormat.dwFlags=DDPF_RGB;d.ddpfPixelFormat.dwRGBBitCount=32;d.ddpfPixelFormat.dwRBitMask=0x00FF0000;d.ddpfPixelFormat.dwGBitMask=0x0000FF00;d.ddpfPixelFormat.dwBBitMask=0x000000FF;hr(ddraw->CreateSurface(&d,&target,nullptr),"2D software surface");
 cpuTextures=std::move(textures);rasterPixels.resize(size_t(W)*H*4);rasterDepth.resize(size_t(W)*H);gpuName="CPU rasterizer + DirectDraw surface blits";rendererInfo={{"directdraw_version",DD_VERSION},{"direct3d_device_created",false},{"rasterizer","CPU perspective-correct textured triangles"},{"surface_memory","system"},{"texture_count",cpuTextures.size()}};
}
float edge(float ax,float ay,float bx,float by,float x,float y){return (bx-ax)*(y-ay)-(by-ay)*(x-ax);}
void rasterize(const ScreenVertex& a,const ScreenVertex& b,const ScreenVertex& c,const Texture& t){
 float area=edge(a.sx,a.sy,b.sx,b.sy,c.sx,c.sy);if(fabsf(area)<1.e-7f)return;
 int x0=std::max(0,int(floorf(std::min({a.sx,b.sx,c.sx})))),x1=std::min(int(W)-1,int(ceilf(std::max({a.sx,b.sx,c.sx}))));int y0=std::max(0,int(floorf(std::min({a.sy,b.sy,c.sy})))),y1=std::min(int(H)-1,int(ceilf(std::max({a.sy,b.sy,c.sy}))));
 float invArea=1/area;
 for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++){
  float wa=edge(b.sx,b.sy,c.sx,c.sy,x+.5f,y+.5f)*invArea,wb=edge(c.sx,c.sy,a.sx,a.sy,x+.5f,y+.5f)*invArea,wc=1-wa-wb;if(wa<0||wb<0||wc<0)continue;float z=wa*a.sz+wb*b.sz+wc*c.sz;size_t at=size_t(y)*W+x;if(z>rasterDepth[at])continue;
  float inv=1/(wa*a.rhw+wb*b.rhw+wc*c.rhw),pa=wa*a.rhw*inv,pb=wb*b.rhw*inv,pc=wc*c.rhw*inv;
  float u=pa*a.tu+pb*b.tu+pc*c.tu,v=pa*a.tv+pb*b.tv+pc*c.tv;u=(u-floorf(u))*t.w-.5f;v=(v-floorf(v))*t.h-.5f;int tx=int(floorf(u)),ty=int(floorf(v));float fx=u-floorf(u),fy=v-floorf(v);unsigned ax=(tx+int(t.w))%t.w,ay=(ty+int(t.h))%t.h,bx=(ax+1)%t.w,by=(ay+1)%t.h;
  const uint8_t* p00=&t.pixels[(size_t(ay)*t.w+ax)*4];const uint8_t* p10=&t.pixels[(size_t(ay)*t.w+bx)*4];const uint8_t* p01=&t.pixels[(size_t(by)*t.w+ax)*4];const uint8_t* p11=&t.pixels[(size_t(by)*t.w+bx)*4];float sample[4];for(unsigned k=0;k<4;k++)sample[k]=(p00[k]*(1-fx)+p10[k]*fx)*(1-fy)+(p01[k]*(1-fx)+p11[k]*fx)*fy;if(sample[3]<127.5f)continue;
  for(unsigned k=0;k<3;k++){unsigned shift=(2-k)*8;float tint=pa*((a.color>>shift)&255)+pb*((b.color>>shift)&255)+pc*((c.color>>shift)&255);float value=sample[k]*tint/255;
   if(showcase){value+=wa*((a.specular>>shift)&255)+wb*((b.specular>>shift)&255)+wc*((c.specular>>shift)&255);float fog=(wa*(a.specular>>24)+wb*(b.specular>>24)+wc*(c.specular>>24))/255;const float fogColor[]={32,44,58};value=value*fog+fogColor[k]*(1-fog);}rasterPixels[at*4+k]=uint8_t(std::clamp(value,0.f,255.f)+.5f);}
  rasterPixels[at*4+3]=255;rasterDepth[at]=z;
 }
}
void drawFrame(bool capture){
 for(size_t i=0;i<rasterDepth.size();i++){rasterDepth[i]=1;rasterPixels[i*4]=32;rasterPixels[i*4+1]=40;rasterPixels[i*4+2]=49;rasterPixels[i*4+3]=255;}
 projectScene();for(unsigned m=0;m<24;m++){auto& b=batches[m];for(size_t i=0;i<b.size();i+=3)rasterize(b[i],b[i+1],b[i+2],cpuTextures[m]);}
 Desc lock{};lock.dwSize=sizeof(lock);hr(target->Lock(nullptr,&lock,DDLOCK_WAIT,nullptr),"2D lock");for(unsigned y=0;y<H;y++){auto* dest=static_cast<uint8_t*>(lock.lpSurface)+size_t(y)*lock.lPitch;auto* src=&rasterPixels[size_t(y)*W*4];for(unsigned x=0;x<W;x++){dest[x*4]=src[x*4+2];dest[x*4+1]=src[x*4+1];dest[x*4+2]=src[x*4];dest[x*4+3]=255;}}hr(target->Unlock(nullptr),"2D unlock");
 if(capture||captureDueNow()){lock={};lock.dwSize=sizeof(lock);hr(target->Lock(nullptr,&lock,DDLOCK_WAIT|DDLOCK_READONLY,nullptr),"2D capture lock");saveCapture(static_cast<uint8_t*>(lock.lpSurface),lock.lPitch,true);hr(target->Unlock(nullptr),"2D capture unlock");}
 RECT dest{0,0,LONG(clientWidth),LONG(clientHeight)};POINT origin{};ClientToScreen(windowHandle,&origin);OffsetRect(&dest,origin.x,origin.y);hr(primary->Blt(&dest,target,nullptr,DDBLT_WAIT,nullptr),"2D surface Blt");rendererInfo["surface_blt_calls"]=++surfaceBlits;rendererInfo["triangles_per_frame"]=vertices.size()/3;
}
void shutdownRenderer(){if(target)target->Release();if(primary)primary->Release();if(ddClipper)ddClipper->Release();if(ddraw)ddraw->Release();}
