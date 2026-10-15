#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <algorithm>
namespace mkw {
// Original ItemSlot.bin: count, then [rank count, item count, item-major bytes].
// Copy the selected 12-racer tables so no race-heap/archive pointer escapes reset.
class ItemOdds {
public:
    bool load(const void* bytes,std::size_t size,unsigned localTable,unsigned cpuTable){
        tables_={};rows_={12,12};ready_=false;
        if(!bytes||size<1)return false;
        const auto* data=static_cast<const uint8_t*>(bytes);std::size_t offset=1;unsigned found=0;
        for(unsigned table=0;table<data[0];++table){
            if(size-offset<2)return false;
            const unsigned ranks=data[offset++],items=data[offset++];
            if(!ranks||!items||std::size_t(ranks)*items>size-offset)return false;
            for(unsigned role=0;role<2;++role)if(table==(role?cpuTable:localTable)){
                // Race tables have 12 positions; battle tables 3 columns
                // (the racer's team winning, tied, losing).
                if((ranks!=12&&ranks!=3)||items!=19)return false;
                rows_[role]=ranks;
                for(unsigned item=0;item<19;++item)for(unsigned rank=0;rank<ranks;++rank)
                    tables_[role][rank][item]=data[offset+item*ranks+rank];
                ++found;
            }
            offset+=std::size_t(ranks)*items;
        }
        ready_=found==2&&offset==size;return ready_;
    }
    bool ready() const{return ready_;}
    const std::array<uint16_t,19>& weights(bool cpu,unsigned rank)const{return tables_[cpu?1:0][std::clamp(rank,1u,rows_[cpu?1:0])-1];}
    // VS/Battle item rules (Pages::VSSettings Items; race settings +0xb80):
    // 1 Aggressive, 2 Strategic reshape every weight by its item's category
    // as Item::SlotData::ProcessTable (USA 0x807ABF78) does: (w + add) * mult,
    // truncated. 0 Balanced keeps the tables; None is handled by the caller.
    void applyMode(unsigned mode){
        if(mode!=1&&mode!=2)return;
        // Per-item category (ItemBehaviour +0xc, USA 0x809BEE98 filled from each
        // item's record): 0 single Green Shell, Banana, Mushroom; 2 Blue Shell,
        // Lightning, Star, Golden, Mega, Bullet and the triple Red Shells and
        // Bananas; 1 the rest.
        constexpr uint8_t Category[19]={0,1,0,1,0,1,1,2,2,2,2,2,1,1,1,2,1,2,2};
        // USA 0x808A15D0 (mode 1) and 0x808A15E4 (mode 2).
        constexpr float Mult[2][3]={{.25f,1.f,4.f},{8.f,.25f,0.f}};
        constexpr uint16_t Add[2][3]={{3,0,0},{0,3,0}};
        for(auto& table:tables_)for(auto& row:table)for(unsigned i=0;i<19;++i)
            row[i]=uint16_t(float(row[i]+Add[mode-1][Category[i]])*Mult[mode-1][Category[i]]);
    }
private:
    std::array<std::array<std::array<uint16_t,19>,12>,2> tables_{};
    std::array<unsigned,2> rows_{12,12};
    bool ready_=false;
};
}
