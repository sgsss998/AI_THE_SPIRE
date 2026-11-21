"""Prepare an empty isolated original game. This module does not supply a seed."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ID="compact_native_sa_round4_unseeded_001"
DEST=ROOT/"native_runtime"/ID


def stage():
    from native_runtime import prepare, verify, write, sha
    from apply_native_bootstrap_guard import apply
    from attach_native_settlement import attach
    from experiments.action193_native import stage as wire
    if not DEST.exists():
        prepare(ID)
    assert not (DEST/"process.json").exists()
    if not (DEST/"bootstrap_guard.json").exists():
        apply(ID)
    attach(DEST)
    config=verify(DEST)
    for rel in (*wire.PINNED,"src/core/grid193.py"):
        f=DEST/"transport_snapshot"/rel
        if rel in wire.PINNED:
            assert sha(f)==wire.PINNED[rel]
            content=wire.rendered(rel)
        else:
            assert not f.exists()
            content=(wire.HERE/"grid.py").read_bytes()
        f.write_bytes(content)
        config["files"][str(f.relative_to(DEST))]=dict(source=str(wire.HERE),sha256=sha(f))
    config["native_action_version"]="communicationmod-193-v1"
    write(DEST/"target.json",config)
    assert not verify(DEST)["fixture_mod_enabled"]
    assert not (DEST/"fixture_config.json").exists() and not any((DEST/"game/saves").iterdir())


if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="launch":
        from native_runtime import launch
        raise SystemExit(launch(ID))
    stage()
