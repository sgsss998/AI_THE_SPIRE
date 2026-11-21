"""Read the intrinsic Split marker from existing publicly encoded, living monster slots."""
from experiments.ordinary_targeting193.session import MONSTERS,rows

SPLITTERS=frozenset(MONSTERS[name]+1 for name in ('SLIME_BOSS','ACID_SLIME_L','SPIKE_SLIME_L'))
KNOWN=frozenset(i+1 for name,i in MONSTERS.items() if name!='INVALID')

def split_markers(vector):
    """True/False for known living enemies, None for noncombat, missing or dead slots."""
    if len(vector)<1253:raise ValueError('Monster rows are incomplete')
    if not vector[7]:return (None,)*5
    return tuple(r[0] in SPLITTERS if r[0] in KNOWN and r[1]>0 and tuple(r[4:7])==(0,0,1) else None
                 for r in rows(vector))
