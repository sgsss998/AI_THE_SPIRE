"""Replay witnessed Big Fish outcomes against the integrated public interface."""
import argparse
import importlib
from pathlib import Path

from experiments.box_omamori193.policy import SUPPLIED
from experiments.event_result_frontiers193.verify import bracket
from experiments.event_rewards_retail193.live import prefix
from experiments.sa_calibration_round5.reference import write

HERE = Path(__file__).resolve().parent


def audit(module, seed, instance):
    engine = module.make_engine()
    session = module.make_session(engine)
    frame = session.reset(seed, ascension=20, final_act=True)
    for action in prefix(seed):
        assert frame.supported_actions[action]
        frame = session.step(action, frame_id=frame.frame_id, action_version=frame.action_version)
    assert frame.page == "EVENT_RESULT" and frame.supported_actions[110]
    leave = session.step(110, frame_id=frame.frame_id, action_version=frame.action_version)
    assert leave.engine_steps == frame.engine_steps and leave.state.vector[6] == 5
    surfaces = []
    for label, model in [("first_leave",frame),("settled_leave",frame),("map",leave)]:
        packet, retail = bracket(HERE.parents[2]/"native_runtime"/instance, label)
        game = packet["raw"]["game_state"]
        values = model.state.vector
        assert values[:6] == (game["current_hp"], game["max_hp"], game["gold"], game["floor"], game["act"], 20)
        deck = [[engine._source._backend.CARD_IDS[int(values[i])-1],int(values[i+1])]
                for i in range(706,706+int(values[22])*2,2)]
        assert deck == [[c["id"],c["times_upgraded"]] for c in retail["master_deck"]]
        assert deck == [[c["id"],c["upgrades"]] for c in game["deck"]]
        relics = [(r["id"],r["counter"]) for r in game["relics"]]
        assert relics == [(r["id"],r["counter"]) for r in retail["relics"]]
        assert relics[1] == (("Omamori",2) if seed == 6000020 else ("Snake Skull",-1))
        assert (values[34],values[35]-1) == ((47,2) if seed == 6000020 else (64,-1))
        assert deck[-1] == ["Regret",0]
        if label == "map":
            assert list(session.route_columns(frame_id=leave.frame_id)) == [n["x"] for n in game["screen_state"]["next_nodes"]]
        else:
            assert game["choice_list"] == ["leave"] and model.state.vector[1769] == 1
        surfaces.append(dict(phase=label, source=packet["raw_hash"], deck_count=len(deck), relics=relics,
                             hp=int(values[0]), gold=int(values[2]), mask_complete=model.policy_mask is not None))
    return dict(seed=seed, original_steps=len(prefix(seed)), phases=surfaces)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", default="experiments.sa_calibration_round7.combined")
    module = importlib.import_module(parser.parse_args().edition)
    result = {str(seed):audit(module,seed,instance) for seed,instance in SUPPLIED.items()}
    write(HERE/"RESULT.json",result)
    print("Verified Big Fish payout, deck and departure on six paired original snapshots.")
