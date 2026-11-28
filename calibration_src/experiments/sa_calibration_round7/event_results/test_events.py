from pathlib import Path
import pytest
from unittest.mock import patch
from experiments.sa_calibration_round6.reference import read
from experiments.sa_calibration_round7.wall.verify import step
from experiments.sa_calibration_round7.event_results import candidate,session
from experiments.sa_calibration_round7.event_results.verify import evidence,original_upgrades

HERE=Path(__file__).resolve().parent
PROBES=read(HERE/'PROBES.json')


@pytest.mark.parametrize('row',PROBES,ids=lambda x:str(x['seed']))
def test_each_previous_stop_reaches_map_after_confirming_observed_result(row):
    fact=evidence(row)
    assert fact['passed']
    if 'eligible' in fact:
        original_upgrades([fact])
        assert fact['actual_upgraded']==fact['original_java_upgraded']


@pytest.fixture(scope='module')
def cases():
    result={}
    evaluate=session.event_result
    def capture(name,slot,v,w,seed):
        result[name,slot]=(v,w,seed)
        return evaluate(name,slot,v,w,seed)
    with patch.object(session,'event_result',side_effect=capture):
        for entry in PROBES:
            e=candidate.make_engine()
            s=candidate.make_session(e)
            f=s.reset(entry['seed'])
            for a in entry['actions']:
                f=step(s,f,a)
    assert len(result)==len(PROBES)
    return result


def change(vector,slot,value):
    values=list(vector)
    values[slot]=value
    return tuple(values)


def test_charge_wrong_gold_or_healing_is_detected(cases):
    for (name,physical),(offer,after,seed) in cases.items():
        assert session.event_result(name,physical,offer,after,seed) is not None
        assert session.event_result(name,physical,offer,change(after,2,after[2]+1),seed) is None


def test_box_wrong_curse_or_existing_relic_is_detected(cases):
    v,w,seed=cases['Big Fish',2]
    assert session.event_result('Big Fish',2,v,change(w,706+2*int(v[22]),session.MULTI_UPGRADE),seed) is None
    assert session.event_result('Big Fish',2,v,change(w,32,w[32]+1),seed) is None


def test_same_face_upgraded_in_wrong_position_is_detected(cases):
    v,w,seed=cases['Shining Light',0]
    chosen=next(i for i,(a,b) in enumerate(zip(session.deck(v),session.deck(w))) if a[1]!=b[1])
    copy=list(w)
    copy[707+2*chosen]-=1
    other=next(i for i,(_,n) in enumerate(session.deck(w)) if not n and i!=chosen)
    copy[707+2*other]+=1
    assert session.event_result('Shining Light',0,v,tuple(copy),seed) is None
