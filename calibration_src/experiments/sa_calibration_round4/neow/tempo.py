"""Check how elapsed original UI time changes the observation without changing the game roll."""
import json
from .verify import HERE, apply, make


def check():
    from experiments.sa_calibration_round4 import release
    sig=release.interface_signature().metadata()
    comparisons=[]
    for seed in (46,48):
        sides=[]
        for timing in ('fast','settled'):
            s=make(timing)
            f=s.reset(seed)
            frames=[]
            for action in (110,112,111,110,110):
                f=apply(s,f,action)
                frames.append(f)
            sides.append(frames)
        diffs=[]
        for (fast,settled),expected in zip(zip(*sides),([], [22,732,1763], [22,732,1763], [], [])):
            different=[i for i,(x,y) in enumerate(zip(fast.state.vector,settled.state.vector)) if x!=y]
            assert different==expected and fast.supported_actions==settled.supported_actions
            assert fast.policy_mask==settled.policy_mask and fast.engine_steps==settled.engine_steps
            diffs.append(dict(page=fast.page,state_difference=different,action_masks_equal=True))
        comparisons.append(dict(seed=seed,differences=diffs,same_3122_map=True))
    assert sig==release.interface_signature().metadata()
    result=dict(interface=sig,seed_pairs=comparisons,timing_modes=['fast','settled'],default='settled')
    (HERE/'TEMPO.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':check()
