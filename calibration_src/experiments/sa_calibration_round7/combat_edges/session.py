"""Combat controls for permanent medium-slime casualties after a witnessed large-slime split."""
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.sa_calibration_round7.death_family import session as prev

MEDIUM = frozenset(("ACID_SLIME_M", "SPIKE_SLIME_M"))


def split_slots(witness):
    """Ordered original-game list: child 0, vanished parent, child 1."""
    order = witness["physical_order"]
    actors = witness["rows"]
    if (
        order != [0, -1, 1]
        or len(actors) != 2
        or actors[0]["id"] not in MEDIUM
        or actors[1]["id"] != actors[0]["id"]
        or actors[0]["max"] != actors[1]["max"]
        or witness["alive"] != 1
        or any(a["half_dead"] or a["escaping"] or a["will_escape"] for a in actors)
    ):
        return None
    return (0, 2)


def native_target(witness, compact):
    columns = split_slots(witness)
    if (
        columns is None
        or compact not in range(2)
        or not witness["rows"][compact]["targetable"]
    ):
        return None
    return columns[compact]


def native_action(witness, aid):
    """Translate the targeted portion; the hand or potion slot retains its existing binding."""
    if 10 <= aid < 60:
        row, slot = divmod(aid - 10, 10)
        target = native_target(witness, row)
        return None if target is None else 10 * (target + 1) + slot
    if 75 <= aid < 100:
        row, slot = divmod(aid - 75, 5)
        target = native_target(witness, row)
        return None if target is None else 75 + 5 * target + slot
    return aid


def casualties(frame, witness):
    base = prev.casualties(frame, witness)
    if base is not None:
        return base
    slots = split_slots(witness)
    if slots is None:
        return None
    # Validate every actor, corpse, overlay, power and queue with the existing
    # rule. Only the independently identified, historical parent is omitted.
    row_witness = dict(
        witness, physical_order=[witness["physical_order"][j] for j in slots]
    )
    result = prev.casualties(frame, row_witness)
    if result is None or len(result[0]) != 1 or result[1]:
        return None
    offers = [i for i, ok in enumerate(frame.supported_actions) if ok]
    native = [native_action(witness, i) for i in offers]
    if any(i is None for i in native) or len(set(native)) != len(offers):
        return None
    return result


class Edges(prev.OrdinaryDecisions):
    _publish = _local_dependencies(
        prev.OrdinaryDecisions._publish, casualties=casualties
    )


def attach(owner):
    node = owner
    while not isinstance(node, prev.r3.TransitionSession):
        node = vars(node).get("delegate", vars(node).get("base"))
        if node is None:
            raise prev.r3.InterfaceMismatch("No owned death settlement")
    if type(node.pages) is not prev.OrdinaryDecisions or node._frame is not None:
        raise prev.r3.InterfaceMismatch("Expected unused ordinary-casualty owner")
    node.pages = Edges(delegate=node.pages._parent, backing=node.backing)
    return owner
