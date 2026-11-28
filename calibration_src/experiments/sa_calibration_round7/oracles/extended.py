"""Check the historical state and the five S3127 purse fields at each decision."""
from dataclasses import replace
from . import step_checks as base
from ..death_family.thief_rewards.observation.session import OFFSETS, WIRE


def historical(frame):
    return replace(frame,state=replace(frame.state,vector=frame.state.vector[:3122]))


def audit_frame(frame):
    values=frame.state.vector
    if len(values)!=3127:
        return [base.mismatch("state_width",3127,len(values))]
    issues=base.audit_frame(historical(frame))
    for i,(offset,amount) in enumerate(zip(OFFSETS,values[3122:],strict=True)):
        if amount!=int(amount) or amount<0:
            issues.append(base.mismatch(f"invalid_stolen_gold_slot_{i}","nonnegative integer",amount))
        elif amount and (not values[7] or values[offset] not in WIRE):
            issues.append(base.mismatch(f"stolen_gold_on_non_thief_slot_{i}",0,amount))
    return issues


def audit_transition(before,action,after):
    if len(before.state.vector)!=3127 or len(after.state.vector)!=3127:
        return []
    issues=base.audit_transition(historical(before),action,historical(after))
    a,b=before.state.vector,after.state.vector
    # Within an unchanged living thief formation, each newly stolen coin leaves the wallet.
    if (a[7] and b[7] and a[3:5]==b[3:5] and all(a[i]==b[i] for i in OFFSETS)
            and any(a[i] in WIRE for i in OFFSETS)
            and all(a[i] not in WIRE or (a[i+1]>0 and b[i+1]>0) for i in OFFSETS)):
        stolen=sum(b[3122:])-sum(a[3122:])
        # Other card/relic effects can move gold independently. Track the transfer on a plain turn.
        from experiments.common_relic193.rules import relic_id
        if action==170 and set(a[32:112:2])<={0,relic_id("RING_OF_THE_SNAKE")} and stolen>0 and a[2]-b[2]!=stolen:
            issues.append(base.mismatch("thief_wallet_vs_purses",stolen,a[2]-b[2]))
    return issues
