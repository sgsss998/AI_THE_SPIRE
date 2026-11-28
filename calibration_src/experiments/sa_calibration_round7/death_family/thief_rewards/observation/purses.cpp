#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "env/Env.h"

using namespace sts;
using namespace sts::env;

PYBIND11_MODULE(_r7_thief_purses, module) {
    module.def("values", [](const Env &env, int step,const std::array<int,5> &ids) {
        if (env.steps != step) throw std::invalid_argument("Stale purse observation");
        std::array<int,5> amounts{};
        if (!env.inBattle) return amounts;
        const auto &group=env.bc.monsters;
        if (group.monsterCount<0 || group.monsterCount>int(amounts.size()))
            throw std::invalid_argument("Unexpected monster count");
        for(int i=0;i<group.monsterCount;++i) {
            const auto &m=group.arr[i];
            if(ids[i]!=int(m.id)+1) throw std::invalid_argument("Kernel and visible targets differ");
            if(m.id!=MonsterId::LOOTER && m.id!=MonsterId::MUGGER) continue;
            if(m.miscInfo<0) throw std::invalid_argument("Invalid stolen gold");
            amounts[i]=m.miscInfo;
        }
        return amounts;
    });
}
