"""Build the read-only purse probe against the same ABI as the active simulator."""
from functools import lru_cache
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from experiments.policy_backend_hand_order.candidate import PINNED_BUILD, PINNED_SHA

HERE = Path(__file__).resolve().parent


def build(folder, source, module):
    assert sha256(PINNED_BUILD.read_bytes()).hexdigest() == PINNED_SHA
    entry = json.loads(PINNED_BUILD.read_bytes())["modules"]["_fixture_setup"]
    args = entry["args"].copy()
    args[args.index(str(PINNED_BUILD.parent / "sources/_fixture_setup.cpp"))] = str(
        source
    )
    out = Path(folder) / entry["file"].replace("_fixture_setup", module)
    args[-1] = str(out)
    subprocess.run(args, check=True, capture_output=True)
    spec = importlib.util.spec_from_file_location(module, out)
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    return extension


@lru_cache(maxsize=1)
def observer():
    # dlopen holds the image after the file is released. Compile once per process;
    # only games currently showing a thief request this optional observation.
    with TemporaryDirectory() as d:
        return build(d, HERE / "purses.cpp", "_r7_thief_purses")
