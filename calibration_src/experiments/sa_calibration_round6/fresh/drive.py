"""One blank retail start after the freeze; keep the original game until its natural ending."""
import os
import signal
import sys
import time
from pathlib import Path
from native_runtime import now
from .instance import HERE,DEST,R6,ROOT,read,write,sha

def drive():
    from native_pilot import bind,libraries
    from .. import release
    from experiments.sa_calibration_round4.fresh import physical
    published=read(R6/"FREEZE.json")
    assert published["runtime"]==release.source_hashes()
    Transport,*_=libraries(DEST)
    transport,session,oracle,_=bind(DEST,Transport)
    driver_source=ROOT/"experiments/sa_calibration_round4/fresh/drive.py"
    if not (HERE/"START_OUTPUT.json").is_file():
        assert not (HERE/"START_INPUT.json").exists()
        frame=transport.read_current()
        assert not frame.raw["in_game"] and "start" in frame.raw["available_commands"]
        write(HERE/"START_INPUT.json",dict(utc=now(),seed=None,version="Silent A20",interface_sha256=sha(R6/"INTERFACE.json"),
            frozen_sha256=sha(R6/"FREEZE.json"),driver_sha256=sha(driver_source),actor_sha256=sha(ROOT/"experiments/sa_calibration_round3/fresh/policy.py")))
        opened=transport.start("THE_SILENT",20,timeout=45)
        write(HERE/"START_OUTPUT.json",opened.as_dict())
        assert opened.command=="start THE_SILENT 20" and opened.status=="observed_start"
    from experiments.sa_calibration_round4.fresh import drive as driver
    driver.HERE,driver.DEST=HERE,DEST
    physical.HERE,physical.DEST=HERE,DEST
    write(HERE/"GUI_LEASE.json",dict(expires_monotonic=time.monotonic()+7200))
    driver.run()

def close():
    process=read(DEST/"process.json")
    end=read(HERE/"TERMINAL.json")
    session=Path(read(DEST/"bridge/active_session.json")["session_dir"])
    cur=read(session/"current.json")["raw"]["game_state"]
    assert read(session/"session.json")["parent_pid"]==process["pid"]
    assert cur["screen_type"]=="GAME_OVER" and cur["seed"]==end["summary"]["seed"]
    if not (DEST/"process_exit.json").exists():
        assert process["cwd"]==str(DEST/"game")
        os.kill(process["pid"],signal.SIGTERM)
    write(HERE/"CLOSE.json",dict(terminal_sha256=sha(HERE/"TERMINAL.json"),pid=process["pid"],at=now()))

if __name__=="__main__":
    close() if sys.argv[1:]==["close"] else drive()
