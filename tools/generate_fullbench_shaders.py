"""Derive core GL and GLES profiles from the same material implementation."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def main():
    text=(ROOT/'src/gl_shaders.h').read_text();vert=text.split('glVertexSource=R"GLSL(')[1].split(')GLSL";')[0];frag=text.split('glFragmentSource=R"GLSL(')[1].split(')GLSL";')[0]
    frag=frag.replace('if(t.a<.5)discard;result=', 'if(t.a<.5)discard;if(modeOptions.x<.5){result=vec4(t.rgb*tint.rgb,1);return;}result=')
    outputs=[]
    for name,version in [('core33','330 core'),('core46','460 core'),('es3','300 es'),('es2','100')]:
        v=vert.replace('330 compatibility',version);f=frag.replace('330 compatibility',version)
        if name.startswith('es'):
            v=v.replace('#version '+version+'\n','#version '+version+'\nprecision highp float;\nprecision highp int;\n');f=f.replace('#version '+version+'\n','#version '+version+'\nprecision highp float;\nprecision highp int;\n')
        if name=='es2':
            v=re.sub(r'layout\(location=\d+\) ', '',v).replace(' in ',' attribute ').replace(' out ',' varying ')
            # Declarations can immediately follow a semicolon, without spaces.
            v=re.sub(r'\bin\b','attribute',v);v=re.sub(r'\bout\b','varying',v)
            begin=f.index('vec3 shadeSurface');end=f.index('void main()',begin);f=f[:begin]+re.sub(r'\bresult\b','lightingResult',f[begin:end])+f[end:]
            f=f.replace('layout(location=0) out vec4 result;','');f=re.sub(r'\bin\b','varying',f);f=re.sub(r'\bresult\b','gl_FragColor',f).replace('texture(','texture2D(')
        if name.startswith('es'):
            # GLSL ES requires explicit floating-point constants in mixed arithmetic.
            for which,source in [('v',v),('f',f)]:
                source=re.sub(r'(?<![\w.])\d+(?![\w.])',lambda m:m[0]+'.0',source)
                source=source.replace('#version 100.0','#version 100').replace('#version 300.0','#version 300')
                source=re.sub(r'(location=\d+)\.0',r'\1',source)
                source=re.sub(r'(?<![.\w])([kxy]\s*(?:==|<=|<|=)\s*-?\d+)\.0',r'\1',source)
                if which=='v':v=source
                else:f=source
        outputs.append(f'static const char* {name}Vertex=R"GLSL({v})GLSL";\nstatic const char* {name}Fragment=R"GLSL({f})GLSL";\n')
    (ROOT/'src/fullbench_shaders.h').write_text('#pragma once\n'+''.join(outputs))
if __name__=='__main__':main()
