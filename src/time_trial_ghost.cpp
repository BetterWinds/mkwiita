#include <mkw/time_trial_ghost.hpp>
#include <cstdio>
#include <sys/stat.h>

namespace mkw {
namespace {
// The longest kept run: 30 minutes of ticks.
constexpr uint32_t MaxFrames=60u*60u*30u;
void ghostPath(unsigned course,char* out,std::size_t size){std::snprintf(out,size,"ux0:data/mkw/ghosts/course_%02u.mkg",course);}
struct Header {uint32_t magic,version,course,choice,driftAuto,milliseconds,frames;};
}

bool TimeTrialGhost::exists(unsigned course){
    TimeTrialGhost ghost;return ghost.load(course);
}

bool TimeTrialGhost::load(unsigned which){
    clear();
    char path[64];ghostPath(which,path,sizeof path);
    FILE* f=std::fopen(path,"rb");if(!f)return false;
    Header h{};bool ok=std::fread(&h,sizeof h,1,f)==1&&h.magic==Magic&&h.version==Version&&h.course==which&&h.frames>0&&h.frames<=MaxFrames&&h.milliseconds;
    if(ok){frames.resize(h.frames);ok=std::fread(frames.data(),sizeof(GhostFrame),frames.size(),f)==frames.size();}
    std::fclose(f);
    if(!ok){clear();return false;}
    course=which;choice=h.choice;driftAuto=h.driftAuto!=0;milliseconds=h.milliseconds;
    return true;
}

bool TimeTrialGhost::save() const{
    if(!valid()||frames.size()>MaxFrames)return false;
    mkdir("ux0:data",0777);mkdir("ux0:data/mkw",0777);mkdir("ux0:data/mkw/ghosts",0777);
    char path[64],temporary[72];ghostPath(course,path,sizeof path);std::snprintf(temporary,sizeof temporary,"%s.tmp",path);
    // A temporary file first, so a pulled card keeps the previous ghost.
    FILE* f=std::fopen(temporary,"wb");if(!f)return false;
    const Header h{Magic,Version,course,choice,driftAuto?1u:0u,milliseconds,uint32_t(frames.size())};
    const bool ok=std::fwrite(&h,sizeof h,1,f)==1&&std::fwrite(frames.data(),sizeof(GhostFrame),frames.size(),f)==frames.size();
    if(std::fclose(f)!=0||!ok){std::remove(temporary);return false;}
    std::remove(path);return std::rename(temporary,path)==0;
}
}
