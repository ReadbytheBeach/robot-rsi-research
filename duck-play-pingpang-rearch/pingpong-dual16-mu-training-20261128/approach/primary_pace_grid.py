"""Companion pace comparison for the same three opened starts and .416 surface."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import numpy as np
from primary_final import OUT,SEEDS,trial,read,save,sim,choose,order
FOLDER=OUT/'fine-pace'

def main():
    FOLDER.mkdir(exist_ok=True)
    rows=read(OUT/'initial.json')
    src=[max((r for r in rows if r['seed']==s),key=order) for s in SEEDS]
    # The most recent retained branches are an additional, separately snapshotted schedule.
    r=read(OUT/'winner.json')
    src.append(r)
    save(FOLDER/'sources.json',src)
    scales=sorted(set([1.0,*np.arange(.96,1.0401,.001).round(4)]))
    save(FOLDER/'protocol.json',dict(mu=.416,scales=scales,seeds=SEEDS,course='combined',independent_seed_start=17280000,independent_count=128))
    with ProcessPoolExecutor(5) as pool:
        out=list(pool.map(trial,[dict(r,scale=float(v)) for r in src for v in scales],chunksize=3))
        save(FOLDER/'trials.json',[{k:v for k,v in a.items() if k!='actions'} for a in out])
        top=[max((r for r in out if r['seed']==s),key=order) for s in SEEDS]
        best=max(top,key=order)
        rr=sim(best,trace=FOLDER/'trajectory.npz')
        assert rr['last_both_m']==best['m']
        save(FOLDER/'result.json',dict(result=rr,seed=best['seed'],scale=best['scale'],settle=best['settle'],selected_actions=best['actions'],n=len(out),top=top))
        print([(r['seed'],r['m'],r['scale']) for r in top],flush=True)
        if best['flat']:
            save(FOLDER/'freeze.json',dict(sha=hashlib.sha256((FOLDER/'result.json').read_bytes()).hexdigest(),start=17280000,n=128))
            fresh=list(pool.map(trial,[dict(best,seed=s) for s in range(17280000,17280128)],chunksize=2))
            save(FOLDER/'fresh.json',dict(n=128,flat=sum(r['flat'] for r in fresh),slope=sum(r['slope'] for r in fresh),finish=sum(r['finish'] for r in fresh),max_m=max(r['m'] for r in fresh),rows=[{k:v for k,v in r.items() if k!='actions'} for r in fresh]))
if __name__=='__main__':main()
