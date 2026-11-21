"""Record the exact formal interface before running the final R5 regression."""
from datetime import datetime,timezone
from . import release
from .reference import HERE,PARENT,PARENT_MANIFEST,read,sha,write


def freeze():
    data=dict(parent_commit=PARENT,parent_local_edition_sha256=PARENT_MANIFEST,components=release.source_hashes(),
              state_space=3122,action_space=193,training_updates=0)
    record=HERE/"FREEZE.json"
    if record.is_file():
        previous=read(record)
        if all(previous.get(k)==v for k,v in data.items()):
            assert read(HERE/"INTERFACE.json")==release.interface_signature().metadata()
            return
        saved=HERE/"editions/rc1"
        assert sha(record)==sha(saved/"FREEZE.json")
        assert read(HERE/"INTERFACE.json")==read(saved/"INTERFACE.json")
        for name,digest in previous["components"].items():
            assert sha(saved/name)==digest,name
        data.update(supersedes=sha(saved/"FREEZE.json"),
                    reason="Count the actual store choices with full potion slots and insufficient gold",edition="rc2")
    write(HERE/"INTERFACE.json",release.interface_signature().metadata())
    write(record,dict(created_utc=datetime.now(timezone.utc).isoformat(),**data))


if __name__=="__main__":
    freeze()
