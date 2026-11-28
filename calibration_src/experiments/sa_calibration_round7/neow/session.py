"""Expose settled simple paid Neow gifts, leaving the game's next map decision intact."""
from dataclasses import replace

from experiments.common_relic193.rules import START, relic_id
from experiments.neow_reward_640.session import CURSES
from experiments.policy_neow_cards.session import page, require
from silent_env.action193 import POLICY_VERSION

# Counter is encoded as the retail counter + 1. Old Coin adds 300 to the wallet.
RELICS = {
    "BIRD_FACED_URN": ("BirdFacedUrn", 0), "CAPTAINS_WHEEL": ("CaptainsWheel", 0),
    "TOUGH_BANDAGES": ("ToughBandages", 0), "TORII": ("Torii", 0),
    "GIRYA": ("Girya", 1), "OLD_COIN": ("OldCoin", 0), "PEACE_PIPE": ("PeacePipe", 0),
    "POCKETWATCH": ("Pocketwatch", 0), "SHOVEL": ("Shovel", 0), "WING_BOOTS": ("WingBoots", 4),
}
COUNTERS = {relic_id(name): count for name, (_, count) in RELICS.items()}
RING = relic_id("RING_OF_THE_SNAKE")
OLD_COIN = relic_id("OLD_COIN")


def settled(old, new, card_ids):
    row = old[334:340]
    if (len(old) != 3118 or len(new) != 3118 or old[:10] != (59,66,99,0,1,20,1,0,10,6)
            or old[22:24] != (13,1) or old[32:112] != (RING,0)+(0,)*78
            or old[706:732:2] != START or any(old[707:732:2]) or old[1769] != 4
            or row[0] != 9 or row[3:] != (0,0,1) or new[6:10] != (5,0,10,0)):
        return None
    gift, cost = row[1:3]
    if gift not in (14,16,18) or cost not in (3,4,5,6):
        return None
    # 3 = lose 10% maximum HP, 4 = lose all gold, 5 = curse, 6 = lose 30% of current HP.
    hp, maximum, wallet = old[:3]
    tenth = int(maximum)//10
    if cost == 3:
        maximum -= tenth
        hp = min(hp, maximum)
    elif cost == 4:
        wallet = 0
    elif cost == 6:
        hp -= int(hp)//10*3
    out = list(old)
    if gift == 16:
        wallet += 250
    elif gift == 18:
        hp += 2*tenth
        maximum += 2*tenth
    else:
        rid, counter = new[34:36]
        if rid not in COUNTERS or COUNTERS[rid] != counter:
            return None
        out[23] = out[1762] = 2
        out[34:36] = (rid,counter)
        if rid == OLD_COIN:
            wallet += 300
    out[:3] = [hp,maximum,wallet]
    if cost == 5:
        card = int(new[732])
        if not (0 < card <= len(card_ids) and card_ids[card-1] in CURSES and new[733] == 0):
            return None
        out[22] = out[1763] = 14
        out[732] = card
        if new[2586] not in (0,2):
            return None
        out[2586] = new[2586]
    # The next kernel screen is a map. Validate all run/deck/inventory effects before staging Leave.
    for lo, hi in ((0,6),(10,322),(706,1769),(1770,2683),(2748,2968),(3114,3118)):
        if tuple(out[lo:hi]) != new[lo:hi]:
            return None
    out[322:706] = [8,0,0,0,0,1] + [0]*378
    out[1769] = 1
    out[2683:2748] = [2]+[0]*64
    out[2968:3114] = [2,1]+[0]*144
    return out


class PaidNeowMixin:
    def step(self, action_id, *, frame_id, action_version):
        with self._lock:
            before = self._current
            after = super().step(action_id,frame_id=frame_id,action_version=action_version)
            if (action_id != 112 or before is None or before.page != "NEOW_OFFERS" or before.engine_steps
                    or after.page != "NEOW_RESULT_UNVERIFIED"):
                return after
            source = self._legacy._source
            raw = self._raw
            values = settled(before.state.vector, source.state.vector, self._source._backend.CARD_IDS)
            if values is None:
                return after
            require(source is self._inner._current and raw is self._source._current and raw.state.vector == source.state.vector
                    and self._current is after and self._legacy._current is self._bound and not (source.done or after.done)
                    and source.page == "DELEGATED" and before.action_version == after.action_version == POLICY_VERSION
                    and raw.engine_steps == source.engine_steps == after.engine_steps == self._source._env.steps == 1
                    and len(raw.packet_sha256) == 64 and raw.packet_sha256 == raw.choice_metadata["packet_sha256"],
                    "Opening claim must have a current receipt for this same game")
            result = page(source,"NEOW_RESULT",values,{110})
            frame = self._sync(self._legacy._cost_projection(self._legacy._version(result)),None)
            # Original Leave on an empty belt has one player action.
            self._current = replace(frame, policy_mask=frame.supported_actions, action_gaps=())
            return self._current
