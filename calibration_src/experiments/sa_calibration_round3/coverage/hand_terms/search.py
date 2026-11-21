"""Catalog closed first-hand CommunicationMod logs by ordered card occurrence."""
import json
from pathlib import Path
from collections import Counter
from hashlib import sha256
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def shown(c):
    if c.get('public_cost',{}).get('available'):
        return c['public_cost'].get('text')
    return None

def main():
    logs=sorted(set((ROOT.parent/'AI_THE_SPIRE_实机验证').rglob('bridge/sessions/*/raw.jsonl')) | set((ROOT/'native_runtime').glob('*/bridge/sessions/*/raw.jsonl')))
    sources=[];hits=[];groups=Counter()
    for p in logs:
        if 'round3_unseeded' in str(p) or 'fresh/' in str(p):continue
        try: it=p.open()
        except OSError:continue
        count=0
        with it:
            for ln in it:
                if not ln.endswith('\n'):continue
                point=json.loads(ln);g=(point.get('raw') or {}).get('game_state') or {};c=g.get('combat_state') or {}
                if g.get('screen_type')!='NONE' or g.get('class')!='THE_SILENT' or g.get('ascension_level')!=20:continue
                count+=1; hand=c.get('hand',[])
                for i,card in enumerate(hand):
                    for j in range(i):
                        prev=hand[j]
                        if prev['id']!=card['id']:continue
                        up=(prev['upgrades'],card['upgrades']);cost=(prev.get('cost_for_turn'),card.get('cost_for_turn'))
                        display=(shown(prev),shown(card))
                        reasons=[]
                        if up[0]!=up[1]:reasons.append('upgrade')
                        if cost[0]!=cost[1]:reasons.append('internal_cost_for_turn')
                        if display[0] is not None and display[1] is not None and display[0]!=display[1]:reasons.append('public_cost')
                        if reasons:
                            for rr in reasons:groups[rr]+=1
                            hits.append([str(p),g['seed'],point['sequence'],card['id'],[j,i],up,cost,display,reasons])
        if count:sources.append([str(p),count])
    oracles=sorted(set((ROOT/'native_runtime').glob('*/native_oracle/*/*.jsonl')) | set((ROOT.parent/'AI_THE_SPIRE_实机验证').rglob('native_oracle/*/*.jsonl')))
    oracle_hits=[];observations=0;occupied=0
    for p in oracles:
        if 'round3_unseeded' in str(p):continue
        with p.open() as stream:
            for line in stream:
                if not line.endswith('\n'):continue
                packet=json.loads(line)
                kind=packet.get('kind');data=packet.get('data') or {}
                if kind=='native_state':native=data.get('payload') or {}
                elif kind=='native_capture' and data.get('observed_bracket_equal'):native=data.get('pre') or {}
                else:continue
                h=native.get('hand',[])
                if not h or not any(shown(c) is not None for c in h):continue
                observations+=1;occupied+=len(h)
                for i,c in enumerate(h):
                    for j,t in enumerate(h[:i]):
                        if c['id']==t['id'] and None not in (shown(c),shown(t)) and shown(c)!=shown(t):
                            oracle_hits.append(dict(file=str(p),seq=packet['seq'],id=c['id'],slots=[j,i],display=[shown(t),shown(c)],upgrade=[t['times_upgraded'],c['times_upgraded']],uuid=[t['uuid'],c['uuid']]))
    (HERE/'SEARCH.json').write_text(json.dumps(dict(files=len(logs),queried=sum(x[1] for x in sources),counts=groups,sources=sources,pairs=hits,oracle_files=len(oracles),oracle_observations=observations,oracle_rows=occupied,oracle_same_id_different_public_icon=oracle_hits),ensure_ascii=False,indent=1))
if __name__=='__main__':main()
