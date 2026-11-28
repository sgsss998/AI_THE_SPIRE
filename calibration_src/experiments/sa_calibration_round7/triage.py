"""Find repeated failure signatures across runs, retaining a reproducible shortest prefix."""
import argparse
from collections import Counter, defaultdict
import gzip
import json

from .campaign import RUNS, TERMINAL, encode, read, sha, write


def rows(folder):
    result = read(folder/"RESULT.json")
    jobs = read(folder/"manifest.json")["jobs"]
    assert sha(folder/"manifest.json") == result["manifest_sha256"]
    index = 0
    for name, digest in sorted(result["shards"].items()):
        shard = folder/name
        assert sha(shard) == digest
        with gzip.open(shard, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                job = jobs[index]
                assert (row["seed"], row["strategy"]) == (job["seed"], job["strategy"])
                yield name, row
                index += 1
    assert index == len(jobs) == result["requested"] == result["completed"]


def signatures(row):
    if row["reason"] not in TERMINAL:
        stop = row["stop"] or {}
        frame = stop.get("after") or stop.get("before") or {}
        page = row["page"]
        # The unsupported page may hide the source event. The last decision retains it.
        previous = stop.get("before") or {}
        context = frame.get("event") or previous.get("event") or ""
        yield ("stop", page, context, tuple(sorted(row["cause"]))), stop.get("step")
    for gap in row["action_gap_counts"]:
        partial = row.get("first_partial") or {}
        after = partial.get("after") or {}
        step = partial.get("step") if gap in after.get("gaps", ()) else None
        yield ("incomplete_or_error", gap), step
    for key in row["semantic_counts"]:
        finding = row["first_semantic"]
        known = any(f["kind"] == key for f in finding["findings"])
        yield ("wrong_result", key), finding["step"] if known else None
    repeat = row["determinism"]
    if not (repeat["checked"] and repeat["matched"]):
        yield ("repeat_diverged",), repeat.get("first_different_frame")


def run(name):
    folder = RUNS/name
    counts, examples, scenes = Counter(), defaultdict(list), Counter()
    flags, by_policy, stages = Counter(), defaultdict(Counter), Counter()
    steps, paired = 0, 0
    for shard, row in rows(folder):
        terminal = row["reason"] in TERMINAL
        flagged = bool(row["action_gap_counts"] or row["semantic_counts"] or not row["determinism"]["matched"])
        steps += len(row["actions"])
        paired += int(row["determinism"]["checked"] and row["determinism"]["matched"])
        flags["natural" if terminal else "unfinished"] += 1
        flags["natural_with_issue" if terminal and flagged else "natural_clean" if terminal else "unfinished_with_issue"] += 1
        by_policy[row["strategy"]][row["reason"]] += 1
        scenes.update(row["scene_counts"].keys())
        acts = {k.split("/")[0] for k in row["scene_counts"]}
        stages.update(acts & {"act1", "act2", "act3", "act4"})
        for key, step in signatures(row):
            counts[key] += 1
            evidence = dict(seed=row["seed"], strategy=row["strategy"], shard=shard, first_step=step,
                            replay_length=len(row["actions"]) if step is None else step, floor=row["engine_floor"])
            pool = examples[key]
            pool.append(evidence)
            # Known prefixes take precedence over full runs with unlocalized findings.
            pool.sort(key=lambda e:(e["first_step"] is None, e["replay_length"], e["seed"]))
            del pool[2:]
    groups = [dict(signature=key, affected_games=n, examples=examples[key]) for key,n in counts.most_common()]
    result = dict(episodes=flags["natural"] + flags["unfinished"], counts=dict(flags), decisions=steps,
                  deterministic_matches=paired, by_policy=dict(by_policy), reached_by_act=dict(stages),
                  episodes_by_scene=dict(sorted(scenes.items())), groups=groups,
                  note="Repeated signatures are leads. Establish the root cause using a replay before merging or fixing groups.")
    assert result["episodes"] == read(folder/"RESULT.json")["requested"]
    write(folder/"TRIAGE.json", result)
    print(encode({k:result[k] for k in ("episodes","counts","decisions","deterministic_matches","reached_by_act")}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    run(parser.parse_args().name)
