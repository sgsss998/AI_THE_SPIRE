#include <stdexcept>
#include <pybind11/pybind11.h>
#include "env/Env.h"
PYBIND11_MODULE(_sa_r5_wheel, mod) {
    mod.def("heal_pending", [](const sts::env::Env& env, int step) {
        const auto& game=env.gc;
        if (env.steps != step || env.done() || env.inBattle ||
            game.screenState != sts::ScreenState::EVENT_SCREEN || game.curEvent != sts::Event::WHEEL_OF_CHANGE)
            throw std::invalid_argument("Wheel observation has a different step or event");
        return game.info.phase==1 && game.info.eventData==2;
    });
}
