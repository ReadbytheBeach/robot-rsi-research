"""Explore measured low-friction primary-course rollouts on previously opened natural seeds."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import csv
import hashlib
import json
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from material import cp,surface,SHORT,save
e=cp.transfer
KNOWN=SHORT/'training/enrichment/selected.json'
ARCHIVE=json.loads((SHORT/'replay/fixed-paced-seal.json').read_text())['actions']


def run(job):
    seed,base,scale,extra=job
    seq=(ARCHIVE if base=='teacher' else [])+extra
    with surface('low') as pairs:r=e.run('combined',seed,scale,actions=seq)
    assert all(pairs[name][1]==.224 for name in cp.NAMES) and r['torque_nm']<=.2000001
    return dict(seed=seed,base=base,scale=scale,extra=extra,flat=r['flat_1m'],slope=r['slope_1m'],finish=r['finish_2p5'],
                m=r['last_both_m'],s=r['seconds'],why=r['reason'],tilt=r['max_tilt_deg'],torque=r['torque_nm'])


def key(r):
    return (r['finish'],r['slope'],r['flat'],r['m'] if r['tilt']<29 else 0.)


def different(rows,n,distinct=False):
    chosen=[]
    for r in sorted(rows,key=key,reverse=True):
        if any(r['seed']==p['seed'] and (distinct or abs(r['m']-p['m'])<.0025) for p in chosen):continue
        chosen.append(r)
        if len(chosen)>=n:break
    return chosen


def pulse(r,rng,j,layer):
    # The timing is chosen offline on an opened prefix. Execution only reads the
    # previous camera estimate and the control clock, like the original actor.
    end=r['s']
    if j%5==0:lo,hi=.08,max(.16,.48*end)
    elif j%5 in (1,2):lo,hi=.30*end,.76*end
    else:lo,hi=.67*end,max(.68*end,end-.12)
    onset=float(rng.uniform(lo,hi))
    a=dict(tick=round(50*onset),duration=float(rng.choice([.22,.46,.86,1.35,2.,2.85,3.8])),
           neck=0.,yaw=0.,hip=0.,pitch=0.,roll=0.,lateral=0.,span=0.,damp=0.,speed=0.)
    if j%4 in (0,1):
        a['speed']=float(rng.uniform(-.18,.57));a['neck']=float(rng.uniform(-.045,.045));a['damp']=float(rng.uniform(-.15,.24))
    elif j%4==2:
        a['yaw']=float(rng.uniform(-.16,.16));a['span']=float(rng.uniform(-.075,.075));a['damp']=float(rng.uniform(-.3,.30))
    else:
        a['speed']=float(rng.uniform(-.26,.32));a['roll']=float(rng.uniform(-.055,.055));a['pitch']=float(rng.uniform(-.055,.055))
    return a


def main():
    seeds=json.loads(KNOWN.read_text())['seeds'];assert len(set(seeds))==len(seeds)==358
    configs=[('teacher',1.),('clear',1.),('clear',1.17)]
    save(HERE/'protocol.json',dict(seeds=seeds,source=str(KNOWN),seed_source_sha=hashlib.sha256(KNOWN.read_bytes()).hexdigest(),
       material=.224,track='combined',initial_arms=configs,beam='prefer real finish/slope/flat/last simultaneous valid distance. '
       'Keep 4 leading prefixes and 2 challenger seeds; after a local plateau revisit earlier control times. '
       'All starts were mined before this study. No selected start contributes to a population rate.'))
    with ProcessPoolExecutor(7) as pool:
        initial=list(pool.map(run,[(s,b,k,[]) for s in seeds for b,k in configs],chunksize=4))
        save(HERE/'initial.json',initial)
        leaders=different(initial,7,True)
        print('initial',[(r['seed'],r['m']) for r in leaders],flush=True)
        best=leaders[0];hist=[];beam=leaders[:6];retained=leaders.copy()
        for stage in range(18):
            jobs=[];rng=np.random.default_rng(4221080+stage)
            for r in beam:
                for j in range(12):
                    a=pulse(r,rng,j,stage)
                    extra=r['extra']+[a]
                    jobs.append((r['seed'],r['base'],r['scale'],extra))
            rows=list(pool.map(run,jobs,chunksize=3))
            new=sorted([*retained,*beam,*rows],key=key,reverse=True)
            retained=different(new,16);best=retained[0]
            if stage<5:
                beam=different(new,6,True)
            else:
                beam=different(new,4)
                for c in different(new,6,True):
                    if all(c['seed']!=v['seed'] for v in beam):beam.append(c)
                    if len(beam)==6:break
            hist.append(dict(stage=stage,n=len(rows),best_seed=best['seed'],m=best['m'],s=best['s'],seeds=len(set(q[0] for q in jobs))))
            save(HERE/'history.json',hist);save(HERE/'best.json',best)
            print(hist[-1],flush=True)
            if best['finish']:break
    extra=best['extra'];seq=(ARCHIVE if best['base']=='teacher' else [])+extra
    with surface('low') as pairs:
        solved=e.run('combined',best['seed'],best['scale'],actions=seq,trace=HERE/'best-low.npz')
        seed_base=next(r for r in initial if r['seed']==best['seed'] and r['base']==best['base'] and r['scale']==best['scale'])
        initial_schedule=ARCHIVE if best['base']=='teacher' else []
        before=e.run('combined',best['seed'],best['scale'],actions=initial_schedule,trace=HERE/'baseline-low.npz')
    assert solved['last_both_m']==best['m'] and before['last_both_m']==seed_base['m']
    first=min((a['tick'] for a in extra),default=0)
    with np.load(HERE/'best-low.npz') as a,np.load(HERE/'baseline-low.npz') as b:
        prefix=min(first,len(a['t'])-1,len(b['t'])-1)
        assert np.array_equal(a['qpos'][:prefix+1],b['qpos'][:prefix+1])
        sha=hashlib.sha256(a['qpos'][:prefix+1].tobytes()).hexdigest()
    save(HERE/'result.json',dict(natural_starts=len(seeds),conditional=True,initial_sims=len(initial),branches=sum(r['n'] for r in hist),
         best_initial=leaders[0],same_start_base=before,selected=solved,first_changed_tick=first,identical_prefix_last_tick=prefix,
         prefix_pose_sha=sha,gates=solved['gates'],material=.224))
    print('complete',solved,flush=True)


if __name__=='__main__':main()
