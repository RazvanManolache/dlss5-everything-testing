#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <tlhelp32.h>
#include <shellapi.h>
#include <DirectXMath.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <stdexcept>
#include "json.hpp"
using Json=nlohmann::json;
namespace fs=std::filesystem;
using namespace DirectX;
using Clock=std::chrono::steady_clock;
#ifndef BACKEND
#error Each executable must select exactly one BACKEND at compile time.
#endif
#ifndef API_NAME
#error API_NAME is required
#endif
constexpr unsigned WDEFAULT=1920,HDEFAULT=1080;
unsigned W=WDEFAULT,H=HDEFAULT;
unsigned clientWidth=WDEFAULT,clientHeight=HDEFAULT;
HWND windowHandle{};
fs::path output,assetDirectory;
fs::path findAssets(){
 for(auto parent=fs::current_path();;parent=parent.parent_path()){
  if(fs::is_regular_file(parent/"assets/museum.bin"))return parent/"assets";
  std::ifstream marker(parent/"ASSETS.TXT");std::string relative;
  if(marker&&std::getline(marker,relative)){
   if(!relative.empty()&&relative.back()=='\r')relative.pop_back();
   fs::path path=fs::u8path(relative);
   if(path.is_absolute())throw std::runtime_error("ASSETS.TXT must contain a relative path");
   if(fs::is_regular_file(parent/path/"museum.bin"))return parent/path;
  }
  if(fs::is_regular_file(parent/"shared-assets/museum.bin"))return parent/"shared-assets";
  if(parent==parent.root_path())break;
 }
 throw std::runtime_error("Cannot find common museum assets relative to executable");
}
fs::path assetPath(const fs::path& path){auto first=path.begin();return first!=path.end()&&*first=="assets"?assetDirectory/path.lexically_relative("assets"):path;}
bool paused=false,room=false,running=true;
uint64_t frameLimit=0,frameNumber=0,captureFrame=30;
float simulationTime=0;
bool fixedTime=false,wantCapture=false;
bool showcase=true,windowed=false,bakeShadow=false;
XMFLOAT3 cameraEye{};
struct Vertex{float p[3];uint32_t color;float uv[2];};
static_assert(sizeof(Vertex)==24);
struct Draw{uint32_t first,count,texture;};
struct Texture{unsigned w,h;std::vector<uint8_t> pixels;};
std::vector<Vertex> vertices;
std::vector<Draw> draws;
std::vector<Texture> textures;
struct Shading{float normal[3],tangent[4],base[3],params[4];};
struct LitVertex{Vertex vertex;Shading shading;};
static_assert(sizeof(Shading)==56&&sizeof(LitVertex)==80);
std::vector<Shading> shading;
std::vector<LitVertex> litVertices;
struct CameraConstants{XMFLOAT4X4 vp;XMFLOAT4 eye,options;};
CameraConstants cameraConstants{};
Json textureInventory=Json::array();
Json rendererInfo=Json::object();
Json renderLoadedModules=Json::array();
void ensure(bool,const std::string&);
std::vector<uint8_t> bytes(const fs::path&);
Texture readTexture(const fs::path& path){auto t=bytes(path);Texture tex;ensure(t.size()>=8,"Texture header");memcpy(&tex.w,t.data(),4);memcpy(&tex.h,t.data()+4,4);ensure(t.size()==8+size_t(tex.w)*tex.h*4,"Texture size");tex.pixels.assign(t.begin()+8,t.end());return tex;}
XMFLOAT3 initialEye,initialTarget;
XMFLOAT4X4 vp;
void ensure(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
void hr(HRESULT result,const char* label){if(FAILED(result)){char s[32];sprintf_s(s," (0x%08lX)",static_cast<unsigned long>(result));throw std::runtime_error(std::string(label)+s);}}
std::vector<uint8_t> bytes(const fs::path& p){std::ifstream f(assetPath(p),std::ios::binary|std::ios::ate);ensure(bool(f),"Missing file: "+p.string());auto n=f.tellg();ensure(n>0,"Empty file");std::vector<uint8_t> b(static_cast<size_t>(n));f.seekg(0);f.read(reinterpret_cast<char*>(b.data()),n);ensure(bool(f),"Truncated file");return b;}
#include "benchmark.inl"
#include "capture_png.inl"
#include "background_desktop.inl"
#include "profiles.inl"
void loadScene(){auto b=bytes("assets/museum.bin");ensure(b.size()>=40,"Scene header");auto* h=reinterpret_cast<const uint32_t*>(b.data());ensure(h[0]==0x4D555345&&h[3]==24,"Scene signature");ensure(b.size()==40+size_t(h[2])*12+size_t(h[1])*24,"Scene size");memcpy(&initialEye,b.data()+16,12);memcpy(&initialTarget,b.data()+28,12);draws.resize(h[2]);vertices.resize(h[1]);memcpy(draws.data(),b.data()+40,draws.size()*12);memcpy(vertices.data(),b.data()+40+draws.size()*12,vertices.size()*24);
auto attributes=bytes("assets/shading.bin");ensure(attributes.size()==vertices.size()*sizeof(Shading),"Shading data size");shading.resize(vertices.size());memcpy(shading.data(),attributes.data(),attributes.size());
for(unsigned i=0;i<24;i++){
 const auto folder=showcase?fs::path("assets/quality"):fs::path("assets");auto color=readTexture(folder/("texture_"+std::to_string(i)+".rgba"));
 textureInventory.push_back({{"material",i},{"width",color.w},{"height",color.h},{"source",folder.u8string()}});textures.push_back(std::move(color));
#if BACKEND>=9 && !defined(LEGACY_MATERIALS)
 if(showcase){textures.push_back(readTexture(fs::path("assets/quality")/("normal_"+std::to_string(i)+".rgba")));textures.push_back(readTexture(fs::path("assets/quality")/("rough_"+std::to_string(i)+".rgba")));}
 else{textures.push_back({1,1,{128,128,255,255}});textures.push_back({1,1,{180,180,180,255}});}
#endif
}
#if BACKEND>=9 && !defined(LEGACY_MATERIALS)
textures.push_back(fs::exists(assetPath("assets/key-shadow.rgba"))?readTexture("assets/key-shadow.rgba"):Texture{1,1,{255,255,255,255}});
#endif
litVertices.resize(vertices.size());for(size_t i=0;i<vertices.size();i++)litVertices[i]={vertices[i],shading[i]};
}
#include "controls.inl"
void camera(){
 XMVECTOR target,eye;
 if(orbitMode){target=XMLoadFloat3(&viewTarget);eye=XMVectorSubtract(target,XMVectorScale(viewDirection(),orbitDistance));XMStoreFloat3(&viewEye,eye);}
 else{eye=XMLoadFloat3(&viewEye);target=XMVectorAdd(eye,viewDirection());}
 // Holding either clock preserves its current offset instead of snapping to zero.
 auto drift=XMVectorSet(.018f*sinf(cameraTime*.55f),.008f*sinf(cameraTime*.7f),.008f*(cosf(cameraTime*.4f)-1.f),0);
 if(!orbitMode){eye=XMVectorAdd(eye,drift);target=XMVectorAdd(target,drift);}
XMStoreFloat3(&cameraEye,eye);
if(bakeShadow){eye=XMVectorSet(4.4f,2.9f,5.3f,1);target=XMVectorSet(2.3f,1.4f,3.8f,1);XMStoreFloat3(&cameraEye,eye);}
auto view=XMMatrixLookAtRH(eye,target,XMVectorSet(0,1,0,0));auto projection=XMMatrixPerspectiveFovRH(bakeShadow?1.91986218f:.78f,float(W)/H,.05f,bakeShadow?40.f:80.f);XMStoreFloat4x4(&vp,view*projection);cameraConstants={vp,{cameraEye.x,cameraEye.y,cameraEye.z,1},{showcase?1.f:0.f,simulationTime,1.15f,bakeShadow?1.f:0.f}};}
void saveCapture(const uint8_t* pixels,size_t pitch,bool bgra=false,bool bottomUp=false){
 const double actual=benchmarkElapsed();size_t end=nextCapture;while(end<captureTimes.size()&&captureTimes[end]<=actual)++end;
 const size_t count=std::max<size_t>(1,end-nextCapture);
 for(size_t i=0;i<count;i++){
  char stem[64];sprintf_s(stem,"capture-%05u",unsigned(captureRecords.size()+1));std::string png=std::string(stem)+".png",ppm=std::string(stem)+".ppm";
  savePng(pixels,pitch,bgra,bottomUp,png);std::ofstream f(output/ppm,std::ios::binary);f<<"P6\n"<<W<<" "<<H<<"\n255\n";
  for(unsigned y=0;y<H;y++){const uint8_t* row=pixels+(bottomUp?H-1-y:y)*pitch;for(unsigned x=0;x<W;x++){char rgb[3]={char(row[x*4+(bgra?2:0)]),char(row[x*4+1]),char(row[x*4+(bgra?0:2)])};f.write(rgb,3);}}ensure(bool(f),"Capture write failed");f.close();
  Json requested=nextCapture<end?Json(captureTimes[nextCapture++]):Json(nullptr);
  captureRecords.push_back({{"requested_seconds",requested},{"elapsed_seconds",actual},{"frame",frameNumber+1},{"png",png},{"ppm",ppm},{"shared_frame",count>1}});
  if(captureRecords.size()==1){captureElapsedSeconds=actual;screenshotFrame=frameNumber+1;fs::copy_file(output/png,output/"capture.png",fs::copy_options::overwrite_existing);fs::copy_file(output/ppm,output/"capture.ppm",fs::copy_options::overwrite_existing);}
 }
 std::ofstream manifest(output/"captures.json");manifest<<Json({{"requested_times",captureTimes},{"captures",captureRecords},{"pending",captureTimes.size()-nextCapture}}).dump(2);ensure(bool(manifest),"Capture manifest write failed");
}
Json moduleList(){Json result=Json::array();HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());if(snap!=INVALID_HANDLE_VALUE){MODULEENTRY32W e{};e.dwSize=sizeof(e);if(Module32FirstW(snap,&e))do{result.push_back(fs::path(e.szExePath).u8string());}while(Module32NextW(snap,&e));CloseHandle(snap);}return result;}
std::string gpuName;
void status(const char* state,const std::string& error=""){Json j={{"state",state},{"api",API_NAME},{"architecture",sizeof(void*)==8?"x64":"x86"},{"pid",GetCurrentProcessId()},{"frames_presented",frameNumber},{"width",W},{"height",H},{"client_width",clientWidth},{"client_height",clientHeight},{"gpu",gpuName},{"scene",room?"museum-room":"museum-face"},{"mode",showcase?"showcase":"matched"},{"maximized",windowHandle?IsZoomed(windowHandle)!=FALSE:false},{"requested_window",windowed?"windowed":"maximized"},{"effects",effectList()},{"textures",textureInventory},{"triangles",vertices.size()/3},{"error",error},{"loaded_modules",moduleList()}};j["controls"]=controlsInfo();j["render_loaded_modules"]=renderLoadedModules;j["background_isolated"]=isolatedBackground;j["renderer_details"]=rendererInfo;j["benchmark"]=benchmarkInfo();j["background"]=background;j["window_visible"]=windowHandle?IsWindowVisible(windowHandle)!=FALSE:false;auto temp=output/"status.tmp";std::ofstream(temp)<<j.dump(2);MoveFileExW(temp.c_str(),(output/"status.json").c_str(),MOVEFILE_REPLACE_EXISTING);}

#if BACKEND>=2 && BACKEND<=7
#include "directdraw_3d.inl"
#elif BACKEND==8 || BACKEND==9
#include "legacy.inl"
#elif BACKEND==10 || BACKEND==11
#include "dx10_11.inl"
#elif BACKEND==12
#include "dx12.inl"
#elif BACKEND==20
#include "opengl.inl"
#elif BACKEND==30
#include "vulkan.inl"
#elif BACKEND==21 || BACKEND==22
#include "programmable_gl.inl"
#elif BACKEND==40
#include "directdraw_2d.inl"
#elif BACKEND==41
#include "glide.inl"
#endif

LRESULT CALLBACK proc(HWND hwnd,UINT msg,WPARAM key,LPARAM l){switch(msg){
 case WM_COMMAND:{unsigned action=LOWORD(key);if(action>=2000&&action<2256){WPARAM code=action-2000;SendMessageW(hwnd,WM_KEYDOWN,code,0);heldKeys[code]=false;return 0;}break;}
 case WM_INITMENUPOPUP:{HMENU menu=reinterpret_cast<HMENU>(key);CheckMenuItem(menu,2000+'F',MF_BYCOMMAND|(frozen()?MF_CHECKED:MF_UNCHECKED));CheckMenuItem(menu,2000+'T',MF_BYCOMMAND|(animationsEnabled?MF_CHECKED:MF_UNCHECKED));CheckMenuItem(menu,2000+'B',MF_BYCOMMAND|(cameraMotionEnabled?MF_CHECKED:MF_UNCHECKED));CheckMenuItem(menu,2000+'O',MF_BYCOMMAND|(orbitMode?MF_CHECKED:MF_UNCHECKED));return 0;}
 case WM_CLOSE:running=false;return 0;
 case WM_DESTROY:running=false;PostQuitMessage(0);return 0;
 case WM_KILLFOCUS:std::fill_n(heldKeys,256,false);mouseLooking=false;if(GetCapture()==hwnd)ReleaseCapture();return 0;
 case WM_CAPTURECHANGED:mouseLooking=false;return 0;
 case WM_KEYUP:if(key<256)heldKeys[key]=false;return 0;
 case WM_KEYDOWN:
  if(background)return 0;
  if(key<256)heldKeys[key]=true;
  if(l&(1LL<<30))return 0;
  if(key==VK_ESCAPE)running=false;
  else if(key==VK_SPACE||key=='F')toggleFreeze();
  else if(key=='T')animationsEnabled=!animationsEnabled;
  else if(key=='B')cameraMotionEnabled=!cameraMotionEnabled;
  else if(key=='O')setOrbit(!orbitMode);
  else if(key=='R'){simulationTime=0;resetView();}
  else if(key==VK_F1){room=true;resetView();}
  else if(key==VK_F2){room=false;resetView();}
  else if(key==VK_F12)wantCapture=true;
  return 0;
 case WM_RBUTTONDOWN:if(!background){mouseLooking=true;mouseX=short(LOWORD(l));mouseY=short(HIWORD(l));SetCapture(hwnd);}return 0;
 case WM_RBUTTONUP:mouseLooking=false;if(GetCapture()==hwnd)ReleaseCapture();return 0;
 case WM_MOUSEMOVE:if(mouseLooking){int x=short(LOWORD(l)),y=short(HIWORD(l));viewYaw-=(x-mouseX)*.004f;viewPitch-=(y-mouseY)*.004f;mouseX=x;mouseY=y;clampView();}return 0;
 case WM_MOUSEWHEEL:if(!background)scrollCamera(float(short(HIWORD(key)))/WHEEL_DELTA);return 0;
 }return DefWindowProcW(hwnd,msg,key,l);}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR,int){int code=0;try{
 SetProcessDPIAware();
 wchar_t exe[32768];GetModuleFileNameW(nullptr,exe,32768);fs::current_path(fs::path(exe).parent_path());assetDirectory=findAssets();output=fs::absolute("run");
 bool durationSet=false,captureSet=false;
 int argc=0;LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);
 for(int i=1;i<argc;i++){
  std::wstring arg=argv[i];
  if(arg==L"--frames"&&i+1<argc)frameLimit=std::stoull(argv[++i]);
  else if(arg==L"--capture-frame"&&i+1<argc)captureFrame=std::stoull(argv[++i]);
  else if(arg==L"--seconds"&&i+1<argc){durationSeconds=std::stod(argv[++i]);durationSet=true;}
  else if(arg==L"--warmup-seconds"&&i+1<argc)measurement.warmup=parseSeconds(argv[++i]);
  else if(arg==L"--measure-seconds"&&i+1<argc){measurement.requested=parseSeconds(argv[++i]);ensure(measurement.requested>0,"Measurement duration must be positive");}
  else if(arg==L"--no-capture"){noCapture=true;captureSet=true;}
  else if(arg==L"--capture-after-measure")captureAfterMeasurement=true;
  else if(arg==L"--capture-at"&&i+1<argc){addCaptureTimes(argv[++i]);captureSet=true;}
  else if(arg==L"--capture-every"&&i+1<argc){captureEverySeconds=parseSeconds(argv[++i]);ensure(captureEverySeconds>0,"--capture-every must be positive");}
  else if(arg==L"--background")background=true;
  else if(arg==L"--width"&&i+1<argc)W=std::stoul(argv[++i]);
  else if(arg==L"--height"&&i+1<argc)H=std::stoul(argv[++i]);
  else if(arg==L"--output"&&i+1<argc)output=fs::absolute(argv[++i]);
  else if(arg==L"--bake-shadow"){bakeShadow=true;showcase=false;windowed=true;}
  else if(arg==L"--mode"&&i+1<argc){std::wstring mode=argv[++i];ensure(mode==L"matched"||mode==L"showcase","--mode must be matched or showcase");showcase=mode==L"showcase";}
  else if(arg==L"--windowed")windowed=true;
  else if(arg==L"--maximized")windowed=false;
  else if(arg==L"--fixed-time")fixedTime=true;
  else if(arg==L"--freeze")paused=true;
  else if(arg==L"--orbit")orbitMode=true;
  else if(arg==L"--camera"&&i+1<argc){std::wstring value=argv[++i];ensure(value==L"free"||value==L"orbit","--camera must be free or orbit");orbitMode=value==L"orbit";}
  else if((arg==L"--animations"||arg==L"--camera-motion")&&i+1<argc){std::wstring value=argv[++i];ensure(value==L"on"||value==L"off","Animation options must be on or off");(arg==L"--animations"?animationsEnabled:cameraMotionEnabled)=value==L"on";}
  else if(arg==L"--no-animations")animationsEnabled=false;
  else if(arg==L"--room")room=true;
  else throw std::runtime_error("Unknown or incomplete argument");
 }
 LocalFree(argv);
 if(background){windowed=true;if(!durationSet&&!frameLimit)durationSeconds=30;}
 ensure(std::isfinite(durationSeconds)&&durationSeconds>=0,"--seconds must be a finite nonnegative number");
 prepareCaptureSchedule(captureSet);
 ensure(!captureAfterMeasurement||measurement.enabled(),"--capture-after-measure requires --measure-seconds");
 ensure(!noCapture||captureTimes.empty(),"--no-capture cannot be combined with scheduled captures");
 ensure(W>=320&&H>=240&&W<=3840&&H<=2160,"Resolution range: 320x240 through 3840x2160");fs::create_directories(output);status("starting");
 isolateBackground();
 WNDCLASSW wc{};wc.style=CS_OWNDC;wc.lpfnWndProc=proc;wc.hInstance=instance;wc.hCursor=LoadCursor(nullptr,IDC_ARROW);wc.lpszClassName=L"MuseumGraphicsTest";RegisterClassW(&wc);
 DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX|WS_MAXIMIZEBOX;RECT rect{0,0,LONG(W),LONG(H)};AdjustWindowRect(&rect,style,background?FALSE:TRUE);
 std::wstring title=L"Museum - ";for(const char* c=API_NAME;*c;c++)title+=wchar_t(*c);title+=sizeof(void*)==8?L" x64":L" x86";
 windowHandle=CreateWindowExW(background?WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW:0,wc.lpszClassName,title.c_str(),style,80,60,rect.right-rect.left,rect.bottom-rect.top,nullptr,background?nullptr:createControlsMenu(),instance,nullptr);ensure(windowHandle!=nullptr,"CreateWindow");
 if(!background){ShowWindow(windowHandle,windowed?SW_SHOW:SW_MAXIMIZE);UpdateWindow(windowHandle);}
 RECT client{};GetClientRect(windowHandle,&client);W=clientWidth=unsigned(client.right);H=clientHeight=unsigned(client.bottom);ensure(W&&H,"Client extent");if(bakeShadow)W=H=2048;loadScene();resetView();
 initRenderer();rendererInfo["vsync_requested"]=false;if(!background&&!windowed)ShowWindow(windowHandle,SW_MAXIMIZE);for(auto& texture:textures){texture.pixels.clear();texture.pixels.shrink_to_fit();}
 benchmarkStart=Clock::now();benchmarkStartTick=GetTickCount64();auto last=benchmarkStart;fpsCsv.open(output/"fps.csv");ensure(bool(fpsCsv),"FPS output");fpsCsv<<"elapsed_seconds,total_frames,interval_frames,interval_seconds,fps,average_fps\n";status("running");
 MSG msg{};
 while(running&&(!frameLimit||frameNumber<frameLimit)){
  while(PeekMessage(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessage(&msg);}
  if(!running)break;
  elapsedSeconds=benchmarkElapsed();if(durationSeconds>0&&elapsedSeconds>=durationSeconds&&!captureDueNow())break;
  measurement.before_frame(elapsedSeconds);
  if(!background&&IsIconic(windowHandle)){Sleep(30);last=Clock::now();continue;}
  auto now=Clock::now();float dt=std::chrono::duration<float>(now-last).count();last=now;moveCamera(std::min(dt,.1f));camera();
#if BACKEND<9 || defined(LEGACY_MATERIALS)
  if(showcase)updateLegacyLighting();
#endif
  bool timedCapture=captureDueNow();
  bool capture=!noCapture&&(wantCapture||timedCapture||(captureAtSeconds<0&&frameLimit&&frameNumber+1==captureFrame));
  drawFrame(capture);double frameSeconds=std::chrono::duration<double>(Clock::now()-now).count();maximumFrameSeconds=std::max(maximumFrameSeconds,frameSeconds);wantCapture=false;++frameNumber;
  bool measuredComplete=measurement.after_frame(benchmarkElapsed(),frameSeconds);sampleMeasurement(measuredComplete);
  if(measuredComplete){std::ofstream(output/"measurement.json")<<measuredInfo().dump(2);status("running");}
  elapsedSeconds=benchmarkElapsed();fpsAverage=frameNumber/elapsedSeconds;size_t priorSamples=fpsSamples.size();sampleFps();
  if(frameNumber==1||fpsSamples.size()!=priorSamples){status("running");
   std::wstring label=title+(showcase?L" | Showcase":L" | Matched")+L" | "+std::to_wstring(int(fpsLatest))+L" FPS"+(frozen()?L" | FROZEN":L"")+(orbitMode?L" | Orbit":L" | Free")+L" | WASD/arrows move, RMB look, F freeze, O orbit, T effects, B camera, R reset";SetWindowTextW(windowHandle,label.c_str());}
 }
 elapsedSeconds=benchmarkElapsed();fpsAverage=elapsedSeconds>0?frameNumber/elapsedSeconds:0;sampleFps(true);
 sampleMeasurement(true);
 Json report=benchmarkInfo();report["api"]=API_NAME;report["mode"]=showcase?"showcase":"matched";report["architecture"]=sizeof(void*)==8?"x64":"x86";report["samples"]=fpsSamples;report["capture_times"]=captureTimes;report["captures"]=captureRecords;report["pending_captures"]=captureTimes.size()-nextCapture;
 report["controls"]=controlsInfo();
 if(measurement.enabled()){
  report["render_elapsed_seconds"]=elapsedSeconds;report["full_run_average_fps"]=fpsAverage;
  report.merge_patch(measuredInfo());report["measurement"]=measuredInfo();
  report["rendering_note"]="Measured frame-boundary interval only; warmup and post-measurement screenshot work are excluded. Hidden-window FPS is not visible-game FPS.";
 }
 std::ofstream(output/"fps.json")<<report.dump(2);fpsCsv.close();renderLoadedModules=moduleList();shutdownRenderer();status("complete");DestroyWindow(windowHandle);closeBackgroundDesktop();
}catch(const std::exception& e){if(output.empty())output=fs::absolute("run");fs::create_directories(output);status("error",e.what());code=1;}
return code;}
