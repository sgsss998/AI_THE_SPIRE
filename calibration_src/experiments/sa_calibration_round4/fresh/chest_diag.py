"""Diagnostic-only claim of one typed, legal relic linked to the same sapphire key."""
from experiments.common_relic193.rules import relic_id
from experiments.sa_calibration_round2.boss import session as boss
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.treasure_reward_640.session import KEY, RELIC, LEAVE, bound_rows
from experiments.sa_calibration_round4 import release

INK = relic_id('INK_BOTTLE')


class InspectChest(boss.Chest):
    _publish = _local_dependencies(boss.Chest._publish,CHEST_RELICS=boss.CHEST_RELICS|{INK})

    def step(self, action, *, token):
        if not (110<=action<110+len(self.rows) and self.rows[action-110]==(RELIC,INK)):
            return super().step(action, token=token)
        # Bind the exact uncoupled row to its live backend slot. Both offers
        # disappear together; only Ink Bottle is granted. Check the native
        # result without repairing any vector, counter or RNG state.
        assert self.active and token==self.frame().token and self.provider.peek()==self.packet
        row=action-110
        assert self._actions[action]==('relic',81+row) and (KEY,2) in self.rows
        old=self.packet
        assert bound_rows(self.provider,old)==self.rows and old.mask146[81+row]
        self.active=False
        new=self.provider.step(81+row); a,b=old.base,new.base
        assert new.step_count==old.step_count+1 and a[3:6]==b[3:6] and a[10:12]==b[10:12]
        expected=list(a[:112]);pos=32+int(a[23])*2
        assert INK not in a[32:pos:2] and not a[14]
        expected[23]+=1;expected[pos:pos+2]=[INK,1]
        assert tuple(expected)==b[:112] and b[706:898]==a[706:898]
        remaining=bound_rows(self.provider,new)
        assert remaining==tuple(r for r in self.rows if r[0] not in (KEY,RELIC))
        self.packet,self.rows,self.active=new,remaining,True
        self._publish()
        return self.frame()


class InspectSetup(boss.ChestSetup):
    _capture = _local_dependencies(boss.ChestSetup._capture,CHEST_RELICS=boss.CHEST_RELICS|{INK},Chest=InspectChest)


class InspectEngine(release.Round4Engine):
    setup_class = InspectSetup


def receipt(source, record, frame):
    g=record['before']['raw']['game_state']
    if g['screen_type']!='COMBAT_REWARD' or not record['command'].startswith('choose '):
        return None
    sel=int(record['command'].split()[1]);rewards=g['screen_state']['rewards']
    if not (0<=sel<len(rewards) and rewards[sel].get('relic',{}).get('id')=='InkBottle'):
        return None
    assert any(r.get('link',{}).get('id')=='InkBottle' for r in rewards)
    after=record['after']['raw']['game_state']
    assert after['relics'][:-1]==g['relics'] and after['relics'][-1]['id']=='InkBottle' and after['relics'][-1]['counter']==0
    raw=source._current;slot=sel;physical=81+slot
    row=raw.choice_metadata['choices'][slot]
    assert raw.packet_sha256==raw.choice_metadata['packet_sha256']
    assert row['kind_name']=='RELIC' and row['slot']==slot and row['sim_action']==physical
    assert row['legal'] and row['described'] and row['parameters'][0]==INK
    assert raw.backend_mask[physical] and source._env.is_valid(physical)
    return dict(raw_packet=raw.packet_sha256, physical_id=physical,native_choice_index=sel,
                true_relic='InkBottle',native_counter=0,linked_key='sapphire', existing_core_steps=frame.engine_steps)
