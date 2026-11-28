"""Local multi-material training for a previously parked release on the isolated 1° slope."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'slope'))
import high_slope as hs
from sweep import ARMS
TRAIN=[.414,.4145,.415,.4155,.416]
SELECT=[.41422,.414747,.415248,.415765]
HOLD=np.random.default_rng(997321116).uniform(.414,.416,48).tolist()
BASE=hs.read(hs.HERE/'sprint-best.json')['config']
ALT=hs.read(hs.HERE/'best.json')['config']

def save(name,obj):
    p=HERE/name;q=p.with_suffix('.tmp');q.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');q.replace(p)

def run(job,trace=None):
    cfg,mu=job
    with patch.dict(ARMS,{'target':mu}):proof=hs.run(cfg,'target',trace=trace)
    r=proof['row'];assert proof['mu']==[mu,mu] and r['torque_nm']<=.2000001
    return dict(mu=mu,park=r['success'],gate=r['slope_1m'],held=r['stable_finish_s'],m=r['last_both_m'],t=r['seconds'],why=r['reason'],gates=r['gates'],tilt=r['max_tilt_deg'],torque=r['torque_nm'])

def summary(rows):
    m=[r['m'] for r in rows]
    return dict(park=sum(r['park'] for r in rows),gate=sum(r['gate'] for r in rows),min_m=min(m),p20_m=float(np.quantile(m,.2)),mean_safe=float(np.mean(np.minimum(m,1.))),mean_hold=float(np.mean([min(1.,r['held']) for r in rows])))

def key(candidate):
    r=candidate['summary']
    return (r['park'],r['gate'],r['min_m'],r['p20_m'],r['mean_hold'],r['mean_safe'])

def evaluate(pool,cfgs,mats):
    jobs=[(c,mu) for c in cfgs for mu in mats]; runs=list(pool.map(run,jobs,chunksize=1))
    return [dict(config=c,rows=(rr:=runs[j*len(mats):(j+1)*len(mats)]),summary=summary(rr)) for j,c in enumerate(cfgs)]

def proposals(parent,layer,slot):
    rng=np.random.default_rng(772649+layer*711+slot*317)
    c=parent['config']
    out=[]
    for j in range(15):
        p=deepcopy(c);choice=(j+layer)%5
        if choice==0:
            p['scale']+=float(rng.choice([-1,1])*rng.choice([.00008,.00023,.00054,.0012,.002,.0045,.008,.019]))
        elif choice==1:
            buf,ramp,wait=p['brake']
            p['brake']=[float(np.clip(buf+rng.uniform(-.018,.018),-.065,.05)),float(np.clip(ramp+rng.uniform(-.065,.11),.02,.50)),float(np.clip(wait+rng.choice([0.,-.06,.04,.12,.24]),0.,.5))]
        elif choice==2:
            act=p['actions'][rng.integers(len(p['actions']))]
            if rng.random()<.5:act['tick']=int(act['tick']+rng.choice([-4,-2,-1,1,2,4]))
            for name in ['speed','neck','pitch','roll','damp']:
                if act[name]:act[name]*=float(1.+rng.uniform(-.09,.09))
        elif choice==3:
            act=p['actions'][rng.integers(len(p['actions']))]
            act['duration']=max(.04,act['duration']+float(rng.choice([-.08,-.04,-.02,.02,.04,.08])))
        else:
            worst=min(parent['rows'],key=lambda r:r['m'])
            t=float(np.clip(worst['t']-rng.uniform(.3,2.9),.18,9.6))
            a=dict.fromkeys(('speed','neck','pitch','roll','damp','hip','lateral','span','yaw'),0.)
            a.update(tick=round(t/.02),duration=float(rng.choice([.14,.24,.45,.72])),speed=rng.uniform(-.042,.042),neck=rng.uniform(-.007,.007),pitch=rng.uniform(-.012,.012),roll=rng.uniform(-.012,.012))
            p['actions'].append(a)
        out.append(p)
    return out

def diverse(rows,n):
    keep=[]
    for z in sorted(rows,key=key,reverse=True):
        vec=[(round(r['m'],6),r['park']) for r in z['rows']]
        if any(old==vec for old,_ in keep):continue
        keep.append((vec,z))
        if len(keep)==n:break
    return [z for _,z in keep]

def main():
    assert all(BASE[k]==ALT[k] for k in ('seed','values','mode','scale'))
    assert len(set([*TRAIN,*SELECT,*HOLD]))==57
    save('protocol.json',dict(course='isolated 1 degree incline, both touching at the gate and one second stable parking',initial_seed=BASE['seed'],training=TRAIN,selection=SELECT,holdout_mode='48 predeclared iid uniform [.414,.416] coefficients; random draw controls only the coefficient; same coefficient for both ball-face contacts; same previously opened release in every trial.',independent_materials=HOLD,rng=997321116,maximum_train=2+3*2*15,maximum_selection=7,search='3 CEM-style local generations on 5 fixed values, 2 retained configurations × 15 small changes; frozen configuration selected in pooled 9 development materials and tested once',rank=['park count','gate count','minimum last physical dual contact distance','p20 distance','mean held','capped mean distance'],baseline='slope/sprint-best.json'))
    with ProcessPoolExecutor(9) as pool:
        prev=evaluate(pool,[BASE,ALT],TRAIN);all_rows=prev.copy(); rounds=[]
        save('baseline-development.json',prev)
        for level in range(3):
            beam=diverse(all_rows,2); cfgs=[c for i,src in enumerate(beam) for c in proposals(src,level,i)]
            seen={json.dumps(z['config'],sort_keys=True) for z in all_rows}
            unique=[]
            for c in cfgs:
                h=json.dumps(c,sort_keys=True)
                if h not in seen:seen.add(h);unique.append(c)
            new=evaluate(pool,unique,TRAIN);all_rows+=new;best=max(all_rows,key=key)
            rounds.append(dict(level=level,n=len(new),best=best['summary']))
            save(f'round-{level}.json',new);save('progress.json',rounds)
            print(level,len(new),best['summary'],flush=True)
        shortlist=diverse(all_rows,5)
        for b in prev:
            if b['config'] not in [z['config'] for z in shortlist]:shortlist.append(b)
        extra=evaluate(pool,[z['config'] for z in shortlist],SELECT)
        pooled=[]
        for a,b in zip(shortlist,extra):
            rows=a['rows']+b['rows'];pooled.append(dict(config=a['config'],rows=rows,summary=summary(rows)))
        save('development-finalists.json',pooled)
        winner=max(pooled,key=key)
        frozen={'config':winner['config'],'summary':winner['summary'],'baseline':BASE,'values':TRAIN+SELECT}
        save('frozen.json',frozen)
        rows=evaluate(pool,[BASE,winner['config']],HOLD)
        save('unseen-material-paired.json',rows)
        old,new=rows
        diffs=[b['m']-a['m'] for a,b in zip(old['rows'],new['rows'])]
        park_wins=[i for i,(a,b) in enumerate(zip(old['rows'],new['rows'])) if b['park'] and not a['park']]
        park_losses=[i for i,(a,b) in enumerate(zip(old['rows'],new['rows'])) if a['park'] and not b['park']]
        report=dict(n_materials=len(HOLD),release_seed=BASE['seed'],counts=dict(candidates=len(all_rows),train_rollouts=len(all_rows)*len(TRAIN),selection_rollouts=len(pooled)*len(SELECT),blind_rollouts=2*len(HOLD)),developed=winner['summary'],baseline_development=next(x['summary'] for x in pooled if x['config']==BASE),baseline=old['summary'],trained=new['summary'],paired_gain=park_wins,paired_loss=park_losses,median_distance_change=float(np.median(diffs)),freeze_sha=hashlib.sha256((HERE/'frozen.json').read_bytes()).hexdigest())
        save('result.json',report);print(report,flush=True)
        # Independent replay and visible evidence; preferentially show a newly parked blind coefficient.
        both_else=[i for i,v in enumerate(new['rows']) if v['park']]
        i=park_wins[0] if park_wins else both_else[0] if both_else else int(np.argmax(diffs))
        chosen=run((winner['config'],HOLD[i]),trace=HERE/'paired-trained.npz')
        original=run((BASE,HOLD[i]),trace=HERE/'paired-baseline.npz')
        assert chosen==new['rows'][i] and original==old['rows'][i]
        save('example.json',dict(material=HOLD[i],paired_blind_index=i,baseline=original,trained=chosen))
if __name__=='__main__':main()
