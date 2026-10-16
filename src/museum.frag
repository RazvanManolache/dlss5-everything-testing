#version 450
layout(push_constant) uniform Camera{mat4 vp;vec4 eye;vec4 options;}camera;
layout(set=0,binding=0) uniform sampler2D image;layout(set=0,binding=1) uniform sampler2D normalMap;layout(set=0,binding=2) uniform sampler2D roughMap;layout(set=0,binding=3) uniform sampler2D shadowMap;
float readShadow(vec2 uv){return dot(texture(shadowMap,uv).rg,vec2(65280./65535.,255./65535.));}
layout(location=0) in vec4 tint;layout(location=1) in vec2 uv;layout(location=2) in vec3 world;layout(location=3) in vec3 normal;layout(location=4) in vec4 tangent;layout(location=5) in vec3 base;layout(location=6) in vec4 material;
layout(location=0) out vec4 result;
vec3 readNormal(vec2 uv){return texture(normalMap,uv).xyz*2.-1.;}float readRough(vec2 uv){return texture(roughMap,uv).r;}
float saturate(float x){return clamp(x,0.,1.);}
vec3 saturate(vec3 x){return clamp(x,vec3(0),vec3(1));}
float keyShadow(vec3 p,vec3 N){vec3 origin=vec3(4.4,2.9,5.3);vec3 Z=normalize(origin-vec3(2.3,1.4,3.8));vec3 X=normalize(cross(vec3(0,1,0),Z));vec3 Y=cross(Z,X);vec3 d=p-origin;float forward=-dot(d,Z);if(forward<=.05)return 1.;float f=1./tan(1.91986218*.5);vec2 uv=vec2(.5+.5*dot(d,X)*f/forward,.5-.5*dot(d,Y)*f/forward);if(uv.x<0||uv.y<0||uv.x>1||uv.y>1)return 1.;float z=40./39.95-2./(39.95*forward);float bias=.000065+.00008*(1-max(dot(N,normalize(origin-p)),0));float sum=0.;for(int y=-2;y<=2;y++)for(int x=-2;x<=2;x++){float depth=readShadow(uv+vec2(x,y)/2048.);sum+=(z-bias<=depth)?1.:.16;}return sum/25.;}
vec3 lightPosition(int k){if(k==0)return vec3(-2.7,4.2,3.5);if(k==1)return vec3(3.2,3.6,2);if(k==2)return vec3(-5,4.8,-4);if(k==3)return vec3(5,4.8,-4);if(k==4)return vec3(-4.5,5,-8);if(k==5)return vec3(4.5,5,-8);if(k==6)return vec3(4.4,2.9,5.3);return vec3(1.1,2.6,2.3);}
vec3 lightColor(int k){if(k==0)return vec3(1,.72,.48)*9;if(k==1)return vec3(.5,.72,1)*8;if(k==2)return vec3(1,.75,.5)*14;if(k==3)return vec3(.5,.7,1)*16;if(k==4)return vec3(1,.7,.4)*16;if(k==5)return vec3(.4,.65,1)*16;if(k==6)return vec3(1,.87,.72)*5.8;return vec3(.45,.65,1)*3.4;}
vec3 aces(vec3 x){return saturate((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14));}
vec3 shadeSurface(vec3 p,vec3 normal,vec4 tangent,vec3 tint,vec4 material,vec2 uv,vec3 tex,vec3 camera,float time,float exposure){
 float kind=floor(material.x+.1);vec3 N=normalize(normal);vec3 T=normalize(tangent.xyz-N*dot(tangent.xyz,N));vec3 B=cross(N,T)*tangent.w;
 vec3 bump=normalize(readNormal(uv));float strength=kind>=10?.48:1.;N=normalize(T*bump.x*strength+B*bump.y*strength+N*bump.z);
 vec3 albedo=pow(max(tex*tint,vec3(0,0,0)),vec3(2.2,2.2,2.2));float rough=clamp(readRough(uv)*.85+.08,.12,.95);float metal=material.y;
 if(kind==3){float wave=sin(p.x*2.4+sin(p.z*1.8)*1.4+sin(p.x*11+p.z*6)*.08);float veins=pow(abs(wave),18);albedo*=.7+.3*veins;vec2 seam=abs(fract(p.xz*.42)-.5);float joint=1-smoothstep(.485,.498,max(seam.x,seam.y));albedo*=.4+.6*joint;rough=.22;}
 if(kind==4){rough=.2;metal=.82;}vec3 V=normalize(camera-p);float nv=max(dot(N,V),.001);vec3 F0=mix(vec3(.04,.04,.04),albedo,metal);
 vec3 result=albedo*(.12+.16*max(N.y,0))*material.w;
 for(int k=0;k<8;k++){
  vec3 lp=lightPosition(k);vec3 delta=lp-p;float d2=dot(delta,delta);vec3 L=normalize(delta);vec3 H=normalize(V+L);float nl=max(dot(N,L),0);float nh=max(dot(N,H),0);float vh=max(dot(V,H),0);
  float a=rough*rough;float a2=a*a;float divisor=nh*nh*(a2-1)+1;float D=a2/max(3.14159265*divisor*divisor,.0001);float g=(rough+1)*(rough+1)/8;float G=(nv/(nv*(1-g)+g))*(nl/(nl*(1-g)+g));vec3 F=F0+(1-F0)*pow(1-vh,5);vec3 spec=D*G*F/max(4*nv*nl,.001);vec3 diffuse=(1-F)*(1-metal)*albedo/3.14159265;
  vec3 radiance=lightColor(k)*(1.+.05*sin(time*1.1));
  float visibility=k==6?keyShadow(p,N):1.;result+=(diffuse+spec)*radiance*nl*visibility/(1+d2);
  if(kind>=10&&uv.x<.33334){float wrap=max((dot(N,L)+.38)/1.38,0);result+=albedo*vec3(1,.45,.28)*radiance*wrap*.095/(1+d2);}
 }
 vec3 R=reflect(-V,N);vec3 environment=mix(vec3(.18,.105,.055),vec3(.12,.22,.4),saturate(R.y*.5+.5));vec3 fresnel=F0+(1-F0)*pow(1-nv,5);result+=environment*fresnel*(1-rough*.8);
 if(kind==5)result+=albedo*2.5;float distance=length(camera-p);float fog=1-exp(-distance*.018*exp(-max(p.y,0)*.11));result=mix(result,vec3(.13,.17,.23),fog);
 return pow(aces(result*exposure),vec3(1./2.2,1./2.2,1./2.2));
}

void main(){vec4 t=texture(image,uv);if(t.a<.5)discard;if(camera.options.x<.5){result=vec4(t.rgb*tint.rgb,1);return;}result=vec4(shadeSurface(world,normal,tangent,base,material,uv,t.rgb,camera.eye.xyz,camera.options.y,camera.options.z),1);}
