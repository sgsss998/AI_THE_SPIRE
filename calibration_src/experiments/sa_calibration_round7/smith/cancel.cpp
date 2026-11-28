#include <pybind11/pybind11.h>
#include "env/Env.h"

using sts::CardSelectScreenType;
using sts::Room;
using sts::ScreenState;
using sts::env::Env;

PYBIND11_MODULE(_r7_cancel_smith,module) {
    module.def("return_to_fire",[](Env &live, const Env &before) {
        auto &game=live.gc;
        const auto &old=before.gc;
        if (live.inBattle || before.inBattle || game.seed!=old.seed || game.floorNum!=old.floorNum
            || game.act!=old.act || game.curRoom!=Room::REST || old.curRoom!=Room::REST
            || live.steps!=before.steps+1 || live.done() || before.done()
            || game.screenState!=ScreenState::CARD_SELECT || old.screenState!=ScreenState::REST_ROOM
            || game.info.selectScreenType!=CardSelectScreenType::UPGRADE || game.info.toSelectCount!=1
            || !game.info.haveSelectedCards.empty() || game.curHp!=old.curHp || game.gold!=old.gold
            || game.deck.size()!=old.deck.size())
            throw std::invalid_argument("The smith decision is no longer pending");
        // Restore only the four picker fields touched by openCardSelectScreen(UPGRADE,1).
        game.info.selectScreenType=old.info.selectScreenType;
        game.info.toSelectCount=old.info.toSelectCount;
        game.info.haveSelectedCards=old.info.haveSelectedCards;
        game.info.toSelectCards=old.info.toSelectCards;
        game.screenState=ScreenState::REST_ROOM;
    });
}
