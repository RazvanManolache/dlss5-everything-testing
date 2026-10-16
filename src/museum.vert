#version 450
layout(push_constant) uniform Camera{mat4 vp;vec4 eye;vec4 options;}camera;
layout(location=0) in vec3 position;layout(location=1) in vec4 color;layout(location=2) in vec2 texcoord;layout(location=3) in vec3 inNormal;layout(location=4) in vec4 inTangent;layout(location=5) in vec3 inBase;layout(location=6) in vec4 inMaterial;
layout(location=0) out vec4 tint;layout(location=1) out vec2 uv;layout(location=2) out vec3 world;layout(location=3) out vec3 normal;layout(location=4) out vec4 tangent;layout(location=5) out vec3 base;layout(location=6) out vec4 material;
void main(){gl_Position=camera.vp*vec4(position,1);gl_Position.y=-gl_Position.y; tint=color;uv=texcoord;world=position;normal=inNormal;tangent=inTangent;base=inBase;material=inMaterial;}
