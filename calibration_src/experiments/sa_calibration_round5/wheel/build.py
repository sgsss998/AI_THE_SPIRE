"""Build against the same C++ classes as the policy owner."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from experiments.policy_backend_hand_order.candidate import PINNED_BUILD, PINNED_SHA, ROOT

HERE=Path(__file__).resolve().parent
NAME='_sa_r5_wheel'


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


def build():
    record=json.loads(PINNED_BUILD.read_bytes())
    assert digest(PINNED_BUILD)==PINNED_SHA and all(digest(ROOT/k)==v for k,v in record['sources'].items())
    recipe=record['modules']['_fixture_setup']
    target_dir=HERE/'build'
    target_dir.mkdir(exist_ok=True)
    target=target_dir/recipe['file'].replace('_fixture_setup',NAME)
    source=HERE/'offer.cpp'
    args=list(recipe['args'])
    args[args.index(str(PINNED_BUILD.parent/'sources/_fixture_setup.cpp'))]=str(source)
    args[-1]=str(target)
    subprocess.run(args,check=True)
    sources=(source,Path(__file__),PINNED_BUILD,ROOT/'vendor/sts_lightspeed/src/game/GameContext.cpp')
    manifest=dict(name=NAME,parent_sha256=PINNED_SHA,file=target.name,sha256=digest(target),
                  sources={str(p.relative_to(ROOT)):digest(p) for p in sources})
    receipt=target_dir/'BUILD.json'
    receipt.write_text(json.dumps(manifest,indent=2)+'\n')
    print(digest(receipt))


if __name__=='__main__':
    build()
