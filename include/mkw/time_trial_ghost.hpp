#pragma once
// Time Trial ghosts: the player's best run on each course, kept as the inputs
// the kart was given every simulation tick from the countdown on. Kinoko is
// deterministic, so a second kart fed the same inputs from the same start runs
// the same race (it never touches anything: KartCollide's intangible mask).
// One file per course: ux0:data/mkw/ghosts/course_NN.mkg.
#include <cstddef>
#include <cstdint>
#include <vector>

namespace mkw {
struct GhostFrame {
    uint8_t buttons=0;  // Kinoko pad buttons (1 accelerate, 2 brake/drift, 8 drift with accelerate)
    int8_t stick=0;     // the Wii lattice, -7..7
    uint8_t trick=0;    // Kinoko::System::Trick
    uint8_t items=0;    // ItemInput: 1 use, 2 backwards, 4 forwards
};
class TimeTrialGhost {
public:
    static constexpr uint32_t Magic=0x4d4b4748; // "MKGH"
    static constexpr uint32_t Version=1;
    // Course, racer (the garage choice: driver * VehiclesPerDriver + vehicle)
    // and result; frames start at the countdown.
    unsigned course=0,choice=0;bool driftAuto=false;
    uint32_t milliseconds=0;
    std::vector<GhostFrame> frames;

    bool valid() const{return milliseconds!=0&&!frames.empty();}
    void clear(){*this=TimeTrialGhost{};}
    bool load(unsigned course);
    bool save() const;
    static bool exists(unsigned course);
    const GhostFrame* frame(std::size_t tick) const{return tick<frames.size()?&frames[tick]:nullptr;}
};
}
