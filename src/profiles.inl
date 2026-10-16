// High detail assets are shared; showcase shading follows each native API path.
std::vector<uint32_t> vertexSpecular;
void limitTexture(Texture& t,unsigned maxWidth,unsigned maxHeight){
 float scale=std::min({1.f,float(maxWidth)/t.w,float(maxHeight)/t.h});if(scale>=1)return;
 unsigned w=std::max(1u,unsigned(t.w*scale)),h=std::max(1u,unsigned(t.h*scale));std::vector<uint8_t> pixels(size_t(w)*h*4);
 for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){float sx=(x+.5f)*t.w/w-.5f,sy=(y+.5f)*t.h/h-.5f;int x0=std::max(0,int(floorf(sx))),y0=std::max(0,int(floorf(sy))),x1=std::min(x0+1,int(t.w)-1),y1=std::min(y0+1,int(t.h)-1);float fx=sx-floorf(sx),fy=sy-floorf(sy);for(unsigned c=0;c<4;c++){float a=t.pixels[(size_t(y0)*t.w+x0)*4+c]*(1-fx)+t.pixels[(size_t(y0)*t.w+x1)*4+c]*fx,b=t.pixels[(size_t(y1)*t.w+x0)*4+c]*(1-fx)+t.pixels[(size_t(y1)*t.w+x1)*4+c]*fx;pixels[(size_t(y)*w+x)*4+c]=uint8_t(a*(1-fy)+b*fy+.5f);}}
 t.w=w;t.h=h;t.pixels=std::move(pixels);
}
Json effectList(){
 if(!showcase)return Json::array({"highest-detail meshes","matched baked multi-light shading","matched 2048px texture set","alpha-tested hair","depth testing"});
#if BACKEND==40
 return Json::array({"highest-detail meshes","full authored color maps","CPU perspective-correct bilinear rasterizer","CPU depth and alpha tests","eight-light Gouraud shading","view-dependent specular/fog","native DirectDraw surface blits"});
#elif BACKEND==41
 return Json::array({"highest-detail meshes","streamed 256px ARGB1555 atlas regions","eight-light Gouraud shading","vertex specular/fog","native Glide textured triangles","native alpha and depth tests"});
#elif BACKEND<9 || defined(LEGACY_MATERIALS)
 return Json::array({"highest-detail meshes","full authored color textures subject to device limits","eight-light Gouraud shading","view-dependent specular highlights","native specular/fog interpolation","perspective-correct textures","alpha-tested hair"});
#else
 return Json::array({"highest-detail meshes","full authored color/normal/roughness textures","tangent-space normal mapping","eight-light per-pixel GGX shading","25-tap filtered baked key-light shadows","roughness/metallic material response","Fresnel reflections","skin wrap/transmission","procedural marble and brass floor","distance/height atmosphere","ACES tone mapping","maximum supported anisotropic filtering","alpha-tested hair"});
#endif
}
struct PortraitLight{XMFLOAT3 p,c;float power;};
PortraitLight profileLights[8]={
 {{-2.7f,4.2f,3.5f},{1.f,.72f,.48f},9},{{3.2f,3.6f,2},{.50f,.72f,1.f},8},
 {{-5,4.8f,-4},{1,.75f,.5f},14},{{5,4.8f,-4},{.5f,.7f,1},16},
 {{-4.5f,5,-8},{1,.7f,.4f},16},{{4.5f,5,-8},{.4f,.65f,1},16},
 {{4.4f,2.9f,5.3f},{1,.87f,.72f},5.8f},{{1.1f,2.6f,2.3f},{.45f,.65f,1},3.4f}};
void updateLegacyLighting(){
 vertexSpecular.resize(vertices.size());
 for(size_t i=0;i<vertices.size();i++){
  auto& v=vertices[i];auto& s=shading[i];auto N=XMLoadFloat3(reinterpret_cast<const XMFLOAT3*>(s.normal));auto P=XMLoadFloat3(reinterpret_cast<const XMFLOAT3*>(v.p));auto V=XMVector3Normalize(XMVectorSubtract(XMLoadFloat3(&cameraEye),P));
  float diffuse[3]={.24f,.28f,.34f},specular[3]{};
  for(auto light:profileLights){auto delta=XMVectorSubtract(XMLoadFloat3(&light.p),P);float d2=XMVectorGetX(XMVector3LengthSq(delta));auto L=XMVector3Normalize(delta);float lambert=std::max(0.f,XMVectorGetX(XMVector3Dot(N,L)));auto half=XMVector3Normalize(XMVectorAdd(L,V));float nh=std::max(0.f,XMVectorGetX(XMVector3Dot(N,half)));float fall=light.power*(1+.05f*sinf(simulationTime*1.1f))/(1+d2);float highlight=powf(nh,12+80*(1-s.params[2]))*fall*(s.params[1]>.5f?.65f:.18f);const float* color=&light.c.x;for(unsigned c=0;c<3;c++){diffuse[c]+=lambert*fall*color[c];specular[c]+=highlight*color[c];}}
  uint32_t packed=0;for(unsigned c=0;c<3;c++){float value=std::clamp(powf(std::max(diffuse[c],0.f),.4545f)*s.base[c],0.f,1.f);packed|=uint32_t(value*255+.5f)<<(c*8);}v.color=packed|0xFF000000;
  float distance=XMVectorGetX(XMVector3Length(XMVectorSubtract(P,XMLoadFloat3(&cameraEye))));unsigned fog=unsigned(std::clamp(expf(-distance*.014f),0.f,1.f)*255+.5f);
  vertexSpecular[i]=(fog<<24)|(uint32_t(std::clamp(specular[0],0.f,1.f)*255)<<16)|(uint32_t(std::clamp(specular[1],0.f,1.f)*255)<<8)|uint32_t(std::clamp(specular[2],0.f,1.f)*255);
 }
}
