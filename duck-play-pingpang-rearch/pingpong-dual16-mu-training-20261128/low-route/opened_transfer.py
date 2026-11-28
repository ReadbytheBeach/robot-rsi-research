"""Test transfer within the already opened seed archive. This is not a population acceptance set."""
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import json
import numpy as np
import develop as d
import extend as e

def attempt(job):
    seed,r,skip=job
    row=dict(r,seed=seed)
    if skip:row['extra']=[]
    measured=e.replay(row)
    return dict(seed=seed,no_added_actions=skip,meters=measured['last_both_m'],flat=measured['flat_1m'],grade=measured['slope_1m'],finish=measured['finish_2p5'])

def main():
    name='prep-result.json';r=e.read(d.HERE/name)['winner']
    archive=e.read(d.KNOWN)['seeds'];seen=set(e.read(d.HERE/'prep-protocol.json')['seeds'])
    subset=np.random.default_rng(822003).choice(sorted(set(archive)-seen),size=96,replace=False).tolist()
    d.save(d.HERE/'opened-transfer-protocol.json',dict(seeds=subset,excluded=sorted(seen),schedule=name,cohort='96 of 358 mined natural IDs excluding 18 used in preparation training; all are previously opened development IDs and not acceptance trials'))
    jobs=[(s,r,skip) for s in subset for skip in (True,False)]
    with ProcessPoolExecutor(3) as pool:rows=list(pool.map(attempt,jobs,chunksize=3))
    d.save(d.HERE/'opened-transfer.json',rows)
    for skip in (True,False):
        group=[v for v in rows if v['no_added_actions']==skip]
        print(skip,len(group),sum(v['flat'] for v in group),max(v['meters'] for v in group),sum(v['meters'] for v in group)/len(group))
if __name__=='__main__':main()
