"""Verify physical gate metadata and encode the frozen real rollouts at normal speed."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import numpy as np
import develop as d

sys.path.insert(0,str(d.SHORT/'media'))
import film

def render(trace,output):
    meta=json.loads(trace.with_suffix('.json').read_text())
    assert meta['track']=='combined' and meta['flat_1m']
    with np.load(trace) as z:
        for name,gate in meta['gates'].items():
            i=np.flatnonzero(np.isclose(z['t'],gate['t'],rtol=0,atol=1e-8))
            assert len(i)==1 and all(z['ball_contacts'][i[0]])
    with patch.object(film,'ROOT',d.HERE):
        film.encode(trace,output,'低摩擦主赛道 · 双球一米开发回放',rate=25.)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True)
    print(output,meta['gates'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('trace',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    render(args.trace.resolve(),args.output.resolve())
