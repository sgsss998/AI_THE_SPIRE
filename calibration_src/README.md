# Silent A20 compact-environment calibration sources

Round five composes independent chest, shop and Wheel of Change adapters on the pinned R4 engine. Use `python3 docs/calibration/r5/verify.py` in the repository checkout to verify the published samples, outcome counts and public replay. The full local replay also uses the private retail captures and separately built game backend. [Round five results](../docs/calibration/r5/README.md)

`experiments/sa_calibration_round4` adds separate Neow, monster-death and event adapters on the pinned R3 entry. The public checks need only standard Python. Run `python3 docs/calibration/r4/verify.py` from the repository root to validate the released receipts, 704 seed results and the 339-input retail holdout. The [R4 report](../docs/calibration/r4/README.md) links the frozen interface and three distinct replay results.

The `experiments/sa_calibration_round3` directory contains the R3 action adapters, Split decoder and S3122/A193 model entry. They are additions to the separately built compact environment. Installing the original game or this repository alone does not provide the R2 policy engine or the native extension binaries. The pinned parent and the measured environment signature are recorded in [the R3 progress report](../docs/calibration/r3/README.md) and [interface.json](../docs/calibration/r3/interface.json).
