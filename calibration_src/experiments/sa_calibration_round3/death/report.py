"""Aggregate the local release checks and original-game evidence, with stable file identities."""
import json
from .cohort import HERE,digest
def read(n):return json.loads((HERE/n).read_text())
def main():
    cohort=read('COHORT.json');cross=read('ANCHORS.json');split=read('SPLIT.json')
    rows=cohort['actual_replays'];fixed=[r for r in rows if r['cohort']=='fixed']
    advanced=[r for r in fixed if r['new_actions']];assert len(advanced)==1
    summary=dict(anchors=[dict(seed=x['seed'],input_sequence=x['sequence'],original_action=x['follow_receipt']['action'],after=x['r3']['after'],next_supported=x['r3']['next_mask']) for x in cross],
         fixed=dict(sole_death_stops=63,spore_candidates=len(fixed),advanced_one=len(advanced),advanced_seeds=[r['seed'] for r in advanced],converted_to_terminal=sum(r['first_successor']['done'] for r in advanced)),
         additional=dict(sole_death_stops=8,spore_candidates=len(rows)-len(fixed),advanced_one=sum(bool(r['new_actions']) for r in rows if r['cohort']=='additional')),
         split=dict(compared=split['compared_unique_frame_slots'],present=split['counts'],unrepresented=split['unrepresented'],width_added=0),
         official_index='OFFICIAL.json',
         sources={n:digest(HERE/n) for n in ('session.py','split.py','anchors.py','cohort.py','verify_rules.py','verify_split.py','test_death.py','ANCHORS.json','COHORT.json','SPLIT.json','RULES.json','OFFICIAL.json','official.py')})
    (HERE/'RESULT.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__':main()
