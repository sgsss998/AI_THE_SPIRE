#include <algorithm>
#include <stdexcept>
#include <vector>
#include <pybind11/pybind11.h>
#include "constants/CardPools.h"
#include "env/Env.h"

using namespace sts;
using sts::env::Env;
namespace py = pybind11;

struct Receipt {
    std::uint64_t seed, next0, next1;
    int floor;
    std::int64_t steps;
    int nextCounter;
    CardId oldResult, result;
    std::vector<Card> survivors;
    std::array<int,4> counts;
    int upgradeable, transformable;
};

static void check(bool ok, const char *msg) {
    if (!ok) throw std::runtime_error(msg);
}

static Receipt prepare(const Env &env, int option, int position) {
    const auto &g = env.gc;
    const auto &info = g.info;
    check(g.ascension == 20 && g.cc == CharacterClass::SILENT && g.act == 1 &&
          (g.curEvent == Event::LIVING_WALL || g.curEvent == Event::TRANSMORGRIFIER) &&
          g.screenState == ScreenState::CARD_SELECT && info.transformRng == MISC_RNG &&
          info.selectScreenType == CardSelectScreenType::TRANSFORM && info.toSelectCount == 1 &&
          info.haveSelectedCards.empty() && option >= 0 && option < info.toSelectCards.size() &&
          position >= 0 && position < g.deck.size() && info.toSelectCards[option].deckIdx == position,
          "Wrong event, transform screen or card position");
    const Card old = g.deck.cards[position];
    check(old == info.toSelectCards[option].card && !old.upgraded && !old.misc &&
          std::all_of(g.deck.bottleIdxs.begin(),g.deck.bottleIdxs.end(),[](int index){ return index==-1; }) && !g.hasRelic(RelicId::OMAMORI) &&
          !g.hasRelic(RelicId::DARKSTONE_PERIAPT) && !g.hasRelic(RelicId::DU_VU_DOLL) &&
          !g.hasRelic(RelicId::CERAMIC_FISH), "Unreviewed curse or inventory effect");
    std::vector<CardId> pool;
    for (auto id : curseCardPool) if (id != old.id) pool.push_back(id);
    check(pool.size() == curseCardPoolSize-1, "Expected a removable curse from the ten-card pool");
    auto rng = g.miscRng;
    const auto idx = rng.random(static_cast<int>(pool.size())-1);
    const auto legacy = curseCardPool[idx] == old.id ? curseCardPool[idx+1] : curseCardPool[idx];
    std::vector<Card> survivors;
    for (int i=0;i<g.deck.size();++i) if (i!=position) survivors.push_back(g.deck.cards[i]);
    return {g.seed, rng.seed0, rng.seed1, g.floorNum, env.steps, rng.counter,
            legacy, pool[idx], survivors, g.deck.cardTypeCounts, g.deck.upgradeableCount, g.deck.transformableCount};
}

static void apply(Env &env, const Receipt &r) {
    auto &g=env.gc;
    check(g.seed==r.seed && g.floorNum==r.floor && env.steps==r.steps+1 &&
          g.screenState==ScreenState::MAP_SCREEN && g.miscRng.counter==r.nextCounter &&
          g.miscRng.seed0==r.next0 && g.miscRng.seed1==r.next1 &&
          g.deck.size()==static_cast<int>(r.survivors.size())+1 &&
          g.deck.cardTypeCounts==r.counts && g.deck.upgradeableCount==r.upgradeable &&
          g.deck.transformableCount==r.transformable, "Wrong curse receipt, RNG stream or card counters");
    for (std::size_t i=0;i<r.survivors.size();++i) {
        const Card &actual=g.deck.cards[i];
        const Card &before=r.survivors[i];
        check(actual.id==before.id && actual.misc==before.misc && actual.upgraded==before.upgraded,
              "A different permanent occurrence changed");
    }
    Card &last=g.deck.cards.back();
    check(!last.upgraded && !last.misc && (last.id==r.oldResult || last.id==r.result),
          "Unexpected card acquired by the backing rule");
    last.id=r.result; // Both are ordinary removable curses with identical counters and no acquisition effects.
}

PYBIND11_MODULE(_r7_curse_draw,m) {
    py::class_<Receipt>(m,"Receipt");
    m.def("prepare",&prepare);
    m.def("settle",&apply);
}
