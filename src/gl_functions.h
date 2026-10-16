#pragma once
#include <cstddef>
template<class T>T glFunction(const char* name){auto p=wglGetProcAddress(name);ensure(p!=nullptr,std::string("Missing OpenGL function: ")+name);return reinterpret_cast<T>(p);}
#define GLFN(ret,name,args) using name##Type=ret(APIENTRY*)args;static name##Type name;
GLFN(GLuint,glCreateShader,(GLenum))
GLFN(void,glShaderSource,(GLuint,GLsizei,const char* const*,const GLint*))
GLFN(void,glCompileShader,(GLuint))
GLFN(void,glGetShaderiv,(GLuint,GLenum,GLint*))
GLFN(void,glGetShaderInfoLog,(GLuint,GLsizei,GLsizei*,char*))
GLFN(GLuint,glCreateProgram,())
GLFN(void,glAttachShader,(GLuint,GLuint))
GLFN(void,glLinkProgram,(GLuint))
GLFN(void,glGetProgramiv,(GLuint,GLenum,GLint*))
GLFN(void,glGetProgramInfoLog,(GLuint,GLsizei,GLsizei*,char*))
GLFN(void,glDeleteShader,(GLuint))
GLFN(void,glDeleteProgram,(GLuint))
GLFN(void,glUseProgram,(GLuint))
GLFN(GLint,glGetUniformLocation,(GLuint,const char*))
GLFN(void,glUniformMatrix4fv,(GLint,GLsizei,GLboolean,const GLfloat*))
GLFN(void,glUniform4f,(GLint,GLfloat,GLfloat,GLfloat,GLfloat))
GLFN(void,glUniform1i,(GLint,GLint))
GLFN(void,glEnableVertexAttribArray,(GLuint))
GLFN(void,glVertexAttribPointer,(GLuint,GLint,GLenum,GLboolean,GLsizei,const void*))
GLFN(void,glActiveTexture,(GLenum))
GLFN(void,glGenerateMipmap,(GLenum))
GLFN(void,glBindAttribLocation,(GLuint,GLuint,const char*))
GLFN(void,glGenVertexArrays,(GLsizei,GLuint*))
GLFN(void,glBindVertexArray,(GLuint))
GLFN(void,glDeleteVertexArrays,(GLsizei,const GLuint*))
GLFN(void,glGenBuffers,(GLsizei,GLuint*))
GLFN(void,glBindBuffer,(GLenum,GLuint))
GLFN(void,glBufferData,(GLenum,std::ptrdiff_t,const void*,GLenum))
GLFN(void,glDeleteBuffers,(GLsizei,const GLuint*))
#undef GLFN
void loadGLFunctions(){
#define LOAD(name) name=glFunction<name##Type>(#name)
LOAD(glCreateShader);LOAD(glShaderSource);LOAD(glCompileShader);LOAD(glGetShaderiv);LOAD(glGetShaderInfoLog);LOAD(glCreateProgram);LOAD(glAttachShader);LOAD(glLinkProgram);LOAD(glGetProgramiv);LOAD(glGetProgramInfoLog);LOAD(glDeleteShader);LOAD(glDeleteProgram);LOAD(glUseProgram);LOAD(glGetUniformLocation);LOAD(glUniformMatrix4fv);LOAD(glUniform4f);LOAD(glUniform1i);LOAD(glEnableVertexAttribArray);LOAD(glVertexAttribPointer);LOAD(glActiveTexture);LOAD(glGenerateMipmap);
LOAD(glBindAttribLocation);LOAD(glGenVertexArrays);LOAD(glBindVertexArray);LOAD(glDeleteVertexArrays);LOAD(glGenBuffers);LOAD(glBindBuffer);LOAD(glBufferData);LOAD(glDeleteBuffers);
#undef LOAD
}
