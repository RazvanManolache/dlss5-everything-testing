bool background=false;
#include "measurement_window.h"
MeasurementWindow measurement;
Json measuredSamples=Json::array();
bool noCapture=false,captureAfterMeasurement=false;
double durationSeconds=0,captureAtSeconds=-1,elapsedSeconds=0,captureElapsedSeconds=-1;
double maximumFrameSeconds=0;
double fpsAverage=0,fpsLatest=0,fpsMinimum=0,fpsMaximum=0;
uint64_t screenshotFrame=0;
std::vector<double> captureTimes;
size_t nextCapture=0;
double captureEverySeconds=0;
Json captureRecords=Json::array();
double parseSeconds(const std::wstring& text){size_t end=0;double value=std::stod(text,&end);ensure(end==text.size()&&std::isfinite(value)&&value>=0,"Capture times must be finite nonnegative numbers");return value;}
void addCaptureTimes(const std::wstring& text){size_t start=0;do{auto end=text.find(L',',start);auto part=text.substr(start,end==std::wstring::npos?end:end-start);ensure(!part.empty(),"Empty --capture-at time");captureTimes.push_back(parseSeconds(part));ensure(captureTimes.size()<=10000,"At most 10000 screenshots per run");if(end==std::wstring::npos)break;start=end+1;}while(true);}
void prepareCaptureSchedule(bool explicitTimes){
 ensure(std::isfinite(captureEverySeconds)&&captureEverySeconds>=0,"Invalid --capture-every interval");
 if(captureEverySeconds>0){ensure(durationSeconds>0,"--capture-every requires a finite --seconds duration");for(uint64_t i=1;double(i)*captureEverySeconds<=durationSeconds+1e-9;i++){ensure(captureTimes.size()<10000,"At most 10000 screenshots per run");captureTimes.push_back(std::min(durationSeconds,double(i)*captureEverySeconds));}ensure(!captureTimes.empty(),"Capture interval exceeds run time; choose an earlier --capture-at time or a shorter interval");}
 if(!explicitTimes&&captureEverySeconds==0&&durationSeconds>0)captureTimes.push_back(durationSeconds*.5);
 std::sort(captureTimes.begin(),captureTimes.end());captureTimes.erase(std::unique(captureTimes.begin(),captureTimes.end(),[](double a,double b){return std::abs(a-b)<1e-9;}),captureTimes.end());
 for(double t:captureTimes)ensure(durationSeconds==0||t<=durationSeconds,"Screenshot times must not exceed --seconds");
 captureAtSeconds=captureTimes.empty()?-1:captureTimes.front();
}
Clock::time_point benchmarkStart;
uint64_t benchmarkStartTick=0;
Json fpsSamples=Json::array();
std::ofstream fpsCsv;
double sampleStartSeconds=0;
uint64_t sampleStartFrame=0;
double benchmarkElapsed(){return std::chrono::duration<double>(Clock::now()-benchmarkStart).count();}
bool captureDueNow(){return !noCapture&&(!captureAfterMeasurement||measurement.complete())&&nextCapture<captureTimes.size()&&benchmarkElapsed()>=captureTimes[nextCapture];}
Json measuredInfo(){return {{"enabled",measurement.enabled()},{"complete",measurement.complete()},{"warmup_seconds",measurement.warmup},{"requested_seconds",measurement.requested},{"start_render_seconds",measurement.start},{"end_render_seconds",measurement.end},{"elapsed_seconds",measurement.elapsed},{"frames_rendered",measurement.frames},{"average_fps",measurement.fps()},{"minimum_sample_fps",measurement.minimum_fps},{"maximum_sample_fps",measurement.maximum_fps},{"maximum_frame_seconds",measurement.maximum_frame},{"samples",measuredSamples},{"vsync_requested",false}};}
void sampleMeasurement(bool final=false){
 double interval=measurement.elapsed-measurement.sample_start;
 if(interval<1.0&&(!final||interval<.01))return;
 uint64_t count=measurement.frames-measurement.sample_frames;if(!count)return;
 double fps=count/interval;
 if(measuredSamples.empty())measurement.minimum_fps=measurement.maximum_fps=fps;
 else{measurement.minimum_fps=std::min(measurement.minimum_fps,fps);measurement.maximum_fps=std::max(measurement.maximum_fps,fps);}
 measuredSamples.push_back({{"elapsed_seconds",measurement.elapsed},{"frames",count},{"interval_seconds",interval},{"fps",fps},{"average_fps",measurement.fps()}});
 measurement.sample_start=measurement.elapsed;measurement.sample_frames=measurement.frames;
}
void sampleFps(bool final=false){
 double interval=elapsedSeconds-sampleStartSeconds;
 if(interval<1.0&&(!final||interval<.01))return;
 uint64_t count=frameNumber-sampleStartFrame;if(!count)return;
 fpsLatest=count/interval;fpsAverage=elapsedSeconds>0?frameNumber/elapsedSeconds:0;
 if(fpsSamples.empty())fpsMinimum=fpsMaximum=fpsLatest;
 else{fpsMinimum=std::min(fpsMinimum,fpsLatest);fpsMaximum=std::max(fpsMaximum,fpsLatest);}
 fpsSamples.push_back({{"maximum_frame_seconds",maximumFrameSeconds},{"elapsed_seconds",elapsedSeconds},{"frames",count},{"interval_seconds",interval},{"fps",fpsLatest},{"average_fps",fpsAverage}});
 fpsCsv<<elapsedSeconds<<','<<frameNumber<<','<<count<<','<<interval<<','<<fpsLatest<<','<<fpsAverage<<'\n';fpsCsv.flush();
 sampleStartSeconds=elapsedSeconds;sampleStartFrame=frameNumber;
}
Json benchmarkInfo(){return {{"capture_times",captureTimes},{"captures",captureRecords},{"pending_captures",captureTimes.size()-nextCapture},{"maximum_frame_seconds",maximumFrameSeconds},{"elapsed_seconds",elapsedSeconds},{"requested_seconds",durationSeconds},{"frames_rendered",frameNumber},{"average_fps",fpsAverage},{"latest_fps",fpsLatest},{"minimum_sample_fps",fpsMinimum},{"maximum_sample_fps",fpsMaximum},{"sample_count",fpsSamples.size()},{"capture_at_seconds",captureAtSeconds},{"capture_elapsed_seconds",captureElapsedSeconds},{"capture_frame",screenshotFrame},{"background",background},{"measurement",measuredInfo()},{"render_start_tick_ms",benchmarkStartTick},{"window_visible",windowHandle?IsWindowVisible(windowHandle)!=FALSE:false},{"rendering_note",background?"Hidden-window render-loop FPS; presentation is occluded and is not equivalent to visible-game FPS.":"Render-loop FPS including presentation and screenshot overhead."}};}
