#pragma once
#include <d3dcompiler.h>
#include <wrl/client.h>
using Microsoft::WRL::ComPtr;
const char* shaderSource=R"(
cbuffer Camera : register(b0) { row_major float4x4 vp; float4 eye; float4 options; }
struct V {float3 p:POSITION;float4 c:COLOR;float2 uv:TEXCOORD0;float3 n:NORMAL;float4 tangent:TANGENT;float3 base:COLOR1;float4 material:TEXCOORD1;};
struct P {float4 p:SV_Position;float4 c:COLOR;float2 uv:TEXCOORD0;float3 world:TEXCOORD1;float3 n:NORMAL;float4 tangent:TANGENT;float3 base:COLOR1;float4 material:TEXCOORD2;};
P vsMain(V v){P p;p.p=mul(float4(v.p,1),vp);p.c=v.c;p.uv=v.uv;p.world=v.p;p.n=v.n;p.tangent=v.tangent;p.base=v.base;p.material=v.material;return p;}
Texture2D image:register(t0);Texture2D normalMap:register(t1);Texture2D roughMap:register(t2);Texture2D shadowMap:register(t3);SamplerState linearSampler:register(s0);
float3 readNormal(float2 uv){return normalMap.Sample(linearSampler,uv).xyz*2-1;}
float readRough(float2 uv){return roughMap.Sample(linearSampler,uv).r;}
float readShadow(float2 uv){float2 v=shadowMap.SampleLevel(linearSampler,uv,0).rg;return dot(v,float2(65280./65535.,255./65535.));}
// SHARED_SHADE_BEGIN
float keyShadow(float3 p,float3 N){float3 origin=float3(4.4,2.9,5.3);float3 Z=normalize(origin-float3(2.3,1.4,3.8));float3 X=normalize(cross(float3(0,1,0),Z));float3 Y=cross(Z,X);float3 d=p-origin;float forward=-dot(d,Z);if(forward<=.05)return 1.;float f=1./tan(1.91986218*.5);float2 uv=float2(.5+.5*dot(d,X)*f/forward,.5-.5*dot(d,Y)*f/forward);if(uv.x<0||uv.y<0||uv.x>1||uv.y>1)return 1.;float z=40./39.95-2./(39.95*forward);float bias=.000065+.00008*(1-max(dot(N,normalize(origin-p)),0));float sum=0.;for(int y=-2;y<=2;y++)for(int x=-2;x<=2;x++){float depth=readShadow(uv+float2(x,y)/2048.);sum+=(z-bias<=depth)?1.:.16;}return sum/25.;}
float3 lightPosition(int k){if(k==0)return float3(-2.7,4.2,3.5);if(k==1)return float3(3.2,3.6,2);if(k==2)return float3(-5,4.8,-4);if(k==3)return float3(5,4.8,-4);if(k==4)return float3(-4.5,5,-8);if(k==5)return float3(4.5,5,-8);if(k==6)return float3(4.4,2.9,5.3);return float3(1.1,2.6,2.3);}
float3 lightColor(int k){if(k==0)return float3(1,.72,.48)*9;if(k==1)return float3(.5,.72,1)*8;if(k==2)return float3(1,.75,.5)*14;if(k==3)return float3(.5,.7,1)*16;if(k==4)return float3(1,.7,.4)*16;if(k==5)return float3(.4,.65,1)*16;if(k==6)return float3(1,.87,.72)*5.8;return float3(.45,.65,1)*3.4;}
float3 aces(float3 x){return saturate((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14));}
float3 shadeSurface(float3 p,float3 normal,float4 tangent,float3 tint,float4 material,float2 uv,float3 tex,float3 camera,float time,float exposure){
 float kind=floor(material.x+.1);float3 N=normalize(normal);float3 T=normalize(tangent.xyz-N*dot(tangent.xyz,N));float3 B=cross(N,T)*tangent.w;
 float3 bump=normalize(readNormal(uv));float strength=kind>=10?.48:1.;N=normalize(T*bump.x*strength+B*bump.y*strength+N*bump.z);
 float3 albedo=pow(max(tex*tint,float3(0,0,0)),float3(2.2,2.2,2.2));float rough=clamp(readRough(uv)*.85+.08,.12,.95);float metal=material.y;
 if(kind==3){float wave=sin(p.x*2.4+sin(p.z*1.8)*1.4+sin(p.x*11+p.z*6)*.08);float veins=pow(abs(wave),18);albedo*=.7+.3*veins;float2 seam=abs(frac(p.xz*.42)-.5);float joint=1-smoothstep(.485,.498,max(seam.x,seam.y));albedo*=.4+.6*joint;rough=.22;}
 if(kind==4){rough=.2;metal=.82;}float3 V=normalize(camera-p);float nv=max(dot(N,V),.001);float3 F0=lerp(float3(.04,.04,.04),albedo,metal);
 float3 result=albedo*(.12+.16*max(N.y,0))*material.w;
 for(int k=0;k<8;k++){
  float3 lp=lightPosition(k);float3 delta=lp-p;float d2=dot(delta,delta);float3 L=normalize(delta);float3 H=normalize(V+L);float nl=max(dot(N,L),0);float nh=max(dot(N,H),0);float vh=max(dot(V,H),0);
  float a=rough*rough;float a2=a*a;float divisor=nh*nh*(a2-1)+1;float D=a2/max(3.14159265*divisor*divisor,.0001);float g=(rough+1)*(rough+1)/8;float G=(nv/(nv*(1-g)+g))*(nl/(nl*(1-g)+g));float3 F=F0+(1-F0)*pow(1-vh,5);float3 spec=D*G*F/max(4*nv*nl,.001);float3 diffuse=(1-F)*(1-metal)*albedo/3.14159265;
  float3 radiance=lightColor(k)*(1.+.05*sin(time*1.1));
  float visibility=k==6?keyShadow(p,N):1.;result+=(diffuse+spec)*radiance*nl*visibility/(1+d2);
  if(kind>=10&&uv.x<.33334){float wrap=max((dot(N,L)+.38)/1.38,0);result+=albedo*float3(1,.45,.28)*radiance*wrap*.095/(1+d2);}
 }
 float3 R=reflect(-V,N);float3 environment=lerp(float3(.18,.105,.055),float3(.12,.22,.4),saturate(R.y*.5+.5));float3 fresnel=F0+(1-F0)*pow(1-nv,5);result+=environment*fresnel*(1-rough*.8);
 if(kind==5)result+=albedo*2.5;float distance=length(camera-p);float fog=1-exp(-distance*.018*exp(-max(p.y,0)*.11));result=lerp(result,float3(.13,.17,.23),fog);
 return pow(aces(result*exposure),float3(1./2.2,1./2.2,1./2.2));
}
// SHARED_SHADE_END
float4 psMain(P p):SV_Target {float4 t=image.Sample(linearSampler,p.uv);clip(t.a-.5);if(options.w>.5){float value=floor(saturate(p.p.z)*65535.+.5);return float4(floor(value/256.)/255.,fmod(value,256.)/255.,0,1);}if(options.x<.5)return float4(t.rgb*p.c.rgb,1);return float4(shadeSurface(p.world,p.n,p.tangent,p.base,p.material,p.uv,t.rgb,eye.xyz,options.y,options.z),1);}
)";
ComPtr<ID3DBlob> compileShader(const char* entry,const char* profile){ComPtr<ID3DBlob> code,error;HRESULT r=D3DCompile(shaderSource,strlen(shaderSource),"museum",nullptr,nullptr,entry,profile,D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&code,&error);if(FAILED(r))throw std::runtime_error(error?static_cast<char*>(error->GetBufferPointer()):"Shader compile");return code;}
