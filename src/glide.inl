// Minimal ABI declarations for the original Glide entry points. Numeric values
// and vertex layout follow the released 3dfx headers retained under vendor.
#include "cpu_projection.inl"
struct GlideTextureInfo{int smallLod,largeLod,aspect,format;void* data;};
struct GlideVertex{float x,y,z,r,g,b,ooz,a,oow;struct{float s,t,q;} tmu[3];};
extern "C" {
__declspec(dllimport) void WINAPI grGlideInit();
__declspec(dllimport) void WINAPI grGlideShutdown();
#if GLIDE_VERSION<3
__declspec(dllimport) void WINAPI grGlideGetVersion(char*);
#else
__declspec(dllimport) const char* WINAPI grGetString(int);
#endif
__declspec(dllimport) int WINAPI grSstQueryHardware(void*);
__declspec(dllimport) void WINAPI grSstSelect(int);
#if GLIDE_VERSION==1
__declspec(dllimport) int WINAPI grSstOpen(int,int,int,int,int,int);
#else
__declspec(dllimport) uintptr_t WINAPI grSstWinOpen(uintptr_t,int,int,int,int,int,int);
#endif
__declspec(dllimport) void WINAPI grRenderBuffer(int);
__declspec(dllimport) void WINAPI grBufferClear(uint32_t,uint32_t,uint16_t);
__declspec(dllimport) void WINAPI grBufferSwap(int);
__declspec(dllimport) void WINAPI grClipWindow(uint32_t,uint32_t,uint32_t,uint32_t);
__declspec(dllimport) void WINAPI grCullMode(int);
__declspec(dllimport) void WINAPI grDepthBufferMode(int);
__declspec(dllimport) void WINAPI grDepthBufferFunction(int);
__declspec(dllimport) void WINAPI grDepthMask(int);
__declspec(dllimport) void WINAPI grColorCombine(int,int,int,int,int);
__declspec(dllimport) void WINAPI grAlphaCombine(int,int,int,int,int);
__declspec(dllimport) void WINAPI grAlphaTestFunction(int);
__declspec(dllimport) void WINAPI grAlphaTestReferenceValue(uint8_t);
__declspec(dllimport) void WINAPI grTexCombine(int,int,int,int,int,int,int);
__declspec(dllimport) void WINAPI grTexFilterMode(int,int,int);
__declspec(dllimport) void WINAPI grTexClampMode(int,int,int);
__declspec(dllimport) void WINAPI grTexMipMapMode(int,int,int);
__declspec(dllimport) uint32_t WINAPI grTexMinAddress(int);
__declspec(dllimport) uint32_t WINAPI grTexMaxAddress(int);
__declspec(dllimport) uint32_t WINAPI grTexTextureMemRequired(uint32_t,const GlideTextureInfo*);
__declspec(dllimport) void WINAPI grTexDownloadMipMap(int,uint32_t,uint32_t,const GlideTextureInfo*);
__declspec(dllimport) void WINAPI grTexSource(int,uint32_t,uint32_t,const GlideTextureInfo*);
__declspec(dllimport) void WINAPI grDrawTriangle(const GlideVertex*,const GlideVertex*,const GlideVertex*);
__declspec(dllimport) int WINAPI grLfbReadRegion(int,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,void*);
#if GLIDE_VERSION==3
__declspec(dllimport) void WINAPI grVertexLayout(int,int,int);
__declspec(dllimport) void WINAPI grCoordinateSpace(int);
#endif
}
std::array<GlideTextureInfo,24> glideTextures;std::array<unsigned,24> glideParts;std::array<std::vector<uint16_t>,72> glidePixels;std::array<uint32_t,3> glideAddresses;uint64_t glideTriangleCalls=0;
void initRenderer(){
 grGlideInit();char version[128]{};
#if GLIDE_VERSION<3
 grGlideGetVersion(version);
#else
 const char* text=grGetString(0xA4);if(text)strncpy_s(version,text,_TRUNCATE);
#endif
 gpuName="dgVoodoo / "+std::string(version);
#if GLIDE_VERSION<3
 std::array<uint8_t,4096> hardware{};ensure(grSstQueryHardware(hardware.data())!=0,"Glide hardware query");
#endif
 grSstSelect(0);
#if GLIDE_VERSION==1
 // Glide 2.11 has no HWND argument. The wrapper uses this thread's active window.
 if(isolatedBackground)SetActiveWindow(windowHandle);
 ensure(grSstOpen(0xA,0,0,0,2,1)!=0,"Glide grSstOpen");W=856;H=480;
#else
 ensure(grSstWinOpen(reinterpret_cast<uintptr_t>(windowHandle),0xA,0,0,0,2,1)!=0,"Glide grSstWinOpen");W=856;H=480;
#endif
 grRenderBuffer(1);grClipWindow(0,0,W,H);grCullMode(0);grDepthBufferMode(1);grDepthBufferFunction(3);grDepthMask(1);grColorCombine(3,1,0,1,0);grAlphaCombine(3,8,0,1,0);grAlphaTestFunction(4);grAlphaTestReferenceValue(127);grTexCombine(0,1,0,1,0,0,0);grTexFilterMode(0,1,1);grTexClampMode(0,0,0);grTexMipMapMode(0,0,0);
#if GLIDE_VERSION==3
 grCoordinateSpace(0);grVertexLayout(1,0,1);grVertexLayout(2,24,1);grVertexLayout(4,32,1);grVertexLayout(0x20,12,1);grVertexLayout(0x10,28,1);grVertexLayout(0x40,36,1);grVertexLayout(0x50,44,1);
#endif
 uint32_t address=grTexMinAddress(0),maxAddress=grTexMaxAddress(0);
 for(unsigned m=0;m<24;m++){
  auto& t=textures[m];unsigned parts=(m<18&&t.w>=t.h*2.9)?3:1;glideParts[m]=parts;
  for(unsigned part=0;part<parts;part++){
   auto& pixels=glidePixels[m*3+part];pixels.resize(256*256);
   for(unsigned y=0;y<256;y++)for(unsigned x=0;x<256;x++){unsigned sx0=std::min(t.w-1,unsigned(((part+x/256.f)*t.w)/parts)),sx1=std::min(t.w,std::max(sx0+1,unsigned(((part+(x+1)/256.f)*t.w)/parts)));unsigned sy0=std::min(t.h-1,unsigned(y*t.h/256.f)),sy1=std::min(t.h,std::max(sy0+1,unsigned((y+1)*t.h/256.f)));unsigned sum[4]{};for(unsigned sy=sy0;sy<sy1;sy++)for(unsigned sx=sx0;sx<sx1;sx++){const auto* texel=&t.pixels[(size_t(sy)*t.w+sx)*4];for(unsigned k=0;k<4;k++)sum[k]+=texel[k];}unsigned count=(sx1-sx0)*(sy1-sy0);for(auto& value:sum)value/=count;pixels[y*256+x]=uint16_t((sum[3]>=128?0x8000:0)|((sum[0]>>3)<<10)|((sum[1]>>3)<<5)|(sum[2]>>3));}
  }
#if GLIDE_VERSION==3
  GlideTextureInfo info{8,8,0,0xb,nullptr};
#else
  GlideTextureInfo info{0,0,3,0xb,nullptr};
#endif
  uint32_t size=grTexTextureMemRequired(3,&info);ensure(size>0&&address+size*3<=maxAddress,"Glide texture cache memory");for(unsigned part=0;part<3;part++)glideAddresses[part]=address+size*part;glideTextures[m]=info;textureInventory[m]["applied_width"]=256;textureInventory[m]["applied_height"]=256;textureInventory[m]["atlas_parts"]=parts;t.pixels.clear();t.pixels.shrink_to_fit();
 }
 rendererInfo={{"glide_version",GLIDE_VERSION},{"glide_runtime",version},{"transport","dgVoodoo D3D11"},{"triangle_calls",0},{"texture_count",24},{"texture_format","ARGB1555; streamed atlas regions"},{"maximum_texture_dimension",256},{"internal_width",W},{"internal_height",H},{"creation",GLIDE_VERSION==1?"grSstOpen":"grSstWinOpen"}};
}
GlideVertex glideVertex(const ScreenVertex& in){GlideVertex v{};v.x=in.sx;v.y=in.sy;v.ooz=in.sz*65535;v.oow=in.rhw;v.r=float((in.color>>16)&255);v.g=float((in.color>>8)&255);v.b=float(in.color&255);v.a=255;
 if(showcase){float fog=float(in.specular>>24)/255;float* channels[]={&v.r,&v.g,&v.b};float fogColor[]={32,44,58};for(unsigned k=0;k<3;k++){float spec=float((in.specular>>((2-k)*8))&255);*channels[k]=std::clamp((*channels[k]+spec)*fog+fogColor[k]*(1-fog),0.f,255.f);}}
 v.tmu[0]={in.tu*256*in.rhw,in.tv*256*in.rhw,in.rhw};return v;
}
void drawFrame(bool capture){
 grBufferClear(0x00202831,255,65535);projectScene();
 for(unsigned m=0;m<24;m++){
  auto& batch=batches[m];if(batch.empty())continue;
  for(unsigned part=0;part<glideParts[m];part++){auto info=glideTextures[m];info.data=glidePixels[m*3+part].data();grTexDownloadMipMap(0,glideAddresses[part],3,&info);}
  int current=-1;
  for(size_t i=0;i<batch.size();i+=3){ScreenVertex p[3]={batch[i],batch[i+1],batch[i+2]};unsigned part=glideParts[m]>1?std::min(2u,unsigned(std::max(0.f,(p[0].tu+p[1].tu+p[2].tu)))):0;
   if(int(part)!=current){grTexSource(0,glideAddresses[part],3,&glideTextures[m]);current=part;}
   if(glideParts[m]>1)for(auto& v:p)v.tu=v.tu*3-part;
   auto a=glideVertex(p[0]),b=glideVertex(p[1]),c=glideVertex(p[2]);grDrawTriangle(&a,&b,&c);++glideTriangleCalls;
  }
 }
 if(capture||captureDueNow()){std::vector<uint16_t> raw(size_t(W)*H);ensure(grLfbReadRegion(1,0,0,W,H,W*2,raw.data())!=0,"Glide LFB screenshot");std::vector<uint8_t> pixels(size_t(W)*H*4);for(size_t i=0;i<raw.size();i++){pixels[i*4]=uint8_t(((raw[i]>>11)&31)*255/31);pixels[i*4+1]=uint8_t(((raw[i]>>5)&63)*255/63);pixels[i*4+2]=uint8_t((raw[i]&31)*255/31);pixels[i*4+3]=255;}saveCapture(pixels.data(),W*4);}
 grBufferSwap(0);rendererInfo["triangle_calls"]=glideTriangleCalls;
}
void shutdownRenderer(){grGlideShutdown();}
