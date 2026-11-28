#include <pybind11/pybind11.h>
#include "env/Env.h"
#include <utility>
using namespace sts;
using namespace sts::env;
PYBIND11_MODULE(_r7_swap_purses, module) {
    module.def("swap_directed", [](Env &env) {
        auto &group=env.bc.monsters;
        if(!env.inBattle || env.gc.act!=2 || group.monsterCount!=2 ||
           group.arr[0].id!=MonsterId::LOOTER || group.arr[1].id!=MonsterId::MUGGER ||
           group.arr[0].curHp<=0 || group.arr[1].curHp<=0 ||
           group.arr[0].miscInfo==group.arr[1].miscInfo)
            throw std::invalid_argument("Expected two live thieves with different purse balances");
        std::swap(group.arr[0].miscInfo,group.arr[1].miscInfo);
    });
}
