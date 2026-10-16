"""Keep showcase lighting identical across the three programmable API families."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def main():
    text=(ROOT/'src/shader.h').read_text();shared=text.split('// SHARED_SHADE_BEGIN\n')[1].split('// SHARED_SHADE_END')[0]
    for a,b in [('float4','vec4'),('float3','vec3'),('float2','vec2'),('lerp(','mix('),('frac(','fract(')]:shared=shared.replace(a,b)
    shared='float saturate(float x){return clamp(x,0.,1.);}\nvec3 saturate(vec3 x){return clamp(x,vec3(0),vec3(1));}\n'+shared
    body='''float readShadow(vec2 uv){return dot(texture(shadowMap,uv).rg,vec2(65280./65535.,255./65535.));}
layout(location=0) in vec4 tint;layout(location=1) in vec2 uv;layout(location=2) in vec3 world;layout(location=3) in vec3 normal;layout(location=4) in vec4 tangent;layout(location=5) in vec3 base;layout(location=6) in vec4 material;
layout(location=0) out vec4 result;
vec3 readNormal(vec2 uv){return texture(normalMap,uv).xyz*2.-1.;}float readRough(vec2 uv){return texture(roughMap,uv).r;}
'''
    vertex='''layout(location=0) in vec3 position;layout(location=1) in vec4 color;layout(location=2) in vec2 texcoord;layout(location=3) in vec3 inNormal;layout(location=4) in vec4 inTangent;layout(location=5) in vec3 inBase;layout(location=6) in vec4 inMaterial;
layout(location=0) out vec4 tint;layout(location=1) out vec2 uv;layout(location=2) out vec3 world;layout(location=3) out vec3 normal;layout(location=4) out vec4 tangent;layout(location=5) out vec3 base;layout(location=6) out vec4 material;
void main(){gl_Position=camera.vp*vec4(position,1);CLIP_CONVERSION tint=color;uv=texcoord;world=position;normal=inNormal;tangent=inTangent;base=inBase;material=inMaterial;}
'''
    camera='layout(push_constant) uniform Camera{mat4 vp;vec4 eye;vec4 options;}camera;\n'
    (ROOT/'src/museum.vert').write_text('#version 450\n'+camera+vertex.replace('CLIP_CONVERSION','gl_Position.y=-gl_Position.y;'))
    fragment='#version 450\n'+camera+'layout(set=0,binding=0) uniform sampler2D image;layout(set=0,binding=1) uniform sampler2D normalMap;layout(set=0,binding=2) uniform sampler2D roughMap;layout(set=0,binding=3) uniform sampler2D shadowMap;\n'+body+shared+'\nvoid main(){vec4 t=texture(image,uv);if(t.a<.5)discard;if(camera.options.x<.5){result=vec4(t.rgb*tint.rgb,1);return;}result=vec4(shadeSurface(world,normal,tangent,base,material,uv,t.rgb,camera.eye.xyz,camera.options.y,camera.options.z),1);}\n'
    (ROOT/'src/museum.frag').write_text(fragment)
    # Shader Model 3 has different resource declarations and varying semantics.
    hlsl=text.split('const char* shaderSource=R"(\n')[1].split(')";')[0]
    hlsl=hlsl.replace('cbuffer Camera : register(b0) { row_major float4x4 vp; float4 eye; float4 options; }','row_major float4x4 vp:register(c0);float4 eye:register(c4);float4 options:register(c5);')
    hlsl=hlsl.replace('Texture2D image:register(t0);Texture2D normalMap:register(t1);Texture2D roughMap:register(t2);Texture2D shadowMap:register(t3);SamplerState linearSampler:register(s0);','sampler2D image:register(s0);sampler2D normalMap:register(s1);sampler2D roughMap:register(s2);sampler2D shadowMap:register(s3);')
    for name in ['image','normalMap','roughMap']:hlsl=hlsl.replace(name+'.Sample(linearSampler,', 'tex2D('+name+',')
    hlsl=hlsl.replace('shadowMap.SampleLevel(linearSampler,uv,0)','tex2Dlod(shadowMap,float4(uv,0,0))')
    old='struct P {float4 p:SV_Position;float4 c:COLOR;float2 uv:TEXCOORD0;float3 world:TEXCOORD1;float3 n:NORMAL;float4 tangent:TANGENT;float3 base:COLOR1;float4 material:TEXCOORD2;};'
    fields='float4 c:COLOR0;float2 uv:TEXCOORD0;float3 world:TEXCOORD1;float3 n:TEXCOORD2;float4 tangent:TEXCOORD3;float3 base:TEXCOORD4;float4 material:TEXCOORD5;'
    hlsl=hlsl.replace(old,'struct P {float4 p:POSITION0;'+fields+'};struct Pixel{'+fields+'};')
    hlsl=hlsl.replace('float4 psMain(P p):SV_Target','float4 psMain(Pixel p):COLOR0')
    hlsl=hlsl.replace('if(options.w>.5){float value=floor(saturate(p.p.z)*65535.+.5);return float4(floor(value/256.)/255.,fmod(value,256.)/255.,0,1);}','')
    hlsl=hlsl.replace('for(int k=0;k<8;k++)','[loop] for(int k=0;k<8;k++)').replace('for(int y=-2;y<=2;y++)for(int x=-2;x<=2;x++)','[loop] for(int y=-2;y<=2;y++)[loop] for(int x=-2;x<=2;x++)')
    (ROOT/'src/dx9_shaders.h').write_text('#pragma once\nstatic const char* shader9Source=R"HLSL('+hlsl+')HLSL";\n')
    # Compatibility context is retained; the showcase uses real GLSL shaders.
    gl_camera='uniform mat4 viewProjection;uniform vec4 cameraEye,modeOptions;\n'
    gl_vert='#version 330 compatibility\n'+vertex.replace('camera.vp','viewProjection').replace('CLIP_CONVERSION','gl_Position.z=2.*gl_Position.z-gl_Position.w;')
    gl_frag='#version 330 compatibility\n'+gl_camera+'uniform sampler2D image,normalMap,roughMap,shadowMap;\n'+body+shared+'\nvoid main(){vec4 t=texture(image,uv);if(t.a<.5)discard;result=vec4(shadeSurface(world,normal,tangent,base,material,uv,t.rgb,cameraEye.xyz,modeOptions.y,modeOptions.z),1);}\n'
    # GLSL 330 has no explicit interface locations for varying variables.
    gl_vert=re.sub(r'layout\(location=\d+\) out ', 'out ',gl_vert)
    gl_frag=re.sub(r'layout\(location=\d+\) in ', 'in ',gl_frag)
    gl_vert=gl_vert.replace('#version 330 compatibility\n','#version 330 compatibility\n'+gl_camera)
    (ROOT/'src/gl_shaders.h').write_text('#pragma once\nstatic const char* glVertexSource=R"GLSL('+gl_vert+')GLSL";\nstatic const char* glFragmentSource=R"GLSL('+gl_frag+')GLSL";\n')
if __name__=='__main__':main()
