"""Ordinary paid card purchase tied to the current shop row, price and permanent deck."""
from dataclasses import replace
from experiments.public_shop.session import check, shop_rows
from experiments.sa_calibration_round5.shop.session import Merchandise
from experiments.common_relic193.rules import relic_id

# These relics can replace sold stock, change the purchased card, return money,
# or change counters in addition to the ordinary debit and card acquisition.
SPECIAL = {relic_id(name) for name in ("THE_COURIER","CERAMIC_FISH","MAW_BANK",
                                        "TOXIC_EGG","MOLTEN_EGG","FROZEN_EGG")}


class CardShelf(Merchandise):
    def _shelf(self):
        frame = super()._shelf()
        source = self._core._session._current
        v = self._parent.state.vector
        if (source.engine_steps != self._parent.engine_steps or v[5:9] != (20,8,0,1)
                or not 0 < v[22] < 60 or SPECIAL.intersection(v[32:112:2])
                or source.packet_sha256 != source.choice_metadata.get("packet_sha256")):
            return frame
        stock = source.choice_metadata["choices"]
        eligible = {(b.choice_row,b.simulator_id) for b in source.bindings if b.operation == "shop_internal_slot"}
        rows = shop_rows(v)
        for index,(slot,row) in enumerate(rows):
            if slot >= 7 or not row[5] or (slot,81+slot) not in eligible:
                continue
            item = stock[slot]
            if (item["slot"] == slot and item["sim_action"] == 81+slot and item["kind_name"] == "CARD"
                    and item["legal"] and item["described"] and item["source_ref"]["container"] == "displayed_shop_slots"
                    and item["card_identity"]["observation_id"] == row[1] and item["parameters"][:3] == row[1:4]
                    and row[3] <= v[2] and source.backend_mask[81+slot]):
                # The inherited purchase executes this exact slot once and checks the actual
                # debit, stock disappearance, untouched old deck and appended card face.
                self._commands[110+index] = slot
        public = list(frame.state.vector)
        public[1769] = sum(int(row[5]) for _,row in rows)
        self._current = replace(frame,state=replace(frame.state,vector=tuple(public)),
                                supported_actions=tuple(i in self._commands for i in range(len(frame.supported_actions))))
        return self._current


def install(engine):
    old = engine._inner
    check(type(old) is Merchandise and old._current is None and old.shop_page is None,
          "Card shop adapter requires a fresh R5 merchandise adapter")
    shelf = CardShelf(old)
    engine._inner = engine._legacy._delegate = shelf
    engine._normal_shop_stack = (engine._legacy,shelf,shelf._core._session)
    return engine
