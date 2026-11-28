"""Render measured uphill state and plate views; preserve original clock."""
import argparse
import hashlib
import json
import subprocess
import sys
from unittest.mock import patch
from high_slope import HERE, OLD, run
sys.path.insert(0,str(OLD/'media'))
import film

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--selection',default='best.json');cli.add_argument('--out',default='high-slope')
    a=cli.parse_args();chosen=json.loads((HERE/a.selection).read_text())
    trace=HERE/(a.out+'.npz');dest=HERE/(a.out+'-replay.mp4')
    proof=run(chosen['config'],trace=trace);r=proof['row']
    assert r==chosen['row'] and proof['mu']==[.416,.416]
    label='独立缓坡 · 高滑动摩擦 0.416 · 双球'+('到站并停车' if r['success'] else '过一米' if r['slope_1m'] else '最远有效里程')
    with patch.object(film,'ROOT',HERE):film.encode(trace,dest,label,rate=25.)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(dest),'-f','null','-'],check=True)
    info=dict(mu=proof['mu'],row=r,source=a.selection,trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
              video_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    (HERE/(a.out+'-proof.json')).write_text(json.dumps(info,indent=2)+'\n')
    print(dest.name,r['last_both_m'],r['success'],flush=True)

if __name__=='__main__':main()
