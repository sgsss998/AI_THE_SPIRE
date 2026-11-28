from pathlib import Path
from unittest.mock import patch
from experiments.sa_calibration_round6.reference import read,write,sha
from ..event_results import verify
from . import candidate

HERE=Path(__file__).resolve().parent


def main():
    old=read(verify.HERE/'RESULT.json')
    pending={x['seed'] for x in old['cases'] if not x['passed']}
    rows=[r for r in verify.records()[0] if r['seed'] in pending]
    with patch.object(verify,'candidate',candidate):
        cases=[verify.evidence(row) for row in rows]
    write(HERE/'PROBES.json',[dict(seed=r['seed'],actions=r['actions']) for r in rows])
    write(HERE/'RESULT.json',dict(previous_stops=len(rows),resolved=sum(r['passed'] for r in cases),
                                  original_case_index=sha(verify.HERE/'RESULT.json'),cases=cases))
    print([(r['after_relics'][-1][0],r['passed']) for r in cases])


if __name__=='__main__':
    main()
