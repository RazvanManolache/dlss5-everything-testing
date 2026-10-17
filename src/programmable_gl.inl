#ifdef USE_EGL
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <EGL/eglext_angle.h>
#include <GLES2/gl2.h>
EGLDisplay eglDisplay=EGL_NO_DISPLAY;EGLContext eglContext=EGL_NO_CONTEXT;EGLSurface eglSurface=EGL_NO_SURFACE;
#else
#include <GL/gl.h>
#include "gl_functions.h"
#include "gl_profile_policy.h"
HDC dc{};HGLRC glContext{};GLuint glVao=0;
#endif
#include "fullbench_shaders.h"
GLuint glProgram=0,glVbo=0;std::vector<GLuint> glTextures;
GLuint fullbenchCompile(GLenum type,const char* source){GLuint shader=glCreateShader(type);glShaderSource(shader,1,&source,nullptr);glCompileShader(shader);GLint ok;glGetShaderiv(shader,0x8B81,&ok);if(!ok){char log[16384]{};glGetShaderInfoLog(shader,sizeof(log),nullptr,log);throw std::runtime_error(std::string("Shader: ")+log);}return shader;}
void initRenderer(){
#ifdef USE_EGL
 auto platform=reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(eglGetProcAddress("eglGetPlatformDisplayEXT"));ensure(platform!=nullptr,"ANGLE platform entry");
#ifdef ANGLE_VULKAN
 constexpr EGLint requestedDriver=EGL_PLATFORM_ANGLE_TYPE_VULKAN_ANGLE;const char* requestedName="Vulkan";
#else
 constexpr EGLint requestedDriver=EGL_PLATFORM_ANGLE_TYPE_D3D11_ANGLE;const char* requestedName="D3D11";
#endif
 rendererInfo["requested_backend"]=requestedName;rendererInfo["egl_client_extensions"]=eglQueryString(EGL_NO_DISPLAY,EGL_EXTENSIONS);
 EGLint attrs[]={EGL_PLATFORM_ANGLE_TYPE_ANGLE,requestedDriver,EGL_PLATFORM_ANGLE_DEVICE_TYPE_ANGLE,EGL_PLATFORM_ANGLE_DEVICE_TYPE_HARDWARE_ANGLE,EGL_NONE};eglDisplay=platform(EGL_PLATFORM_ANGLE_ANGLE,EGL_DEFAULT_DISPLAY,attrs);ensure(eglDisplay!=EGL_NO_DISPLAY,"ANGLE display");EGLint major,minor;EGLBoolean initialized=eglInitialize(eglDisplay,&major,&minor);ensure(initialized==EGL_TRUE,"ANGLE initialization error "+std::to_string(eglGetError()));ensure(eglBindAPI(EGL_OPENGL_ES_API)==EGL_TRUE,"EGL API");
 EGLint configAttrs[]={EGL_SURFACE_TYPE,EGL_WINDOW_BIT,EGL_RENDERABLE_TYPE,GLES_VERSION==3?EGL_OPENGL_ES3_BIT_KHR:EGL_OPENGL_ES2_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_DEPTH_SIZE,24,EGL_STENCIL_SIZE,8,EGL_NONE};EGLConfig config{};EGLint count;ensure(eglChooseConfig(eglDisplay,configAttrs,&config,1,&count)==EGL_TRUE&&count>0,"EGL config");EGLint contextAttrs[]={EGL_CONTEXT_CLIENT_VERSION,GLES_VERSION,EGL_NONE};eglContext=eglCreateContext(eglDisplay,config,EGL_NO_CONTEXT,contextAttrs);ensure(eglContext!=EGL_NO_CONTEXT,"EGL context");eglSurface=eglCreateWindowSurface(eglDisplay,config,windowHandle,nullptr);ensure(eglSurface!=EGL_NO_SURFACE,"EGL window surface");ensure(eglMakeCurrent(eglDisplay,eglSurface,eglSurface,eglContext)==EGL_TRUE,"EGL current");ensure(eglSwapInterval(eglDisplay,0)==EGL_TRUE,"Disable EGL VSync");
 EGLint minimumInterval=1;eglGetConfigAttrib(eglDisplay,config,EGL_MIN_SWAP_INTERVAL,&minimumInterval);rendererInfo={{"uncapped_available",minimumInterval==0},{"swap_interval",0},{"context_api","EGL / ANGLE"},{"requested_backend",requestedName},{"egl_version",std::to_string(major)+"."+std::to_string(minor)},{"gles_requested",GLES_VERSION},{"surface","EGL window surface"}};
#if GLES_VERSION==2
 const char* vertex=es2Vertex;const char* fragment=es2Fragment;
#else
 const char* vertex=es3Vertex;const char* fragment=es3Fragment;
#endif
#else
 dc=GetDC(windowHandle);PIXELFORMATDESCRIPTOR p{sizeof(p),1};p.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;p.iPixelType=PFD_TYPE_RGBA;p.cColorBits=32;p.cDepthBits=24;p.cStencilBits=8;int pf=ChoosePixelFormat(dc,&p);ensure(pf&&SetPixelFormat(dc,pf,&p),"Core pixel format");HGLRC bootstrap=wglCreateContext(dc);ensure(bootstrap&&wglMakeCurrent(dc,bootstrap),"WGL bootstrap");using Create=HGLRC(WINAPI*)(HDC,HGLRC,const int*);auto create=glFunction<Create>("wglCreateContextAttribsARB");int attrs[]={0x2091,GL_CORE_MAJOR,0x2092,GL_CORE_MINOR,0x9126,1,0};glContext=create(dc,nullptr,attrs);wglMakeCurrent(nullptr,nullptr);wglDeleteContext(bootstrap);ensure(glContext&&wglMakeCurrent(dc,glContext),"Core-profile context");loadGLFunctions();GLint profile=0;glGetIntegerv(0x9126,&profile);
 auto proxy=GetModuleHandleW(L"opengl32.dll");bool reshadeLoaded=proxy&&GetProcAddress(proxy,"ReShadeRegisterAddon");
 ensure(acceptedGLProfile(GL_CORE_MAJOR,GL_CORE_MINOR,profile,reshadeLoaded),"Expected GL core profile (or ReShade's pre-4.3 context upgrade)");
 rendererInfo={{"context_api","WGL requested core"},{"profile_mask",profile},{"requested_profile","core"},{"actual_profile",profile&1?"core":"compatibility"},{"reshade_profile_upgrade",!(profile&1)&&reshadeLoaded},{"requested_version",std::to_string(GL_CORE_MAJOR)+"."+std::to_string(GL_CORE_MINOR)}};glGenVertexArrays(1,&glVao);glBindVertexArray(glVao);
#if GL_CORE_MAJOR==4
 const char* vertex=core46Vertex;const char* fragment=core46Fragment;
#else
 const char* vertex=core33Vertex;const char* fragment=core33Fragment;
#endif
 using Interval=BOOL(WINAPI*)(int);auto interval=reinterpret_cast<Interval>(wglGetProcAddress("wglSwapIntervalEXT"));rendererInfo["uncapped_available"]=interval&&interval(0);rendererInfo["swap_interval"]=0;
#endif
 gpuName=reinterpret_cast<const char*>(glGetString(GL_RENDERER));rendererInfo["renderer"]=gpuName;rendererInfo["version"]=reinterpret_cast<const char*>(glGetString(GL_VERSION));rendererInfo["shading_language"]=reinterpret_cast<const char*>(glGetString(0x8B8C));
 auto vs=fullbenchCompile(0x8B31,vertex),ps=fullbenchCompile(0x8B30,fragment);glProgram=glCreateProgram();glAttachShader(glProgram,vs);glAttachShader(glProgram,ps);const char* names[]={"position","color","texcoord","inNormal","inTangent","inBase","inMaterial"};for(unsigned i=0;i<7;i++)glBindAttribLocation(glProgram,i,names[i]);glLinkProgram(glProgram);GLint ok;glGetProgramiv(glProgram,0x8B82,&ok);if(!ok){char log[16384]{};glGetProgramInfoLog(glProgram,sizeof(log),nullptr,log);throw std::runtime_error(log);}glDeleteShader(vs);glDeleteShader(ps);glUseProgram(glProgram);
 glGenBuffers(1,&glVbo);glBindBuffer(0x8892,glVbo);glBufferData(0x8892,litVertices.size()*sizeof(LitVertex),litVertices.data(),0x88E4);int sizes[]={3,4,2,3,4,3,4},offsets[]={0,12,16,24,36,52,64};for(unsigned i=0;i<7;i++){glEnableVertexAttribArray(i);glVertexAttribPointer(i,sizes[i],i==1?GL_UNSIGNED_BYTE:GL_FLOAT,i==1?GL_TRUE:GL_FALSE,sizeof(LitVertex),reinterpret_cast<void*>(size_t(offsets[i])));}
 glEnable(GL_DEPTH_TEST);glDepthFunc(GL_LEQUAL);glDisable(GL_CULL_FACE);GLfloat maxAniso=1;glGetFloatv(0x84FF,&maxAniso);if(glGetError()!=GL_NO_ERROR)maxAniso=1;rendererInfo["max_anisotropy"]=maxAniso;
 for(auto& t:textures){GLuint texture;glGenTextures(1,&texture);glBindTexture(GL_TEXTURE_2D,texture);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,t.w,t.h,0,GL_RGBA,GL_UNSIGNED_BYTE,t.pixels.data());glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_REPEAT);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_REPEAT);if(showcase){glGenerateMipmap(GL_TEXTURE_2D);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR_MIPMAP_LINEAR);if(maxAniso>1)glTexParameterf(GL_TEXTURE_2D,0x84FE,maxAniso);}glTextures.push_back(texture);t.pixels.clear();t.pixels.shrink_to_fit();}
 ensure(glGetError()==GL_NO_ERROR,"Programmable GL initialization");glUniform1i(glGetUniformLocation(glProgram,"image"),0);glUniform1i(glGetUniformLocation(glProgram,"normalMap"),1);glUniform1i(glGetUniformLocation(glProgram,"roughMap"),2);glUniform1i(glGetUniformLocation(glProgram,"shadowMap"),3);
}
void drawFrame(bool capture){
 glViewport(0,0,W,H);glClearColor(32/255.f,40/255.f,49/255.f,1);glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);glUseProgram(glProgram);glUniformMatrix4fv(glGetUniformLocation(glProgram,"viewProjection"),1,GL_FALSE,&vp._11);glUniform4f(glGetUniformLocation(glProgram,"cameraEye"),cameraEye.x,cameraEye.y,cameraEye.z,1);glUniform4f(glGetUniformLocation(glProgram,"modeOptions"),showcase?1.f:0.f,cameraConstants.options.y,cameraConstants.options.z,0);glActiveTexture(0x84C3);glBindTexture(GL_TEXTURE_2D,glTextures[72]);for(auto& d:draws){for(unsigned k=0;k<3;k++){glActiveTexture(0x84C0+k);glBindTexture(GL_TEXTURE_2D,glTextures[d.texture*3+k]);}glDrawArrays(GL_TRIANGLES,d.first,d.count);}ensure(glGetError()==GL_NO_ERROR,"Programmable GL draw");if(capture||captureDueNow()){std::vector<uint8_t> pixels(size_t(W)*H*4);glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());ensure(glGetError()==GL_NO_ERROR,"GL capture");saveCapture(pixels.data(),size_t(W)*4,false,true);}
#ifdef USE_EGL
 ensure(eglSwapBuffers(eglDisplay,eglSurface)==EGL_TRUE,"EGL present");
#else
 ensure(SwapBuffers(dc)!=FALSE,"Core GL present");
#endif
}
void shutdownRenderer(){glFinish();glDeleteTextures(GLsizei(glTextures.size()),glTextures.data());glDeleteBuffers(1,&glVbo);glDeleteProgram(glProgram);
#ifdef USE_EGL
 eglMakeCurrent(eglDisplay,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);eglDestroySurface(eglDisplay,eglSurface);eglDestroyContext(eglDisplay,eglContext);eglTerminate(eglDisplay);
#else
 glDeleteVertexArrays(1,&glVao);wglMakeCurrent(nullptr,nullptr);wglDeleteContext(glContext);ReleaseDC(windowHandle,dc);
#endif
}
