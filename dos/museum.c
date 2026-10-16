/* DOS protected-mode VGA gallery. Original software rasterizer; no Windows API. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <conio.h>
#include <dpmi.h>
#include <go32.h>
#include <sys/farptr.h>
#include <sys/movedata.h>
#include <pc.h>

#define W 320
#define H 200
#define TEX 65536
typedef struct {float x,y,z,u,v,light;} Vertex;
typedef struct {uint32_t i[3];uint16_t tex,pad;} Triangle;
typedef struct {float x,y,z,u,v,l;} View;
typedef struct {float x,y,q,u,v,l;} Screen;
static Vertex *vertices;
static Triangle *triangles;
static View *view;
static uint32_t nv,nt,texture_count;
static unsigned char *textures, palette[768], shades[8192],pixels[W*H],font[2048];
static float depth[W*H],initial[6],eye[3],target[3],yaw,pitch;
static int room=0,paused=0,fixed=0,showcase=1,quit=0,screen_set=0;
static int orbit_mode=0,animations_enabled=1,camera_motion=1;
static double scene_time=0,camera_time=0;
static float orbit_distance=1;
static unsigned long frames=0,submitted=0,pixel_writes=0;
static double duration=0,capture_every=0,clock_start=0,maximum_frame=0;
#define MAX_CAPTURES 10000
typedef struct {double requested,elapsed;unsigned long frame;int shared;char bmp[13];} Capture;
static double capture_times[MAX_CAPTURES];
static Capture captures[MAX_CAPTURES];
static int time_count=0,next_capture=0,capture_count=0,explicit_times=0;
static unsigned long frame_limit=0;

static void text_mode(void){__dpmi_regs r;memset(&r,0,sizeof(r));r.x.ax=3;__dpmi_int(0x10,&r);screen_set=0;}
static void fail(const char *s){if(screen_set)text_mode();fprintf(stderr,"Gallery: %s\n",s);exit(1);}
static double number(const char *s){char *end;double v=strtod(s,&end);if(end==s||*end||!__builtin_isfinite(v)||v<0)fail("times must be finite nonnegative numbers");return v;}
static void add_time(double value){if(time_count>=MAX_CAPTURES)fail("at most 10000 screenshots per run");capture_times[time_count++]=value;}
static void add_times(const char *csv){char *copy=malloc(strlen(csv)+1),*start,*comma;if(!copy)fail("out of memory");strcpy(copy,csv);start=copy;do{comma=strchr(start,',');if(comma)*comma=0;add_time(number(start));if(!comma)break;start=comma+1;}while(1);free(copy);explicit_times=1;}
static int compare_times(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return x<y?-1:x>y;}
static void prepare_schedule(void){int i,n=0;
    if(capture_every>0){if(duration<=0)fail("--capture-every requires --seconds");for(i=1;i*capture_every<=duration+1e-9;i++){double t=i*capture_every;add_time(t>duration?duration:t);}if(!time_count)fail("capture interval exceeds run time");}
    if(!explicit_times&&capture_every==0){if(duration>0)add_time(duration/2);else if(!frame_limit)add_time(15);}
    qsort(capture_times,time_count,sizeof(double),compare_times);
    for(i=0;i<time_count;i++){if(duration>0&&capture_times[i]>duration)fail("screenshot time exceeds run time");if(!n||fabs(capture_times[i]-capture_times[n-1])>=1e-9)capture_times[n++]=capture_times[i];}time_count=n;
}
static void read_exact(FILE *f,void *data,size_t size){if(fread(data,1,size,f)!=size)fail("truncated asset file");}
static void load(void){
    uint32_t head[4];FILE *f=NULL;
    const char *paths[]={"ASSETS/GALLERY.DAT","../../DOS/ASSETS/GALLERY.DAT","../../../DOS/ASSETS/GALLERY.DAT","D:/GALLERY.DAT"};
    unsigned i;for(i=0;i<sizeof(paths)/sizeof(paths[0])&&!f;i++)f=fopen(paths[i],"rb");
    if(!f)fail("missing common GALLERY.DAT");
    read_exact(f,head,16);if(head[0]!=0x31534F44||head[1]>2000000||head[2]>2000000||head[3]!=24)fail("invalid asset header");
    nv=head[1];nt=head[2];texture_count=head[3];read_exact(f,initial,24);read_exact(f,palette,768);read_exact(f,shades,8192);
    vertices=malloc(nv*sizeof(Vertex));triangles=malloc(nt*sizeof(Triangle));view=malloc(nv*sizeof(View));textures=malloc(texture_count*TEX);
    if(!vertices||!triangles||!view||!textures)fail("not enough memory (use 32 MB or more)");
    read_exact(f,vertices,nv*sizeof(Vertex));read_exact(f,triangles,nt*sizeof(Triangle));read_exact(f,textures,texture_count*TEX);fclose(f);
}
static void set_view(void){
    if(room){eye[0]=0;eye[1]=2.5f;eye[2]=9;target[0]=0;target[1]=1.3f;target[2]=-3;}
    else{memcpy(eye,initial,12);memcpy(target,initial+3,12);}
    yaw=atan2(target[0]-eye[0],target[2]-eye[2]);
    pitch=atan2(target[1]-eye[1],sqrt((target[0]-eye[0])*(target[0]-eye[0])+(target[2]-eye[2])*(target[2]-eye[2])));
    orbit_distance=sqrt((target[0]-eye[0])*(target[0]-eye[0])+(target[1]-eye[1])*(target[1]-eye[1])+(target[2]-eye[2])*(target[2]-eye[2]));camera_time=0;
}
static void clamp_view(void){if(pitch>1.48f)pitch=1.48f;if(pitch<-1.48f)pitch=-1.48f;if(orbit_distance<.12f)orbit_distance=.12f;if(orbit_distance>60)orbit_distance=60;}
static void set_orbit(int enabled){
    if(enabled==orbit_mode)return;
    if(enabled){target[0]=eye[0]+sin(yaw)*cos(pitch)*orbit_distance;target[1]=eye[1]+sin(pitch)*orbit_distance;target[2]=eye[2]+cos(yaw)*cos(pitch)*orbit_distance;}
    orbit_mode=enabled;
}
static void move_view(float forward,float right,float up){
    float step=room?.18f:.03f;
    if(orbit_mode){yaw+=right*.10f;pitch+=up*.07f;orbit_distance*=exp(-forward*.08f);clamp_view();}
    else{eye[0]+=(sin(yaw)*cos(pitch)*forward-cos(yaw)*right)*step;eye[1]+=(sin(pitch)*forward+up)*step;eye[2]+=(cos(yaw)*cos(pitch)*forward+sin(yaw)*right)*step;}
}
static void update_camera(double dt){
    if(dt>.1)dt=.1;
    if(!paused&&!fixed){if(animations_enabled)scene_time+=dt;if(camera_motion){camera_time+=dt;if(orbit_mode)yaw+=dt*.22;}}
    clamp_view();
    if(orbit_mode){eye[0]=target[0]-sin(yaw)*cos(pitch)*orbit_distance;eye[1]=target[1]-sin(pitch)*orbit_distance;eye[2]=target[2]-cos(yaw)*cos(pitch)*orbit_distance;}
}
static void vga(void){
    __dpmi_regs r;int i;memset(&r,0,sizeof(r));r.x.ax=0x1130;r.h.bh=3;__dpmi_int(0x10,&r);
    dosmemget(((unsigned long)r.x.es<<4)+r.x.bp,2048,font);
    memset(&r,0,sizeof(r));r.x.ax=0x13;__dpmi_int(0x10,&r);screen_set=1;
    outportb(0x3c8,0);for(i=0;i<768;i++)outportb(0x3c9,palette[i]>>2);
}
static void print_at(int x,int y,const char *s,int color){int a,b;while(*s){unsigned char c=*s++;for(b=0;b<8;b++)for(a=0;a<8;a++)if(font[c*8+b]&(128>>a)){int px=x+a,py=y+b;if(px>=0&&px<W&&py>=0&&py<H)pixels[py*W+px]=color;}x+=8;}}
static float cross2(float ax,float ay,float bx,float by){return ax*by-ay*bx;}
static float min2(float a,float b){return a<b?a:b;}
static float max2(float a,float b){return a>b?a:b;}
static Screen project(View v){Screen s;s.q=1/v.z;s.x=160-v.x*s.q*292;s.y=100-v.y*s.q*243;s.u=v.u*s.q;s.v=v.v*s.q;s.l=v.l*s.q;return s;}
static void raster(View a,View b,View c,unsigned tex){
    Screen p=project(a),q=project(b),r=project(c);
    float area=cross2(q.x-p.x,q.y-p.y,r.x-p.x,r.y-p.y),inv;
    int x,y,x0,x1,y0,y1;float aa,bb,cc,dq,du,dv,dl;unsigned char *map=textures+tex*TEX;
    if(fabs(area)<.04f)return;
    x0=(int)floor(min2(p.x,min2(q.x,r.x)));x1=(int)ceil(max2(p.x,max2(q.x,r.x)));
    y0=(int)floor(min2(p.y,min2(q.y,r.y)));y1=(int)ceil(max2(p.y,max2(q.y,r.y)));
    if(x1<0||x0>=W||y1<14||y0>=H-12)return;
    if(x0<0)x0=0;if(x1>=W)x1=W-1;if(y0<14)y0=14;if(y1>=H-12)y1=H-13;
    inv=1/area;submitted++;
    for(y=y0;y<=y1;y++){
        aa=cross2(q.x-(x0+.5f),q.y-(y+.5f),r.x-(x0+.5f),r.y-(y+.5f))*inv;
        bb=cross2(r.x-(x0+.5f),r.y-(y+.5f),p.x-(x0+.5f),p.y-(y+.5f))*inv;
        cc=1-aa-bb;dq=(q.y-r.y)*inv;du=(r.y-p.y)*inv;dv=-dq-du;
        for(x=x0;x<=x1;x++,aa+=dq,bb+=du,cc+=dv){
            float iz;int at=y*W+x,u,v,shade;unsigned char color;
            if(aa<-.0001f||bb<-.0001f||cc<-.0001f)continue;
            iz=aa*p.q+bb*q.q+cc*r.q;if(iz<=depth[at])continue;
            u=(int)((aa*p.u+bb*q.u+cc*r.u)/iz*256);v=(int)((aa*p.v+bb*q.v+cc*r.v)/iz*256);
            color=map[((v&255)<<8)|(u&255)];if(color==255)continue;
            dl=(aa*p.l+bb*q.l+cc*r.l)/iz;
            shade=showcase?(int)(dl*31):31;if(shade<0)shade=0;if(shade>31)shade=31;
            depth[at]=iz;pixels[at]=shades[shade*256+color];pixel_writes++;
        }
    }
}
static View interpolate(View a,View b,float t){View v;v.x=a.x+(b.x-a.x)*t;v.y=a.y+(b.y-a.y)*t;v.z=.05f;v.u=a.u+(b.u-a.u)*t;v.v=a.v+(b.v-a.v)*t;v.l=a.l+(b.l-a.l)*t;return v;}
static void triangle(Triangle t){
    View in[3],out[5];int n=0,i;for(i=0;i<3;i++){if(t.i[i]>=nv)return;in[i]=view[t.i[i]];}
    for(i=0;i<3;i++){View a=in[i],b=in[(i+1)%3];int ia=a.z>=.05f,ib=b.z>=.05f;
        if(ia)out[n++]=a;if(ia!=ib)out[n++]=interpolate(a,b,(.05f-a.z)/(b.z-a.z));}
    for(i=1;i+1<n;i++)raster(out[0],out[i],out[i+1],t.tex);
}
static void render(double elapsed){
    unsigned i;float sy=sin(yaw),cy=cos(yaw),sp=sin(pitch),cp=cos(pitch);
    float ex=eye[0],ey=eye[1],ez=eye[2];char label[80];
    if(!orbit_mode){ex+=.009f*sin(camera_time*.5);ey+=.004f*sin(camera_time*.7);}
    memset(pixels,245,sizeof(pixels));memset(depth,0,sizeof(depth));
    for(i=0;i<nv;i++){
        Vertex v=vertices[i];float x=v.x-ex,y=v.y-ey,z=v.z-ez;
        view[i].x=x*cy-z*sy;view[i].y=-x*sy*sp+y*cp-z*cy*sp;view[i].z=x*sy*cp+y*sp+z*cy*cp;
        view[i].u=v.u;view[i].v=v.v;view[i].l=v.light*(1+.05f*sin(scene_time*1.1));
    }
    for(i=0;i<nt;i++)triangle(triangles[i]);
    memset(pixels,245,W*14);memset(pixels+W*(H-12),245,W*12);
    sprintf(label,"DOS %s %s %s %.1f FPS",room?"ROOM":"FACE",orbit_mode?"ORBIT":"FREE",paused||fixed?"FROZEN":"LIVE",elapsed>0?frames/elapsed:0);print_at(4,3,label,241);
    print_at(4,H-10,"WASD MOVE F FREEZE O ORBIT T FX B CAM",240);
    dosmemput(pixels,sizeof(pixels),0xa0000);
}
static void put16(FILE *f,unsigned v){fputc(v&255,f);fputc(v>>8,f);}
static void put32(FILE *f,unsigned long v){put16(f,v&65535);put16(f,v>>16);}
static void write_bmp(const char *filename){
    int i,y;FILE *f=fopen(filename,"wb");if(!f)fail("cannot write screenshot");
    /* Read the actual emulated VGA framebuffer, including the HUD. */
    dosmemget(0xa0000,sizeof(pixels),pixels);
    fputc('B',f);fputc('M',f);put32(f,1078+W*H);put32(f,0);put32(f,1078);
    put32(f,40);put32(f,W);put32(f,H);put16(f,1);put16(f,8);put32(f,0);put32(f,W*H);
    put32(f,0);put32(f,0);put32(f,256);put32(f,256);
    for(i=0;i<256;i++){fputc(palette[i*3+2]&252,f);fputc(palette[i*3+1]&252,f);fputc(palette[i*3]&252,f);fputc(0,f);}
    for(y=H-1;y>=0;y--)if(fwrite(pixels+y*W,1,W,f)!=W)fail("screenshot write failed");if(fclose(f))fail("screenshot close failed");
}
static void capture(double requested,double actual,int shared){
    Capture *record;if(capture_count>=MAX_CAPTURES)fail("too many screenshots");record=&captures[capture_count++];
    record->requested=requested;record->elapsed=actual;record->frame=frames;record->shared=shared;
    sprintf(record->bmp,"CAP%05d.BMP",capture_count);write_bmp(record->bmp);
    if(capture_count==1)write_bmp("CAPTURE.BMP");
}
static void keys(void){while(kbhit()){
    int c=getch();if(c==0||c==224){c=getch();
        if(c==59){room=1;set_view();}if(c==60){room=0;set_view();}
        if(c==75)move_view(0,-1,0);if(c==77)move_view(0,1,0);if(c==72)move_view(1,0,0);if(c==80)move_view(-1,0,0);
        if(c==134)capture(-1,(double)uclock()/UCLOCKS_PER_SEC-clock_start,0);
    }else{
        if(c==27)quit=1;
        if(c==' '||c=='f'||c=='F'){if(fixed){fixed=0;paused=0;}else paused=!paused;}
        if(c=='r'||c=='R'){scene_time=0;set_view();}
        if(c=='o'||c=='O')set_orbit(!orbit_mode);
        if(c=='t'||c=='T')animations_enabled=!animations_enabled;
        if(c=='b'||c=='B')camera_motion=!camera_motion;
        if(c=='w'||c=='W')move_view(1,0,0);if(c=='s'||c=='S')move_view(-1,0,0);
        if(c=='a'||c=='A')move_view(0,-1,0);if(c=='d'||c=='D')move_view(0,1,0);
        if(c=='q'||c=='Q')move_view(0,0,-1);if(c=='e'||c=='E')move_view(0,0,1);
        if(c=='j'||c=='J')yaw+=.10f;if(c=='l'||c=='L')yaw-=.10f;
        if(c=='i'||c=='I')pitch+=.07f;if(c=='k'||c=='K')pitch-=.07f;
        clamp_view();
    }
}}
int main(int argc,char **argv){
    int i;double elapsed=0;FILE *log;
    if(sizeof(Vertex)!=24||sizeof(Triangle)!=16)fail("compiler packing mismatch");
    for(i=1;i<argc;i++){
        if(!strcmp(argv[i],"--room"))room=1;
        else if(!strcmp(argv[i],"--fixed-time"))fixed=1;
        else if(!strcmp(argv[i],"--freeze"))paused=1;
        else if(!strcmp(argv[i],"--tour")||!strcmp(argv[i],"--orbit"))orbit_mode=1;
        else if(!strcmp(argv[i],"--camera")&&i+1<argc){const char *v=argv[++i];if(strcmp(v,"free")&&strcmp(v,"orbit"))fail("--camera must be free or orbit");orbit_mode=!strcmp(v,"orbit");}
        else if((!strcmp(argv[i],"--animations")||!strcmp(argv[i],"--camera-motion"))&&i+1<argc){int is_scene=!strcmp(argv[i],"--animations");const char *v=argv[++i];if(strcmp(v,"on")&&strcmp(v,"off"))fail("animation options must be on or off");if(is_scene)animations_enabled=!strcmp(v,"on");else camera_motion=!strcmp(v,"on");}
        else if(!strcmp(argv[i],"--no-animations"))animations_enabled=0;
        else if(!strcmp(argv[i],"--seconds")&&i+1<argc)duration=number(argv[++i]);
        else if(!strcmp(argv[i],"--capture-at")&&i+1<argc)add_times(argv[++i]);
        else if(!strcmp(argv[i],"--capture-every")&&i+1<argc){capture_every=number(argv[++i]);if(capture_every<=0)fail("capture interval must be positive");}
        else if(!strcmp(argv[i],"--capture-file")&&i+1<argc){double t;FILE *f=fopen(argv[++i],"r");if(!f)fail("missing capture schedule");while(fscanf(f,"%lf",&t)==1){if(!__builtin_isfinite(t)||t<0)fail("invalid schedule time");add_time(t);}if(!feof(f)||!time_count)fail("invalid capture schedule");fclose(f);explicit_times=1;}
        else if(!strcmp(argv[i],"--frames")&&i+1<argc)frame_limit=atol(argv[++i]);
        else if(!strcmp(argv[i],"--mode")&&i+1<argc)showcase=strcmp(argv[++i],"matched")!=0;
        else fail("unknown argument");
    }
    prepare_schedule();load();set_view();vga();clock_start=(double)uclock()/UCLOCKS_PER_SEC;
    log=fopen("FPS.CSV","w");if(log)fprintf(log,"frame,elapsed_seconds\n");
    {double last_frame=clock_start;
    while(!quit){
        keys();
        double frame_start=(double)uclock()/UCLOCKS_PER_SEC;int due;
        update_camera(frame_start-last_frame);last_frame=frame_start;
        elapsed=frame_start-clock_start;render(elapsed);frames++;
        elapsed=(double)uclock()/UCLOCKS_PER_SEC-clock_start;
        if(log)fprintf(log,"%lu,%.17g\n",frames,elapsed);
        due=next_capture;while(due<time_count&&capture_times[due]<=elapsed)due++;
        {int shared=due-next_capture>1;while(next_capture<due)capture(capture_times[next_capture++],elapsed,shared);}
        {double cost=(double)uclock()/UCLOCKS_PER_SEC-frame_start;if(cost>maximum_frame)maximum_frame=cost;}
        elapsed=(double)uclock()/UCLOCKS_PER_SEC-clock_start;
        if((duration>0&&elapsed>=duration&&!(next_capture<time_count&&capture_times[next_capture]<=elapsed))||(frame_limit>0&&frames>=frame_limit))quit=1;
    }}
    if(!capture_count)capture(-1,elapsed,0);
    if(log)fclose(log);text_mode();
    log=fopen("RESULT.JSN","w");if(log){
        fprintf(log,"{\"state\":\"complete\",\"platform\":\"DOS\",\"renderer\":\"CPU / VGA mode 13h\",\"width\":320,\"height\":200,\"palette_colors\":256,\"vertices\":%lu,\"triangles\":%lu,\"frames\":%lu,\"seconds\":%.17g,\"average_fps\":%.17g,\"capture_seconds\":%.17g,\"submitted_triangles\":%lu,\"pixel_writes\":%lu,\"room\":%s,\"mode\":\"%s\",\"maximum_frame_seconds\":%.17g,\"pending_captures\":%d,\"capture_times\":[",(unsigned long)nv,(unsigned long)nt,frames,elapsed,frames/(elapsed>.001?elapsed:.001),captures[0].elapsed,submitted,pixel_writes,room?"true":"false",showcase?"showcase":"matched",maximum_frame,time_count-next_capture);
        for(i=0;i<time_count;i++)fprintf(log,"%s%.17g",i?",":"",capture_times[i]);fprintf(log,"],\"captures\":[");
        for(i=0;i<capture_count;i++){Capture c=captures[i];fprintf(log,"%s{\"requested_seconds\":",i?",":"");if(c.requested<0)fprintf(log,"null");else fprintf(log,"%.17g",c.requested);fprintf(log,",\"elapsed_seconds\":%.17g,\"frame\":%lu,\"bmp\":\"%s\",\"shared_frame\":%s}",c.elapsed,c.frame,c.bmp,c.shared?"true":"false");}
        fprintf(log,"],\"controls\":{\"frozen\":%s,\"animations_enabled\":%s,\"camera_motion_enabled\":%s,\"camera_mode\":\"%s\",\"simulation_seconds\":%.17g,\"camera_seconds\":%.17g,\"character_pose\":\"baked static pose\"}}\n",paused||fixed?"true":"false",animations_enabled?"true":"false",camera_motion?"true":"false",orbit_mode?"orbit":"free",scene_time,camera_time);fclose(log);}
    puts("Museum DOS complete. CAPTURE.BMP, FPS.CSV and RESULT.JSN saved.");return 0;
}
