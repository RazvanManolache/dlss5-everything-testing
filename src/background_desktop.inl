// Some historical wrappers create/show their own windows. Keep those windows
// on a private, non-input desktop during automated runs. Never switch desktops.
HDESK originalDesktop{},renderDesktop{};bool isolatedBackground=false;
void isolateBackground(){
#ifdef ISOLATE_BACKGROUND
 if(!background)return;originalDesktop=GetThreadDesktop(GetCurrentThreadId());std::wstring name=L"MuseumFixture_"+std::to_wstring(GetCurrentProcessId());renderDesktop=CreateDesktopW(name.c_str(),nullptr,nullptr,0,GENERIC_ALL,nullptr);ensure(renderDesktop!=nullptr,"Private render desktop");ensure(SetThreadDesktop(renderDesktop)!=FALSE,"Attach private render desktop");isolatedBackground=true;
#endif
}
void closeBackgroundDesktop(){if(renderDesktop&&SetThreadDesktop(originalDesktop)){CloseDesktop(renderDesktop);renderDesktop=nullptr;}}
