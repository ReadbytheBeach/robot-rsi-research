"""Use the existing short course and change only the two sphere–paddle sliding pairs."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import json
import sys

HERE=Path(__file__).resolve().parent
PILOT=HERE.parent/'pingpong-dual16-mu-pilot-20261128'
SHORT=HERE.parent/'pingpong-dual16-short-20261128'
sys.path.insert(0,str(PILOT))
import contact_pairs as cp
sys.path.insert(0,str(SHORT/'training'))
import study
import actors
import short_track

RECIPE=dict(mode='fixed',cruise=.44,wait=.18,ramp=.44)


def save(path, data):
    tmp=path.with_suffix('.part')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


@contextmanager
def surface(name):
    if name=='wide':
        with cp.surface('wide') as info:
            yield info
    else:
        mu={'high':.416,'nominal':.32,'low':.224,'record':cp.HISTORIC}[name]
        with patch.object(cp,'HISTORIC',mu),cp.surface('historic_fixed') as info:
            yield info
