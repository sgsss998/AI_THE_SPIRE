"""Reproducible Silent A20 discovery runs through the published S/A interface."""
from collections import Counter
from dataclasses import replace
from functools import lru_cache
from hashlib import sha256
from itertools import zip_longest
import json
from random import Random
from struct import Struct

from experiments.episode_outcomes193.rollout import check, endpoint, terminal_or_act_change
from experiments.policy_grid_integration.coverage import choose, SCREEN, EVENT
from experiments.sa_calibration_round6 import release
from silent_env.action193 import choice_slot
from silent_env.observation import schema

STRATEGIES = ('fixed', 'survival', 'explore')
@lru_cache(maxsize=8)
def _state_format(size):
    return Struct(f'<{size}d')


def state_bytes(values):
    return _state_format(len(values)).pack(*values)

CARD = {v + 1: k for k, v in schema()['enums']['CardId'].items()}
ROOM = {v + 1: k for k, v in schema()['enums']['Room'].items()}
DEFEND = {'DEFEND_GREEN', 'SURVIVOR', 'BACKFLIP', 'LEG_SWEEP', 'DODGE_AND_ROLL', 'BLUR', 'DEFLECT'}
PRIORITY = {'NEUTRALIZE', 'DAGGER_THROW', 'DASH', 'PREDATOR', 'GLASS_KNIFE', 'FOOTWORK', 'WRAITH_FORM', 'AFTER_IMAGE', 'NOXIOUS_FUMES', 'BLADE_DANCE'}


def scene(frame):
    v = frame.state.vector
    return '/'.join((f'act{int(v[4])}', ROOM.get(int(v[8]), 'UNKNOWN'), SCREEN.get(int(v[6]), 'UNKNOWN'), frame.page))


def option_row(v, action):
    slot = choice_slot(action)
    if slot is None:
        return ()
    start = 322 + slot * 6
    return tuple(map(int, v[start:start + 6]))


def survival_score(v, action):
    if int(v[6]) == 9 and v[7]:
        if action < 60:
            card = CARD.get(int(v[1253 + 6 * (action % 10)]))
            damage = sum(max(0, v[i + 8]) * max(1, v[i + 9]) for i in range(993, 1253, 52) if v[i + 6])
            if card in DEFEND:
                return 65 if damage > v[900] + 2 else 5
            if action >= 10:
                target = 993 + (action // 10 - 1) * 52
                effective_hp = v[target + 1] + v[target + 3]
                if effective_hp <= (3 if card == 'NEUTRALIZE' else 6):
                    return 95
                return (83 if card == 'NEUTRALIZE' else 60 if card in PRIORITY else 45) - min(effective_hp, 200) / 1000
            return 70 if card in PRIORITY else 40
        if 70 <= action < 105:
            return 75 if v[0] * 2 < v[1] else 8
    row = option_row(v, action)
    if row:
        kind, arg, arg1 = row[:3]
        if kind == 7:
            room = ROOM.get(arg1)
            return {'REST': 80 if v[0] * 3 < v[1] * 2 else 55, 'ELITE': 12, 'SHOP': 60 if v[2] >= 90 else 25, 'TREASURE': 75, 'EVENT': 50}.get(room, 35)
        if kind == 10:
            return 85 if arg == int(v[0] * 3 >= v[1] * 2) else 35
        if kind == 1:
            return 68 if CARD.get(arg) in PRIORITY else 50
        return {2: 80, 3: 55, 4: 85, 5: 70, 6: 10, 12: 80}.get(kind, 40)
    return -20 if 105 <= action < 110 else 0


def select(frame, legal, rng, strategy, visits):
    if len(legal) == 1:
        return legal[0]
    if strategy == 'fixed':
        return choose(legal, rng)
    v = frame.state.vector
    if strategy == 'survival':
        scores = {action: survival_score(v, action) for action in legal}
        # A shop can close and reopen with identical holdings. Try an untried
        # alternative when the exact same public position returns on this floor.
        position = (frame.page, sha256(state_bytes(v)).digest(), tuple(legal))
        for action in legal:
            scores[action] -= 150 * visits[position, action]
        high = max(scores.values())
        selected = rng.choice([a for a in legal if scores[a] == high])
        visits[position, selected] += 1
        return selected
    # Count displayed identities across the run so duplicate faces, different targets,
    # and rarely used controls all get a chance. The random tie break is seed-local.
    keys = {}
    for action in legal:
        row = option_row(v, action)
        identity = tuple(row[:4]) if row else int(v[1253 + 6 * (action % 10)]) if action < 60 else None
        keys[action] = (frame.page, int(v[6]), action, identity)
    low = min(visits[key] for key in keys.values())
    selected = rng.choice([a for a in legal if visits[keys[a]] == low])
    visits[keys[selected]] += 1
    return selected


def fingerprint(frame):
    h = sha256(state_bytes(frame.state.vector))
    h.update(bytes(frame.supported_actions))
    h.update(b'?' if frame.policy_mask is None else bytes(frame.policy_mask))
    h.update(json.dumps([frame.page, frame.state.state_version, frame.action_version,
                         frame.done, int(frame.engine_steps), frame.action_gaps], separators=(',', ':')).encode())
    return h.digest()


def snapshot(frame, detailed=False):
    if frame is None:
        return None
    v = frame.state.vector
    data = dict(page=frame.page, scene=scene(frame), engine_steps=int(frame.engine_steps),
                hp=int(v[0]), max_hp=int(v[1]), gold=int(v[2]), floor=int(v[3]), act=int(v[4]),
                event=EVENT.get(int(v[9])) if int(v[6]) == 1 else None,
                legal=[i for i, bit in enumerate(frame.supported_actions) if bit],
                gaps=list(frame.action_gaps), complete=frame.policy_mask is not None,
                done=frame.done, sha256=fingerprint(frame).hex())
    if detailed:
        data['state_nonzero'] = [[i, val] for i, val in enumerate(v) if val]
    return data


def _run(seed, strategy, cap, runtime):
    from .oracles.step_checks import audit_frame, audit_transition
    engine = runtime.make_engine()
    session = runtime.make_session(engine)
    frame = session.reset(seed, ascension=20, final_act=True)
    core = engine._source._env
    check(core.seed == seed and core.character == 'SILENT' and core.steps == 0, 'Wrong game at reset')
    rng = Random(seed + 8384)
    visits, scenes, gaps, semantic = Counter(), Counter(), Counter(), Counter()
    actions, trace = [], []
    partial = ui_only = 0
    first_semantic = first_partial = first_issue = terminal = None
    previous = attempted = None
    act3 = heart = False
    summary_floor = None
    while True:
        trace.append(fingerprint(frame))
        scenes[scene(frame)] += 1
        findings = audit_frame(frame)
        if previous is not None:
            findings += audit_transition(previous, actions[-1], frame)
        if findings:
            semantic.update(f['kind'] for f in findings)
            if first_semantic is None:
                first_semantic = dict(step=len(actions), findings=findings, action=actions[-1] if actions else None,
                                      before=snapshot(previous, True), after=snapshot(frame, True))
                first_issue = first_issue or first_semantic
        if frame.policy_mask is None or frame.action_gaps:
            gaps.update(frame.action_gaps)
            if first_partial is None:
                first_partial = dict(step=len(actions), before=snapshot(previous), after=snapshot(frame))
                first_issue = first_issue or first_partial
        # Only this older terminal classifier expects the 3118-field prefix.
        prefix = replace(frame, state=replace(frame.state, vector=frame.state.vector[:3118]))
        try:
            reason = endpoint(prefix, core, cap_reached=len(actions) >= cap)
        except (AssertionError, ValueError) as exc:
            reason = 'endpoint_error'
            gaps[str(exc)] += 1
        if reason:
            if reason == 'terminal':
                check(terminal is not None and terminal.terminated, 'Missing final accepted transition')
                reason = terminal.stage
                summary_floor = terminal.native_summary_floor
            break
        legal = [i for i, bit in enumerate(frame.supported_actions) if bit]
        attempted = select(frame, legal, rng, strategy, visits)
        source = engine._source._current
        prior_values = source.raw_base[:32]
        prior_steps = core.steps
        prior_legal = sum(source.backend_mask)
        partial += int(frame.policy_mask is None)
        try:
            after = session.step(attempted, frame_id=frame.frame_id, action_version=frame.action_version)
            check(after.frame_id != frame.frame_id and core.steps >= prior_steps, 'Action did not consume its decision')
        except (AssertionError, ValueError, RuntimeError, IndexError, KeyError) as exc:
            reason = 'step_error'
            gaps[f'{type(exc).__name__}: {exc}'] += 1
            break
        previous, frame = frame, after
        actions.append(attempted)
        attempted = None
        ui_only += int(prior_steps == core.steps)
        entered_four = prior_values[4] == 3 and core.steps != prior_steps and engine._source._current.raw_base[4] == 4
        if core.done or entered_four:
            terminal = terminal_or_act_change(core, prior_values, prior_steps, prior_legal, engine._source._backend)
            act3 |= terminal.act3_cleared_this_step
            heart |= terminal.heart_killed_this_step
    stop = None
    if reason not in ('loss', 'act3_win', 'heart_win'):
        stop = dict(step=len(actions), reason=reason, action=attempted if attempted is not None else actions[-1] if actions else None,
                    before=snapshot(frame if attempted is not None else previous, True), after=snapshot(frame, True) if attempted is None else None)
        first_issue = first_issue or stop
    result = dict(seed=seed, strategy=strategy, actions=actions, reason=reason, page=frame.page,
                  engine_floor=int(core.floor), engine_steps=int(core.steps), ui_only_actions=ui_only,
                  incomplete_action_sets=partial, summary_floor=summary_floor, act3_cleared=act3, heart_killed=heart,
                  cause=list(frame.action_gaps) if reason == 'unsupported' else list(gaps) if reason.endswith('_error') else [],
                  action_gap_counts=dict(gaps), scene_counts=dict(scenes), semantic_counts=dict(semantic),
                  first_issue=first_issue, first_partial=first_partial, first_semantic=first_semantic,
                  stop=stop, trace_sha256=sha256(b''.join(trace)).hexdigest())
    return result, trace


def trial(seed, strategy, cap=2000, *, runtime=None, verify_repeat=True):
    """Return one JSON row; a repeat checks every published S, A, chosen action and endpoint."""
    if type(seed) is not int or seed < 0 or type(cap) is not int or cap < 0 or strategy not in STRATEGIES:
        raise ValueError('Expected nonnegative integer seed/cap and a declared strategy')
    runtime = release if runtime is None else runtime
    result, trace = _run(seed, strategy, cap, runtime)
    result['determinism'] = {'checked': False, 'matched': None}
    if verify_repeat:
        repeat, second = _run(seed, strategy, cap, runtime)
        mismatch = next((i for i, (a, b) in enumerate(zip_longest(trace, second)) if a != b), None)
        action_diff = next((i for i, (a, b) in enumerate(zip_longest(result['actions'], repeat['actions'])) if a != b), None)
        equal = mismatch is None and action_diff is None and all(result[k] == repeat[k] for k in ('reason','engine_floor','cause','semantic_counts','summary_floor','act3_cleared','heart_killed'))
        result['determinism'] = dict(checked=True, matched=equal, first_different_frame=mismatch,
                                     first_different_action=action_diff, repeat_reason=repeat['reason'],
                                     repeat_trace_sha256=repeat['trace_sha256'])
        if not equal:
            result['determinism']['first_evidence'] = dict(first=(trace[mismatch].hex() if mismatch is not None and mismatch < len(trace) else None),
                second=(second[mismatch].hex() if mismatch is not None and mismatch < len(second) else None),
                actions=[a[action_diff] if action_diff is not None and action_diff < len(a) else None for a in (result['actions'], repeat['actions'])])
    return result
