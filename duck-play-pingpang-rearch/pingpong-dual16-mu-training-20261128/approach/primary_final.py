"""One final .416 search on three opened release-aligned main-course starts."""
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch
import hashlib
import numpy as np
from search import HERE,cp,material,read,save,SEED,BASES
from slope_entry import actions as gait_actions
OUT=HERE/'primary-final'
SEEDS=(15387848,15233602,15250319)
ENGINE=cp.transfer

def sim(row, fork=None, trace=None):
    conf=deepcopy(ENGINE.NS['spec']['params'])
    if row.get('settle') is not None:conf['settle_s']=row['settle']
    with patch.dict(ENGINE.NS,{'spec':{'params':conf}}),material('high'):
        return ENGINE.run('combined',row['seed'],row['scale'],actions=row['actions'],fork=fork,trace=trace)

def trial(r):
    out=sim(r)
    return dict(r,m=out['last_both_m'],s=out['seconds'],flat=out['flat_1m'],slope=out['slope_1m'],finish=out['finish_2p5'],tilt=out['max_tilt_deg'],why=out['reason'])

def task(job):
    r,tick,slot,group,adir,acts=job
    sim(r,dict(folder=adir,tick=tick,slot=slot,members=[(j,a) for j,a in enumerate(acts) if j%2==group]))
    return True

def order(r):
    return r['finish'],r['slope'],r['flat'],r['m'],-r['tilt']

def choose(rows,n):
    out=[]
    for r in sorted(rows,key=order,reverse=True):
        if any(q['seed']==r['seed'] and abs(q['m']-r['m'])<.0009 and abs(q['s']-r['s'])<.04 for q in out):continue
        out.append(r)
        if len(out)==n:break
    return out

def main():
    OUT.mkdir(exist_ok=True)
    low=HERE.parent/'low-route'; dirs={name:read(low/name) for name in ('best.json','prep-result.json','extension-best.json')}
    dirs['prep-result.json']=dirs['prep-result.json']['winner']
    sources={'empty':[],'teacher':read(BASES['record'])['actions'],'primary':read(HERE/'primary/result.json')['selected_actions'],
             'high-catch':read(HERE/'high-catch/result.json')['selected_actions']}
    sources.update({k:(sources['teacher'] if r.get('base')=='teacher' else [])+r['extra'] for k,r in dirs.items()})
    save(OUT/'sources.json',sources)
    save(OUT/'protocol.json',dict(mu=.416,seeds=SEEDS,track='combined',source='three opened developer seeds, human-specified after preceding experiments',scoring='physical simultaneous contact to valid gate; no extra body tilt filtering',new_starts=dict(start=17280000,count=128),actions='camera spread, support-phase movement and targeted paddle tilts; 12 adaptive stages maximum, selected from fresh-release pilot incl variable empty paddle settle and gait scale'))
    prep=[.54,.68,.82,.98,1.10,1.18,1.32,1.46,1.62,1.76]
    spec=ENGINE.NS['spec']['params']
    jobs=[dict(seed=s,settle=t,scale=k,actions=a,source=name) for s in SEEDS for t in [None,*prep] for k in [.83,1.,1.12,1.26] for name,a in sources.items() if name=='empty' or (t in (None,1.18) and k==1.)]
    with ProcessPoolExecutor(7) as pool:
        initial=list(pool.map(trial,jobs,chunksize=2))
        save(OUT/'initial.json',initial)
        top=[max((r for r in initial if r['seed']==s),key=order) for s in SEEDS]
        print('pilots',[(r['seed'],r['m'],r['settle'],r['scale']) for r in top],flush=True)
        best=max(top,key=order);beam=[*top,best];history=[]
        for layer in range(12):
            folder=OUT/f's{layer:02d}';folder.mkdir(exist_ok=True)
            parents=[];jobs=[]
            for slot,r in enumerate(beam):
                rng=np.random.default_rng(729110+layer*77+slot*193)
                tick=max(3,int(round(50*max(.06,r['s']-[.84,1.44,2.35,.48][(slot+layer)%4]))))
                acts=gait_actions(layer+70,slot)
                for j in range(1,11):
                    z=dict.fromkeys(('pitch','roll','damp','speed','neck','hip','lateral','yaw','span'),0.)
                    theta=(j-1)*np.pi/3+rng.uniform(-.45,.45);v=rng.uniform(.035,.14)
                    if j<=6:z.update(pitch=v*np.cos(theta),roll=v*np.sin(theta),speed=rng.uniform(-.12,.28),damp=rng.uniform(-.15,.5))
                    else:z.update(hip=.03*np.cos(theta),lateral=.03*np.sin(theta),yaw=rng.uniform(-.39,.39),speed=rng.uniform(-.33,.58),neck=rng.uniform(-.06,.06))
                    z['duration']=float(rng.choice([.22,.48,.78,1.2,1.8]));acts[j]=z
                parents.append((r,tick,slot,acts))
                jobs.extend((r,tick,slot,g,folder,acts) for g in range(2))
            list(pool.map(task,jobs))
            rows=[]; proofs=[]
            for r,tick,slot,acts in parents:
                vals=[read(folder/f'{slot}-{j:02}.json') for j in range(len(acts))]
                assert vals[0]['last_both_m']==r['m'] and len({v['fork_sha'] for v in vals})==1
                proofs.append(dict(seed=r['seed'],tick=tick,sha=vals[0]['fork_sha']))
                for a,v in zip(acts,vals):
                    assert v['torque_nm']<=.2000001
                    rows.append(dict(r,actions=r['actions']+([dict(tick=tick,**a)] if a else []),m=v['last_both_m'],s=v['seconds'],flat=v['flat_1m'],slope=v['slope_1m'],finish=v['finish_2p5'],tilt=v['max_tilt_deg'],why=v['reason']))
            allr=[*top,best,*beam,*rows];best=max(allr,key=order)
            top=[max((r for r in allr if r['seed']==s),key=order) for s in SEEDS]
            beam=([*top,*choose(allr,1)] if layer<4 else choose(allr,4))
            history.append(dict(layer=layer,branches=len(rows),top=[(r['seed'],r['m']) for r in top],proofs=proofs))
            save(OUT/'history.json',history);save(OUT/'winner.json',best);print('round',layer,history[-1]['top'],flush=True)
            if best['flat']:
                break
        out=sim(best,trace=OUT/'trajectory.npz')
        assert out['last_both_m']==best['m']
        save(OUT/'result.json',dict(seed=best['seed'],selected_actions=best['actions'],scale=best['scale'],settle=best['settle'],source=best['source'],result=out,materials=['high',.416],branches=sum(r['branches'] for r in history),pilots=len(initial),best_by_seed=top))
        if best['flat']:
            import json
            internal_hash=hashlib.sha256((OUT/'result.json').read_bytes()).hexdigest()
            save(OUT/'freeze.json',dict(sha=internal_hash,start=17280000,n=128))
            fresh=list(pool.map(trial,[dict(best,seed=s) for s in range(17280000,17280128)],chunksize=2))
            save(OUT/'fresh.json',dict(n=len(fresh),flat=sum(r['flat'] for r in fresh),slope=sum(r['slope'] for r in fresh),finish=sum(r['finish'] for r in fresh),max_m=max(r['m'] for r in fresh),rows=[{k:v for k,v in r.items() if k!='actions'} for r in fresh]))
if __name__=='__main__':main()
