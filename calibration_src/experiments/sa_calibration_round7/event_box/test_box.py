from unittest.mock import patch
import pytest
from experiments.sa_calibration_round6.reference import read
from experiments.sa_calibration_round7.event_box import candidate,session,verify
from experiments.sa_calibration_round7.wall.verify import step
from experiments.sa_calibration_round7.event_results.test_events import change

PROBES=read(verify.HERE/'PROBES.json')


@pytest.fixture(scope='module')
def captures():
    observations={}
    original=session.settled
    def capture(v,w):
        observations[session.event.relics(w)[-1][0]]=(v,w)
        return original(v,w)
    for entry in PROBES:
        game=candidate.make_session()
        f=game.reset(entry['seed'])
        with patch.object(session,'settled',side_effect=capture):
            for aid in entry['actions']:
                f=step(game,f,aid)
        assert f.page=='EVENT_RESULT' and f.supported_actions[110]
        next_frame=step(game,f,110)
        assert next_frame.state.vector[6]==5 and next_frame.engine_steps==f.engine_steps
    return observations


def test_late_card_callbacks_include_new_relic(captures):
    for item,field,gain in (('CERAMIC_FISH',2,9),('DARKSTONE_PERIAPT',1,6)):
        v,w=captures[session.relic_id(item)]
        assert w[field]-v[field]==gain
        assert session.settled(v,change(w,field,v[field])) is None


def test_curse_count_includes_the_new_regret_and_existing_curses(captures):
    v,w=captures[session.DOLL]
    assert session.event.relics(w)[-1][1]==4
    i=32+2*(int(w[23])-1)+1
    assert session.settled(v,change(w,i,3)) is None


def test_new_belt_slots_must_be_empty_and_preserve_previous_slots(captures):
    v,w=captures[session.POTION_BELT]
    assert w[16]==w[1771]==v[16]+2
    assert session.settled(v,change(w,1771,v[16])) is None
    assert session.settled(v,change(w,17+int(v[16]),1)) is None


def test_omamori_checks_old_inventory_prior_to_late_hooks(captures):
    v,w=captures[session.event.CERAMIC]
    # Change the pre-existing relic to a two-charge charm in both states. The already-resolved
    # Regret, the unspent charge and the +9 late pickup bonus must no longer be accepted.
    before=change(change(v,32,session.event.OMAMORI),33,3)
    after=change(change(w,32,session.event.OMAMORI),33,3)
    assert session.settled(before,after) is None
