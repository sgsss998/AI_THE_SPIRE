"""Retire only our four experiment processes after their native evidence was saved."""
import os
import signal
from .native import NATIVE, SEED, read
from native_runtime import sha, write, now

def close(name, first_attempt=False):
    dest=NATIVE/name
    process=read(dest/"process.json");session=read(dest/"bridge/active_session.json")
    from pathlib import Path
    session_dir=Path(session["session_dir"])
    assert session_dir.resolve().is_relative_to(dest.resolve()) and read(session_dir/"session.json")["parent_pid"]==process["pid"]
    assert process["cwd"]==str(dest/"game") and not (dest/"process_exit.json").exists()
    path=dest/"chest_check";current=read(session_dir/"current.json")
    assert current["raw"]["game_state"]["seed"]==SEED
    if first_attempt:
        assert name=="compact_native_r5_chest_ink_001" and current["raw"]["game_state"]["floor"]==1
        attempts=(path/"actions.jsonl").read_bytes().splitlines()
        assert len(attempts)==32 and not (path/"END.json").exists()
        reason="Stopped after original hand confirmation did not play the incidental Strike; restart with both witnessed actions."
    else:
        assert read(path/"END.json")["raw_hash"]==current["raw_hash"] and current["raw"]["game_state"]["screen_type"]=="MAP"
        reason="Original branch observed on the subsequent map."
    write(path/"CLOSE.json",dict(reason=reason,journal_sha256=sha(path/"actions.jsonl"),at=now(),pid=process["pid"]))
    os.kill(process["pid"],signal.SIGTERM)

if __name__=="__main__":
    for name in ("ink_001","ink_002","key_001","leave_001"):
        close("compact_native_r5_chest_"+name,name=="ink_001")
