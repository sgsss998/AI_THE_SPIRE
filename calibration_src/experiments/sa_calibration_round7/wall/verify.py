"""Offline comparison with the sealed R6 retail run and the fixed R6 regression seed."""
from dataclasses import asdict, replace
from pathlib import Path

from experiments.episode_outcomes193.rollout import run_episode
from experiments.sa_calibration_round4.fresh import invocations
from experiments.sa_calibration_round5.regression import Observation
from experiments.sa_calibration_round5.replay import unique_ack
from experiments.sa_calibration_round6 import replay as r6
from experiments.sa_calibration_round6.fresh import replay as archive
from experiments.sa_calibration_round6.reference import read, write, sha
from .. import release

HERE = Path(__file__).resolve().parent
R6 = release.R6
SEED = 6846117179527628677
FIXED = 9000033


def loaded():
    folder = R6/"fresh"
    journal = archive.view.rows(folder/"ACTIONS.jsonl")
    end = read(folder/"TERMINAL.json")
    assert end["trace_sha256"] == sha(folder/"ACTIONS.jsonl")
    assert read(folder/"SEED.json")["unsigned"] == SEED
    calls, hashes = archive.capture(journal, end)
    return journal, calls, hashes


def step(session, frame, action):
    return session.step(action, frame_id=frame.frame_id, action_version=frame.action_version)


def compare(engine, frame, snap):
    # R6's independent comparator checks the inherited layout against the pinned R6 version.
    assert frame.state.state_version.endswith(release.TAG)
    projected = replace(frame, state=replace(frame.state, state_version=frame.state.state_version.removesuffix(release.TAG)))
    return r6.compare(projected, engine, snap)["differences"]


def legal(frame):
    return [i for i, enabled in enumerate(frame.supported_actions) if enabled]


def retail_replay(journal, calls):
    engine = release.make_engine()
    session = release.make_session(engine)
    frame = session.reset(SEED)
    frames, rows, first_diff, stop = {}, [], None, None
    for pos, row in enumerate(journal):
        i = row["index"]
        before = compare(engine, frame, row["before"])
        aid, binding = archive.view.map_action(row, frame, engine)
        entry = dict(index=i, command=row["command"], floor=int(frame.state.vector[3]), page=frame.page,
                     offered=legal(frame), retail_legal=row["legal"], public_action=aid, before=before,
                     original_before_hash=row["before"]["raw_hash"], original_after_hash=row["after"]["raw_hash"])
        rows.append(entry)
        if before and not first_diff and set(before)-{"page"}:
            first_diff = dict(index=i, phase="before", fields=before)
        if aid is None:
            later = compare(engine, frame, row["after"])
            ack = unique_ack(row) and not later
            if (not ack and unique_ack(row) and set(later)=={"page"} and pos+1 < len(journal)):
                following = journal[pos+1]
                ack = (unique_ack(following) and row["after"]["raw_hash"]==following["before"]["raw_hash"]
                       and not compare(engine, frame, following["after"]))
            if not ack:
                stop = dict(index=i, reason="unmapped_retail_input", binding=binding)
            else:
                entry["status"] = "presentation_ack"
        elif aid not in legal(frame):
            stop = dict(index=i, reason="action_missing", action=aid, binding=binding)
        else:
            frame = step(session, frame, aid)
            entry["status"] = "executed"
            for seq, raw_invocation in invocations.received(row, calls):
                extra, detail = invocations.binding(row, raw_invocation, frame, engine)
                if extra not in legal(frame):
                    stop = dict(index=i, reason="additional_action_missing", action=extra, binding=detail)
                    break
                frame = step(session, frame, extra)
                entry.setdefault("incidental_actions", []).append((seq,extra))
        if stop:
            stop.update(floor=entry["floor"], page=frame.page, offered=legal(frame), gaps=list(frame.action_gaps))
            entry["status"] = "stopped"
            break
        after = compare(engine, frame, row["after"])
        entry["after"] = after
        if after and not first_diff and set(after)-{"page"}:
            first_diff = dict(index=i, phase="after", fields=after)
        if 30 <= i <= 34:
            frames[i] = frame
    return dict(rows=rows, completed_inputs=sum(q["status"]!="stopped" for q in rows),
                total_original_inputs=len(journal), first_substantive_difference=first_diff, stop=stop), frames


def bound_cards(journal, frames):
    snapshots = [journal[index-1]["after"] for index in (31,32,33)]
    raw = [s["raw"]["game_state"] for s in snapshots]
    native = [archive.view.NATIVE[s["session"],s["sequence"]] for s in snapshots]
    deck = [c["uuid"] for c in raw[0]["deck"]]
    assert len(deck) == len(set(deck)) and deck == [c["uuid"] for c in native[0]["master_deck"]]
    grid = [c["uuid"] for c in raw[0]["screen_state"]["cards"]]
    assert grid == [c["uuid"] for c in native[0]["selection"]["target_group"]]
    positions = [deck.index(uuid) for uuid in grid]
    v = frames[31].state.vector
    assert [int(v[2684+i])-203 for i in range(len(grid))] == positions
    assert len(grid) == int(v[1769])
    assert frames[31].state.vector[22] == frames[32].state.vector[22] == len(deck)
    chosen = journal[31]["aid"] - 110
    preview = frames[32].state.vector
    assert [i for i in range(len(grid)) if preview[325+6*i]] == [chosen]
    assert preview[28] == 1 and raw[1]["screen_state"]["confirm_up"]
    assert [c["uuid"] for c in native[1]["master_deck"]] == deck
    survivors = [uuid for uuid in deck if uuid != grid[chosen]]
    assert [c["uuid"] for c in native[2]["master_deck"]] == survivors == [c["uuid"] for c in raw[2]["deck"]]
    assert frames[33].state.vector[22] == len(survivors)
    for index in (31,32,33,34):
        assert legal(frames[index-1]) == journal[index-1]["legal"]
    return dict(positions_zero_based=positions,grid_uuids=grid,
                chosen_slot_zero_based=chosen,chosen_uuid=grid[chosen],remaining_deck_uuids=survivors,
                ordinary_strike_candidates=sum(c["id"] == "Strike_G" for c in raw[0]["screen_state"]["cards"]),
                selected_uuid_evidence="retail choose slot, no preview deck change, only that UUID disappears on confirmation",
                matching_full_action_sets_at_inputs=[31,32,33,34],
                deck_counts=[len(r["deck"]) for r in raw])


class FixedObservation(Observation):
    def __init__(self, engine):
        self.session = release.make_session(engine)


def fixed_replay():
    old = next(row for row in read(R6/"regression/RESULT.json")["records"] if row["seed"]==FIXED)
    new = asdict(run_episode(FIXED, cap=old["cap"], engine_factory=release.make_engine, wrap=FixedObservation))
    assert new["actions"][:len(old["actions"])] == old["actions"] and len(new["actions"]) > len(old["actions"])
    return dict(previous_inputs=len(old["actions"]),previous_floor=old["engine_floor"],old_page=old["page"],
                candidate=new, matched_prefix=len(old["actions"]),retail_floor5_matched=False)


def main():
    journal, calls, hashes = loaded()
    replay, frames = retail_replay(journal, calls)
    bound = bound_cards(journal, frames)
    fixed = fixed_replay()
    write(HERE/"RESULT.json", dict(retail_seed=SEED,retail_display="20WSEQKXI76GH",runtime=release.source_hashes(),
                retail_journal=sha(R6/"fresh/ACTIONS.jsonl"), verified_native_files=hashes,
                fixed=fixed,retail=replay,wall=bound))
    print("retail",replay["completed_inputs"],replay["first_substantive_difference"],replay["stop"])
    new = fixed["candidate"]
    print("fixed",len(new["actions"]),new["reason"],new["engine_floor"],new["page"])


if __name__ == "__main__":
    main()
