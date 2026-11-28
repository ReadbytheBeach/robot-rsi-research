"""Audit a higher-tilt continuation under the same unmodified course scorer and original motor cap."""
from unittest.mock import patch
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import catch
import slope_entry as se
from search import HERE,SEED,read,save,simulate
OUT=HERE/'slope-entry-tilt'


def recover():
    observed=[]
    original=catch.key
    def ranking(row):
        if 'actions' in row:observed.append(row)
        return original(row)
    class CachedForks:
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def map(self,fn,jobs):
            for _,_,_,fork,_ in jobs:
                for i,_ in fork['members']:
                    assert (fork['folder']/f'{fork["slot"]}-{i:02d}.json').is_file()
            return []
    def rerun(job):
        mode,seed,s,branch,trace=job
        return simulate((mode,seed,s,branch,None))
    with patch.object(catch,'ProcessPoolExecutor',CachedForks),patch.object(catch,'key',ranking),patch.object(catch,'save',lambda *a:None),patch.object(catch,'simulate',rerun):
        catch.main()
    best=max(observed,key=lambda r:r['last_both_m'])
    rr=simulate(('high',SEED,best['actions'],None,None))
    assert rr['last_both_m']==best['last_both_m']
    return best


def physical(row):
    return row['finish_2p5'],row['slope_1m'],row['last']['safe_slope_m'],row['last_both_m'],-row['max_tilt_deg']


def retain(rows,target,count):
    keep=[max(rows,key=physical)]
    eligible=[(r,se.probe(r,target)) for r in rows]
    eligible=[(r,p[1]) for r,p in eligible if p is not None and abs(p[1][0]-target)<.09]
    for j in range(3):
        def desired(q):
            r,p=q
            m=.055-p[1];fore=.055-p[6];outward=max(0.,p[3])
            if j==0:return .6*m+fore-.38*outward
            if j==1:return m+fore-.65*p[3]-.35*p[2]
            return .5*m+fore-.18*outward+.10*r['last_both_m']-.0017*r['max_tilt_deg']
        for r,_ in sorted(eligible,key=desired,reverse=True):
            if all(abs(r['last_both_m']-k['last_both_m'])>.0008 for k in keep):
                keep.append(r);break
    return keep


def main():
    OUT.mkdir(exist_ok=True)
    if not (OUT/'sources.json').exists():
        late=recover()
        safe=read(HERE/'high-catch/result.json')['selected_actions']
        save(OUT/'sources.json',[late['actions'],safe,late['actions'],safe])
        save(OUT/'source-audit.json',{k:late[k] for k in ('gates','last_both_m','seconds','max_tilt_deg','torque_nm','last')})
    with patch.object(se,'OUT',OUT),patch.object(se,'order',physical),patch.object(se,'alternatives',retain),patch.object(se,'DISTANCES',[.70,.77,.84,.90,.95,1.00]):
        se.main()
    # Record the constraint actually used in this deliberate comparison.
    protocol=read(OUT/'protocol.json')
    protocol['keep']='Original task scorer and actuator limits throughout. No extra 29-degree development preference. Separate from the low-tilt search; compare achieved distance with maximum tilt.'
    save(OUT/'protocol.json',protocol)


if __name__=='__main__':main()
