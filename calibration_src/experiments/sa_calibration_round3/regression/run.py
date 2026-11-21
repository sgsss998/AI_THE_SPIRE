"""Independent R3 regression against frozen R2 tea-state 704-seed trajectories; never writes R1 outputs."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime
import gzip
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
import traceback

from experiments.sa_calibration_round1.regression import run as base

HERE = Path(__file__).resolve().parent


def snap(frame, engine, session, enhancer=None):
    exposed = base.resolve(enhancer)(frame, engine, session) if enhancer else frame
    if enhancer:
        assert len(exposed.state.vector) == 3121
        assert exposed.state.vector[:3118] == frame.state.vector
        for field in ("frame_id", "action_version", "supported_actions", "policy_mask", "action_gaps", "page", "done", "engine_steps"):
            assert getattr(exposed, field) == getattr(frame, field), field
        extra = list(exposed.state.vector[3118:])
        assert extra[2] in (0, 1, 2)
    values = list(exposed.state.vector)
    assert len(values)==3122 and len(exposed.supported_actions)==193
    assert values[3120] in (0,1,2) and values[3121] in (0,1)
    assert not (values[3121] and (exposed.done or values[7]))
    core = engine._source._env
    return dict(page=exposed.page, done=exposed.done, engine_steps=exposed.engine_steps,
                state=values, state_sha256=sha256(base.encoded(values)).hexdigest(),
                state_version=exposed.state.state_version, base_state_version=frame.state.state_version,
                action_version=exposed.action_version,
                supported=[i for i, bit in enumerate(exposed.supported_actions) if bit],
                legal=None if exposed.policy_mask is None else [i for i, bit in enumerate(exposed.policy_mask) if bit],
                gaps=list(exposed.action_gaps), kernel_floor=core.floor,
                kernel_won=core.won, kernel_lost=core.lost)


def first_semantic(reference, current):
    """Versions are separately pinned; compare behavior on the shared original 3118 fields."""
    for index, (old, new) in enumerate(zip(reference, current)):
        indices = [i for i, (a, b) in enumerate(zip(old["state"], new["state"])) if a != b]
        fields = {k:dict(previous=old[k], current=new[k]) for k in
                  ("page", "done", "engine_steps", "supported", "legal", "gaps") if old[k] != new[k]}
        if indices or fields:
            return dict(observation=index, state_differences=[dict(index=i, previous=old['state'][i], current=new['state'][i]) for i in indices],
                        fields=fields)
    return None


def trace_write(path, frames):
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=1, mtime=0) as zipped:
            zipped.write(base.encoded(frames))
    return dict(path=str(path), sha256=base.digest(path), observations=len(frames))


def endpoint_from_snapshot(frame):
    return ("loss" if frame["kernel_lost"] else "win" if frame["kernel_won"] else
            "unsupported" if not frame["supported"] else "prefix_end")


def forced_replay(job, resampled, frames, reference):
    old = job["prior"]["actions"]
    if len(resampled["actions"]) >= len(old) and resampled["actions"][:len(old)] == old:
        chosen = frames[:len(old)+1]
        mode = "reused_identical_resampled_prefix"
        available, failure = True, None
    else:
        engine = base.resolve(job["engine_factory"])()
        session = base.resolve(job["session_factory"])(engine)
        frame = session.reset(job["prior"]["seed"], ascension=20, final_act=True)
        chosen = [snap(frame, engine, session, job["enhance_factory"])]
        available, failure = True, None
        for index, action in enumerate(old):
            if frame.done or not frame.supported_actions[action]:
                available = False
                failure = dict(decision=index+1, action=action, page=frame.page,
                               done=frame.done, supported=chosen[-1]["supported"], gaps=list(frame.action_gaps))
                break
            frame = session.step(action, frame_id=frame.frame_id, action_version=frame.action_version)
            chosen.append(snap(frame, engine, session, job["enhance_factory"]))
        mode = "forced_archived_actions"
    last = chosen[-1]
    endpoint = dict(reason=endpoint_from_snapshot(last), page=last["page"], engine_floor=last["kernel_floor"],
                    engine_steps=last["engine_steps"], cause=last["gaps"])
    changes = {k:dict(previous=job["prior"].get(k), current=v) for k,v in endpoint.items() if job["prior"].get(k) != v}
    result = dict(mode=mode, archived_action_count=len(old), actions_replayed=len(chosen)-1,
                  prefix_complete=available and len(chosen)==len(old)+1, first_unavailable=failure,
                  endpoint=endpoint, endpoint_changes=changes,
                  first_semantic_difference=first_semantic(reference, chosen) if reference else None)
    if mode == "forced_archived_actions":
        result["trace"] = trace_write(Path(job["output"]) / "forced_traces" / f"{job['prior']['seed']}.json.gz", chosen)
    return result


def play(job):
    from experiments.episode_outcomes193.rollout import run_episode
    frames = []
    started = perf_counter()
    result = dict(seed=job["prior"]["seed"], cohort=job["cohort"], batch=job["batch"], cap=job["cap"])

    class Observed:
        def __init__(self, engine):
            self.engine = engine
            self.inner = base.resolve(job["session_factory"])(engine)

        def capture(self, frame):
            # The fixed selector depends only on action support. The enhanced frame is
            # read and checked on that exact live decision; the existing evaluator
            # retains its original S3118 validation rather than being monkey-patched.
            frames.append(snap(frame, self.engine, self.inner, job["enhance_factory"]))
            if len(frame.state.vector)>=3121:
                # Only the local selector projection is S3118; the actual session and captured trace remain S3121.
                # Existing released evaluator checks and original packages are unchanged.
                return replace(frame,state=replace(frame.state,vector=frame.state.vector[:3118]))
            return frame

        def reset(self, *args, **kwargs):
            return self.capture(self.inner.reset(*args, **kwargs))

        def step(self, *args, **kwargs):
            return self.capture(self.inner.step(*args, **kwargs))

    try:
        ep = run_episode(result["seed"], cap=job["cap"], engine_factory=base.resolve(job["engine_factory"]), wrap=Observed)
        current = json.loads(json.dumps(asdict(ep)))
        reference_path = Path(job["reference_run"]) / "full/traces" / f"{result['seed']}.json.gz"
        assert base.digest(reference_path) == job['reference_trace_sha256'], 'Final R2 trace differs from its frozen receipt'
        reference = base.read_trace(reference_path)
        for row in reference:
            assert len(row["state"])==3121
            row["state"]=row["state"]+[0]  # R2 tea REGRESSION proves zero on all 60156 archived frames.
        result['reference_trace_sha256'] = job['reference_trace_sha256']
        result["episode"] = current
        result["resampled_differences"] = base.compare(job["prior"], current, frames)
        result["resampled_first_semantic_difference"] = first_semantic(reference, frames) if reference else None
        result["forced"] = forced_replay(job, current, frames, reference)
        if frames and len(frames[0]['state'])>=3121:
            availability = Counter(int(f["state"][3120]) for f in frames)
            result["enhancement"] = dict(observations=len(frames), original_3118_equal=None, actions_equal=None,
                availability={str(k):v for k,v in sorted(availability.items())},
                known_top_card_ids=sorted({int(f["state"][3118]) for f in frames if f["state"][3120]==2}),
                upgraded_top_observations=sum(f["state"][3120]==2 and bool(f["state"][3119]) for f in frames),tea_charged_observations=sum(bool(f['state'][3121]) for f in frames))
    except Exception as error:
        result["error"] = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc(),
                               observation=len(frames)-1, last_frame=base.brief(frames[-1]) if frames else None)
    result["trace"] = trace_write(Path(job["output"]) / "traces" / f"{result['seed']}.json.gz", frames)
    result["seconds"] = perf_counter()-started
    return result


def summary(rows):
    valid = [r for r in rows if "episode" in r]
    result = dict(seeds=len(rows), errors=sum("error" in r for r in rows),
                  outcomes=dict(Counter(r['episode']['reason'] for r in valid)),
                  decisions=sum(len(r['episode']['actions']) for r in valid),
                  resampled_changed_seeds=sum(bool(r['resampled_differences']) for r in valid),
                  changed_policy_observations=sum(bool(r['resampled_first_semantic_difference']) for r in valid),
                  forced_prefix_complete=sum(r.get('forced',{}).get('prefix_complete',False) for r in valid),
                  forced_endpoint_changed=sum(bool(r.get('forced',{}).get('endpoint_changes')) for r in valid),
                  forced_rerun_seeds=sum(r.get('forced',{}).get('mode')=='forced_archived_actions' for r in valid),
                  stopped_pages=dict(Counter(r['episode']['page'] for r in valid if r['episode']['reason']=='unsupported')),
                  partial_mask_decisions=sum(r['episode']['incomplete_action_sets'] for r in valid))
    enhanced = [r['enhancement'] for r in valid if 'enhancement' in r]
    if enhanced:
        counts=Counter()
        for e in enhanced: counts.update(e['availability'])
        result['enhancement']=dict(observations=sum(e['observations'] for e in enhanced), availability=dict(counts),
                                  original_3118_equal=None if any(e['original_3118_equal'] is None for e in enhanced) else all(e['original_3118_equal'] for e in enhanced),
                                  actions_equal=None if any(e['actions_equal'] is None for e in enhanced) else all(e['actions_equal'] for e in enhanced),
                                  upgraded_top_observations=sum(e['upgraded_top_observations'] for e in enhanced),tea_charged_observations=sum(e['tea_charged_observations'] for e in enhanced))
    return result


def phase(jobs, out, options):
    out.mkdir()
    (out/'traces').mkdir()
    (out/'forced_traces').mkdir()
    started=perf_counter()
    with ProcessPoolExecutor(max_workers=options['workers']) as pool:
        rows=list(pool.map(play,[dict(j,output=str(out),**options) for j in jobs],chunksize=2))
    result=dict(seconds=perf_counter()-started, fixed=summary([r for r in rows if r['cohort']=='fixed']),
                additional=summary([r for r in rows if r['cohort']=='additional']),runs=rows)
    base.write_new(out/'RESULT.json',result)
    print(json.dumps(dict(phase=out.name,**{k:v for k,v in result.items() if k!='runs'}),ensure_ascii=False),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--engine-factory',default='experiments.sa_calibration_round3.release:make_engine')
    parser.add_argument('--session-factory',default='experiments.sa_calibration_round3.release:make_session')
    parser.add_argument('--signature-factory',default='experiments.sa_calibration_round3.release:interface_signature')
    parser.add_argument('--reference-run',type=Path,default=base.ROOT/'experiments/sa_calibration_round2/regression/runs/20261120_201657_722221_R2_privileged_final')
    parser.add_argument('--smoke-only',action='store_true')
    parser.add_argument('--focused-only',action='store_true')
    parser.add_argument('--enhance-factory')
    parser.add_argument('--enhance-signature-factory')
    parser.add_argument('--label',default='R3')
    args=parser.parse_args()
    assert 1<=args.workers<=8 and args.label.replace('_','').isalnum()
    assert bool(args.enhance_factory)==bool(args.enhance_signature_factory)
    jobs,hashes,archived=base.cohorts()
    tea_path=base.ROOT/'experiments/sa_calibration_round2/tea_state/REGRESSION.json'
    tea=json.loads(tea_path.read_bytes());assert tea['seeds']==704 and tea['observations']==60156 and tea['charged']==0
    focused=json.loads((HERE/'FOCUSED_53.json').read_bytes())
    focus_seeds={r['seed'] for r in focused['cases']};assert len(focus_seeds)==53
    prior_path=args.reference_run/'full/RESULT.json'
    prior=json.loads(prior_path.read_bytes())
    by_seed={r['seed']:r for r in prior['runs']}
    assert len(by_seed)==704 and not prior['fixed']['errors'] and not prior['additional']['errors']
    for job in jobs:
        reference=by_seed[job['prior']['seed']]
        assert job['cap']==reference['cap'] and job['cohort']==reference['cohort']
        job['prior']=reference['episode']
        job['reference_trace_sha256']=reference['trace']['sha256']
    interface=base.signature(args.signature_factory)
    if args.signature_factory.startswith("experiments.sa_calibration_round3.release:"):
        assert interface==json.loads((HERE.parent/"INTERFACE.json").read_bytes()), "Frozen R3 interface mismatch"
    assert interface["observation_dimension"]==3122 and interface["actions"]==193
    enhanced_interface=base.signature(args.enhance_signature_factory) if args.enhance_factory else None
    output=HERE/'runs'/f'{datetime.now(base.SHANGHAI):%Y%m%d_%H%M%S_%f}_{args.label}'
    output.mkdir(parents=True)
    with (output/'RUNNER_SNAPSHOT.py').open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    inputs=dict(started_at=base.now(), runner_sha256=base.digest(Path(__file__)), shared_helpers_sha256=base.digest(Path(base.__file__)),
                archive_sha256=hashes,current_interface=interface,enhanced_interface=enhanced_interface,
                reference_run=str(args.reference_run.resolve()),reference_result_sha256=base.digest(args.reference_run/'RESULT.json'),
                reference_full_sha256=base.digest(prior_path),reference_role='Final R2 S3122 tea-state: existing S3121 trace plus certified zero pending bit',tea_regression_sha256=base.digest(tea_path),focused_manifest_sha256=base.digest(HERE/'FOCUSED_53.json'),smoke_only=args.smoke_only,focused_only=args.focused_only,
                selector='fixed coverage driver',policy_rng='Random(seed + 8384)',
                engine_factory=args.engine_factory,session_factory=args.session_factory,signature_factory=args.signature_factory,
                enhance_factory=args.enhance_factory,enhance_signature_factory=args.enhance_signature_factory,workers=args.workers)
    base.write_new(output/'INPUTS.json',inputs)
    options={k:inputs[k] for k in ('workers','engine_factory','session_factory','reference_run','enhance_factory')}
    frontiers=json.loads((base.ARCHIVE/'FRONTIERS.json').read_bytes())['cases']
    seeds={0,17000003,9000026,2000011}
    for page in {c['page'] for c in frontiers if c['cohort']=='fixed'}:
        seeds.add(next(c['seed'] for c in frontiers if c['cohort']=='fixed' and c['page']==page))
    smoke=phase([j for j in jobs if j['prior']['seed'] in seeds],output/'smoke',options)
    full=None;focused_run=None
    if not args.smoke_only and not smoke["fixed"]["errors"] and not smoke["additional"]["errors"]:
        focused_run=phase([j for j in jobs if j["prior"]["seed"] in focus_seeds],output/"focused",options)
    if not args.smoke_only and not args.focused_only and not smoke['fixed']['errors'] and not smoke['additional']['errors']:
        full=phase(jobs,output/'full',options)
    signature_same=interface==base.signature(args.signature_factory)
    enhanced_same=enhanced_interface==base.signature(args.enhance_signature_factory) if args.enhance_factory else True
    result=dict(**inputs,finished_at=base.now(),output=str(output),signature_unchanged=signature_same,
                enhanced_signature_unchanged=enhanced_same,archive_unchanged=all(base.digest(base.ARCHIVE/n)==v for n,v in hashes.items()),
                smoke={k:v for k,v in smoke.items() if k!='runs'},focused=None if focused_run is None else {k:v for k,v in focused_run.items() if k!='runs'},full=None if full is None else {k:v for k,v in full.items() if k!='runs'},
                trained_steps=0,training_eligible=False,
                evidence_boundary='Final R2 actions are the forced-prefix reference. Resampled trajectories remain separate. S3122 sessions are fully executed and captured; R2 shared trace receives its certified zero tea bit; only the local selector view slices the original S3118 so the unchanged released evaluator can check it. Cross-version equality awaits pair.py.')
    result['reference_unchanged']=base.digest(prior_path)==inputs['reference_full_sha256']
    result['valid']=bool(signature_same and enhanced_same and result['archive_unchanged'] and result['reference_unchanged']
                         and not smoke['fixed']['errors'] and not smoke['additional']['errors']
                         and (args.smoke_only or args.focused_only and focused_run is not None and not focused_run["fixed"]["errors"] or full is not None and not full['fixed']['errors'] and not full['additional']['errors']))
    base.write_new(output/'RESULT.json',result)
    print(json.dumps(dict(output=str(output),valid=result['valid']),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
