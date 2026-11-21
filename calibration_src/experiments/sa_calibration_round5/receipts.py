"""Produce portable per-input evidence for the R4 control and the R5 replay."""
from .reference import HERE,read,sha,write


def compact(path):
    data = read(path)
    journal = []
    for row in data["records"]:
        stripped = {k:row[k] for k in ("index","command","action","status","binding","actions_executed",
                                        "page","offered","actual_reported","original_before","original_after")}
        if "incidental_card" in row:
            stripped["incidental_card"] = row["incidental_card"]
        for phase in ("before","after"):
            if phase not in row:
                continue
            value = row[phase]
            stripped[phase] = dict(model_resources=value["model"]["resources"],original_resources=value["original"]["resources"],
                                   field_groups=len(value["original"]),differences=value["differences"])
            if row["index"] in (96,97,98,99,128,129):
                stripped[phase]["key_and_rewards"] = {side:{k:value[side].get(k) for k in ("keys","relics","rewards")} for side in ("model","original")}
        journal.append(stripped)
    return dict(source_sha256=sha(path), **{k:v for k,v in data.items() if k not in ("records","final")},
                final={k:data["final"][k] for k in ("resources","facade_page","done","lost","won")},records=journal)


def generate():
    out = HERE/"replay"
    for target in ("CONTROL","RESULT"):
        write(out/(target.lower()+"-receipts.json"),compact(out/(target+".json")))


if __name__ == "__main__":
    generate()
