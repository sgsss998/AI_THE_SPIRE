"""Exercise the frozen full release on two actual original journeys and a held-out positive Split observation."""
import gzip
import json
from . import anchors
from .cohort import HERE,ROOT,INDEX,digest
from .. import release

def positive(interface):
    ref=json.loads(INDEX.read_bytes())['public']['full']
    data=json.loads((INDEX.parent/ref['path']).read_bytes())['runs']
    for r in data:
        if r['cohort']!='fixed':continue
        path=Path(r['trace']['path'])
        with gzip.open(path) as f:frames=json.load(f)
        k=next((i for i,f in enumerate(frames) if any(z is True for z in release.split_markers(f['state']))),None)
        if k is None:continue
        e=release.make_engine();s=release.make_session(e);f=s.reset(r['seed'])
        for a in r['episode']['actions'][:k]:
            assert f.supported_actions[a]
            f=s.step(a,frame_id=f.frame_id,action_version=f.action_version)
        assert f.state.state_version==interface['state_version'] and len(f.state.vector)==3122
        v=f.state.vector;flags=release.split_markers(v);assert any(x is True for x in flags)
        return dict(seed=r['seed'],original_reference='saved R2 simulator trace',reference_trace_sha256=digest(path),prefix_actions=k,
                    width=len(v),floor=v[3],slots=[dict(id=e._source._backend.MONSTER_NAMES[int(v[j])-1],hp=v[j+1],max=v[j+2]) if v[j] else None for j in range(993,1253,52)],flags=flags)
    raise AssertionError('Could not recover a positive natural public Split decision')
from pathlib import Path
def main():
    interface=release.interface_signature().metadata()
    freeze=HERE.parent/'INTERFACE.json'; assert interface==json.loads(freeze.read_bytes())
    cases=[anchors.capture(anchors.triple.SEED,anchors.triple.ARCHIVE,335,release),
           anchors.capture(anchors.probe.SEED,anchors.probe.ARCHIVE,526,release)]
    for r in cases:
        v=r['r3']; assert v['width']==v['shape_after']==3122 and v['state_version']==interface['state_version']
        assert all(x is not True for x in v['split_before']+v['split_after'])
    pos=positive(interface)
    out=dict(signature_sha256=digest(freeze),decoder_sha256=interface['state_decoder_sha256'],
             anchors=cases,positive_formal_simulated_decision=pos,archived_boss_original_and_same_kernel='SPLIT.json')
    (HERE/'OFFICIAL.json').write_text(json.dumps(out,indent=2)+'\n')
    print(pos)
if __name__=='__main__':main()
