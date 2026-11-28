#include <pybind11/pybind11.h>
#include "env/Env.h"
#include "game/SaveFile.h"
#include <stdexcept>

using namespace sts;

PYBIND11_MODULE(_r7_parasite, module) {
    module.def("enter", [](env::Env &e, const std::string &path) {
        auto save = SaveFile::loadFromPath(path, CharacterClass::SILENT);
        if (e.steps || e.inBattle || save.post_combat || save.seed != e.gc.seed ||
            save.act_num != 2 || save.floor_num != 18 || save.ascension_level != 20 ||
            save.monster_list.empty() || save.monster_list[0] != MonsterEncounter::SHELL_PARASITE)
            throw std::invalid_argument("Expected the archived Silent A20 Act 2 precombat save");
        e.gc = GameContext();
        e.gc.initFromSave(save);
        e.bc = BattleContext();
        e.bc.init(e.gc);
        e.inBattle = true;
    });
}
