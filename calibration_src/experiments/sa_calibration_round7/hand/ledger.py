"""Bind a native hand choice to its signed display rank and occurrence in S."""
from dataclasses import replace
from experiments.retail_deselect_order193.compare import cards


def bind(row,frame,engine):
    g=row["before"]["raw"]["game_state"]
    action=row["aid"]
    if (g["screen_type"]!="HAND_SELECT" or not (110<=action<120 or 179<=action<189)
            or frame.state.vector[26] not in (6,9,21,22,28) or frame.done):
        return None
    compact=replace(frame,state=replace(frame.state,vector=frame.state.vector[:3118]))
    hand,selected=cards(compact)
    side,offset,shown=(hand,110,"hand") if action<120 else (selected,179,"selected")
    real=g["screen_state"][shown]
    ids=engine._source._backend.CARD_IDS
    sequence=[(ids[c.card_id-1],c.upgrades) for c in side]
    if sequence!=[(c["id"],c["upgrades"]) for c in real] or action-offset>=len(real):
        return None
    card=real[action-offset]
    return action,dict(binding="matching signed display rank",side=shown,face=card["id"],uuid=card["uuid"],
                       slot=action-offset,physical_model_slot=side[action-offset].backing_slot)
