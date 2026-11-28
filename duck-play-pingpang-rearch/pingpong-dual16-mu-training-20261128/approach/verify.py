"""Freeze the opened-state recipes, then compare them to the untouched teacher from release."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import numpy as np
from search import HERE,SHORT,BASES,MATERIAL,SEED,read,run,save


def job(x):
    mode,track,seed,name,actions=x
    r=run(track,seed,actions,mode)
    return {k:r[k] for k in ('seed','last_both_m','seconds','reason','flat_1m','slope_1m','finish_2p5','max_tilt_deg','torque_nm')} | dict(material=mode,track=track,policy=name)


def freeze(mode):
    folder=HERE/mode;res=read(folder/'result.json')
    material='record' if mode.startswith('record') else 'high'
    actions=res['selected_actions'];l=f'{mode}-frozen.json'
    save(HERE/l,dict(actions=actions,mu=MATERIAL[material],development_seed=res.get('seed',res['result']['seed']),source=str(folder/'result.json'),sha256=hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()))
    return actions


def verify(mode):
    protocol=read(HERE/'blind-protocol.json')
    actions=freeze(mode)
    material='record' if mode.startswith('record') else 'high'
    seed0=protocol['start']; n=protocol['count']
    controls={'teacher':read(BASES['record'])['actions'],'trained':actions}
    rows=[]
    with ProcessPoolExecutor(4) as pool:
        for track in ('combined',) if mode.startswith('primary') else ('combined','fixed'):
            tasks=[(material,track,seed,name,ac) for seed in range(seed0,seed0+n) for name,ac in controls.items()]
            rows.extend(pool.map(job,tasks,chunksize=3))
    assert len(rows) in (2*n,4*n) and max(r['torque_nm'] for r in rows)<=.20000001
    folder=HERE/mode
    with (folder/'fresh.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    scores={}
    for track in sorted(set(r['track'] for r in rows)):
        scores[track]={}
        for name in controls:
            selected=[r for r in rows if r['track']==track and r['policy']==name]
            scores[track][name]=dict(n=n,flat=sum(r['flat_1m'] for r in selected),
               slope=sum(r['slope_1m'] for r in selected),finished=sum(r['finish_2p5'] for r in selected),
               half=sum(r['last_both_m']>=.5 for r in selected),survived_2s=sum(r['seconds']>2 for r in selected),
               mean_m=float(np.mean([r['last_both_m'] for r in selected])),max_m=max(r['last_both_m'] for r in selected))
    save(folder/'fresh.json',scores)
    print(mode,scores,flush=True)


def film(mode):
    sys.path.insert(0,str(SHORT/'media'))
    import film as ff
    folder=HERE/mode
    kind='high' if mode.startswith('slope-entry') else mode.split('-')[0]
    title={'high':'最高摩擦 0.416 · 从释放重跑入坡动作','record':'纪录摩擦 0.364467 · 提前调节双球分离','primary':'最高摩擦 0.416 · 释放对齐的主赛道'}[kind]
    with patch.object(ff,'ROOT',HERE):
        ff.encode(folder/'trajectory.npz', folder/'original-speed.mp4', title, fixed_grid=(kind!='primary'),rate=25.)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(folder/'original-speed.mp4'),'-f','null','-'],check=True)


if __name__=='__main__':
    kinds=('high','record','primary')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=(*kinds, 'high-catch', 'slope-entry', 'slope-entry-tilt', *(s+'-continuation' for s in kinds)));parser.add_argument('--film',action='store_true')
    args=parser.parse_args()
    if args.film:film(args.mode)
    else:verify(args.mode)
