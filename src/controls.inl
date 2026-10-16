// Shared by every Windows API fixture; never polls global keyboard state.
bool animationsEnabled=true,cameraMotionEnabled=true,orbitMode=false;
bool heldKeys[256]{},mouseLooking=false;
int mouseX=0,mouseY=0;
float cameraTime=0,viewYaw=0,viewPitch=0,orbitDistance=1,moveSpeed=.6f;
XMFLOAT3 viewEye{},viewTarget{};
bool frozen(){return paused||fixedTime;}
XMVECTOR viewDirection(){float c=cosf(viewPitch);return XMVectorSet(sinf(viewYaw)*c,sinf(viewPitch),cosf(viewYaw)*c,0);}
void clampView(){viewPitch=std::clamp(viewPitch,-1.48f,1.48f);orbitDistance=std::clamp(orbitDistance,.12f,60.f);}
void resetView(){
 viewEye=room?XMFLOAT3{0,2.5f,9}:initialEye;
 viewTarget=room?XMFLOAT3{0,1.3f,-3}:initialTarget;
 auto delta=XMVectorSubtract(XMLoadFloat3(&viewTarget),XMLoadFloat3(&viewEye));
 orbitDistance=std::max(.12f,XMVectorGetX(XMVector3Length(delta)));
 XMFLOAT3 d;XMStoreFloat3(&d,delta);viewYaw=atan2f(d.x,d.z);viewPitch=atan2f(d.y,sqrtf(d.x*d.x+d.z*d.z));
 cameraTime=0;
}
void setOrbit(bool enabled){
 if(enabled==orbitMode)return;
 if(enabled)XMStoreFloat3(&viewTarget,XMVectorAdd(XMLoadFloat3(&viewEye),XMVectorScale(viewDirection(),orbitDistance)));
 else XMStoreFloat3(&viewEye,XMVectorSubtract(XMLoadFloat3(&viewTarget),XMVectorScale(viewDirection(),orbitDistance)));
 orbitMode=enabled;
}
void toggleFreeze(){if(fixedTime){fixedTime=false;paused=false;}else paused=!paused;}
void moveCamera(float dt){
 if(!frozen()){
  if(animationsEnabled)simulationTime+=dt;
  if(cameraMotionEnabled){cameraTime+=dt;if(orbitMode)viewYaw+=dt*.22f;}
 }
 if(!background&&GetForegroundWindow()==windowHandle){
  float forward=float(heldKeys['W']||heldKeys[VK_UP])-float(heldKeys['S']||heldKeys[VK_DOWN]);
  float right=float(heldKeys['D']||heldKeys[VK_RIGHT])-float(heldKeys['A']||heldKeys[VK_LEFT]);
  float up=float(heldKeys['E'])-float(heldKeys['Q']);
  viewYaw+=(float(heldKeys['J'])-float(heldKeys['L']))*dt;
  viewPitch+=(float(heldKeys['I'])-float(heldKeys['K']))*dt;
  if(orbitMode){viewYaw+=right*dt;viewPitch+=up*dt*.6f;orbitDistance*=expf(-forward*dt);}
  else{
   auto f=viewDirection(),r=XMVector3Normalize(XMVector3Cross(f,XMVectorSet(0,1,0,0)));
   auto direction=XMVectorAdd(XMVectorAdd(XMVectorScale(f,forward),XMVectorScale(r,right)),XMVectorSet(0,up,0,0));
   float length=XMVectorGetX(XMVector3Length(direction));
   if(length>0)XMStoreFloat3(&viewEye,XMVectorAdd(XMLoadFloat3(&viewEye),XMVectorScale(direction,dt*moveSpeed*(room?5.f:1.f)*(heldKeys[VK_SHIFT]?4.f:1.f)/length)));
  }
 }
 clampView();
}
void scrollCamera(float delta){
 if(orbitMode){orbitDistance*=expf(-delta*.12f);clampView();}
 else XMStoreFloat3(&viewEye,XMVectorAdd(XMLoadFloat3(&viewEye),XMVectorScale(viewDirection(),delta*moveSpeed*.2f)));
}
Json controlsInfo(){return {{"frozen",frozen()},{"animations_enabled",animationsEnabled},{"camera_motion_enabled",cameraMotionEnabled},{"camera_mode",orbitMode?"orbit":"free"},{"simulation_seconds",simulationTime},{"camera_seconds",cameraTime},{"camera_eye",{cameraEye.x,cameraEye.y,cameraEye.z}},{"yaw",viewYaw},{"pitch",viewPitch},{"orbit_distance",orbitDistance},{"character_pose","baked static pose"}};}
HMENU createControlsMenu(){
 HMENU bar=CreateMenu(),menu=CreatePopupMenu();
 AppendMenuW(menu,MF_STRING,2000+'F',L"Freeze automatic motion\tF / Space");
 AppendMenuW(menu,MF_STRING,2000+'T',L"Animate lighting\tT");
 AppendMenuW(menu,MF_STRING,2000+'B',L"Animate camera\tB");
 AppendMenuW(menu,MF_STRING,2000+'O',L"Orbit camera\tO");
 AppendMenuW(menu,MF_SEPARATOR,0,nullptr);
 AppendMenuW(menu,MF_STRING,2000+VK_F1,L"Room view\tF1");
 AppendMenuW(menu,MF_STRING,2000+VK_F2,L"Focused face\tF2");
 AppendMenuW(menu,MF_STRING,2000+'R',L"Reset view and animation time\tR");
 AppendMenuW(menu,MF_STRING,2000+VK_F12,L"Save screenshot\tF12");
 AppendMenuW(menu,MF_SEPARATOR,0,nullptr);
 AppendMenuW(menu,MF_STRING|MF_GRAYED,0,L"WASD / arrows: move; Q / E: down / up");
 AppendMenuW(menu,MF_STRING|MF_GRAYED,0,L"Right-drag / IJKL: look; wheel: zoom; Shift: faster");
 AppendMenuW(bar,MF_POPUP,reinterpret_cast<UINT_PTR>(menu),L"Museum controls");return bar;
}
