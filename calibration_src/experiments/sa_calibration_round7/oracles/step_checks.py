"""Read-only checks on a full public S3122/A193 frame. No game-driver calls."""
from collections import Counter


def mismatch(kind, expected, actual):
    return {"kind": kind, "expected": expected, "actual": actual}


def audit_frame(frame):
    state = frame.state.vector
    mask = frame.supported_actions
    errors = []
    if len(state) != 3122:
        return [mismatch("state_width", 3122, len(state))]
    if len(mask) != 193:
        return [mismatch("action_width", 193, len(mask))]
    if frame.policy_mask is not None and frame.policy_mask != mask:
        errors.append(mismatch("complete_mask_vs_supported", list(mask), list(frame.policy_mask)))
    if state[1] > 0 and state[0] > state[1]:
        errors.append(mismatch("hp_exceeds_maximum", state[1], state[0]))
    if state[2] < 0:
        errors.append(mismatch("negative_gold", ">=0", state[2]))
    if state[-1] not in (0, 1):
        errors.append(mismatch("tea_charge_domain", [0, 1], state[-1]))
    return errors


def choice_slot(action):
    if 110 <= action <= 169:
        return action - 110
    if 189 <= action <= 192:
        return action - 129
    return None


def options(values):
    return [tuple(values[i:i+6]) for i in range(322, 706, 6) if values[i]]


def deck(values):
    return Counter(tuple(values[i:i+2]) for i in range(706, 898, 2) if values[i])


def reward_checks(before, slot, after):
    from experiments.sa_calibration_round6.rewards.session import inventory

    left, right = before.state.vector, after.state.vector
    if left[4] != 1 or left[5] != 20 or left[8] != 5 or not inventory(left):
        return []
    start = 322 + slot * 6
    kind, item, parameter, _, _, legal = left[start:start+6]
    if not legal:
        return []
    checks = {}
    if before.page == "COMBAT_REWARD" and kind in (3, 4):
        desired_rows = options(left)
        desired_rows.remove(tuple(left[start:start+6]))
        checks["remaining_rewards"] = (desired_rows, options(right))
        if kind == 4 and not parameter:
            checks["ordinary_gold_payout"] = (left[2] + item, right[2])
        if kind == 3:
            belt = list(left[17:17+int(left[16])])
            if 0 in belt:
                belt[belt.index(0)] = item
                checks["ordinary_potion_payout"] = (belt, list(right[17:17+int(right[16])]))
    if before.page == "CARD_REWARD" and kind == 1:
        old = deck(left)
        if old.total() < 96:
            old[(item, parameter)] += 1
            actual = deck(right)
            if old != actual:
                checks["chosen_card_in_permanent_deck"] = (sorted(old.elements()), sorted(actual.elements()))
    return [mismatch(key, expected, actual) for key, (expected, actual) in checks.items() if expected != actual]


def audit_transition(before, action, after):
    mask = before.supported_actions
    if not (0 <= action < len(mask)) or not mask[action]:
        return [mismatch("unsupported_action_executed", "supported before step", action)]
    if len(before.state.vector) != 3122 or len(after.state.vector) != 3122:
        return []  # Width is reported once by audit_frame.
    slot = choice_slot(action)
    if slot is not None and before.page in ("COMBAT_REWARD", "CARD_REWARD"):
        return reward_checks(before, slot, after)
    return []
