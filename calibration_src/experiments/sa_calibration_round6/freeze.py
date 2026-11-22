"""Seal the runtime edition before the independent retail start."""
from datetime import datetime, timezone
from . import release
from .reference import HERE, PARENT_SHA, COMMIT, baseline, read, write, sha

def run():
    baseline()
    signature = release.interface_signature().metadata()
    fixed = HERE / "FREEZE.json"
    if fixed.exists():
        previous = read(fixed)
        assert previous["runtime"] == release.source_hashes()
        assert read(HERE / "INTERFACE.json") == signature
        return
    assert not (HERE / "fresh/START_INPUT.json").exists()
    write(HERE / "INTERFACE.json",signature)
    write(fixed,dict(created_utc=datetime.now(timezone.utc).isoformat(),parent_commit=COMMIT,
          parent_manifest=PARENT_SHA,runtime=release.source_hashes(),interface_sha256=sha(HERE/"INTERFACE.json"),
          state_space=3122,action_space=193,training_updates=0))

if __name__ == "__main__":
    run()
