#include <pybind11/pybind11.h>
#include "env/Env.h"
using namespace sts;
using namespace sts::env;

PYBIND11_MODULE(_r7_event_cost_control, m) {
    m.def("set", [](Env &e, int hp, bool addFairy, bool scrap) {
        auto &g=e.gc;
        if (e.inBattle || e.done() || g.act!=1 || g.ascension!=20 || g.curEvent!=Event::WING_STATUE ||
            g.curRoom!=Room::EVENT || g.screenState!=ScreenState::EVENT_SCREEN || hp<1 || hp>g.maxHp)
            throw std::invalid_argument("Expected the current Golden Wing decision");
        g.curHp=hp;
        if (addFairy) {
            if(g.potionCount>=g.potionCapacity) throw std::invalid_argument("Potion slots are full");
            g.obtainPotion(Potion::FAIRY_POTION);
        }
        if (scrap) { g.curEvent=Event::SCRAP_OOZE; g.setupEvent(); }
    });
}
