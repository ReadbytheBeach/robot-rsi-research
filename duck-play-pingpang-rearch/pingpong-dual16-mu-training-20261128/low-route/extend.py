"""Extend a witnessed real trajectory by forking its full MuJoCo state before loss."""
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import argparse
import json
import numpy as np
import develop as d

@contextmanager
def physics(seed):
    spec=d.e.NS['spec']
    config=deepcopy(spec['params'])
    if 'settle' in seed:config['settle_s']=seed['settle']
    d.e.NS['spec']={'params':config}
    try:
        with d.surface('low') as pairs:yield pairs
    finally:d.e.NS['spec']=spec

def read(path):
    return json.loads(path.read_text())

def schedule(row):
    return (d.ARCHIVE if row.get('base')=='teacher' else [])+row['extra']

def branch(job):
    parent,folder,slot,group,tick,actions=job
    members=[(j,a) for j,a in enumerate(actions) if j%3==group]
    with physics(parent):
        d.e.run('combined',parent['seed'],parent['scale'],actions=schedule(parent),
                fork=dict(folder=folder,tick=tick,slot=slot,members=members))
    return 0

def replay(row,path=None):
    with physics(row):return d.e.run('combined',row['seed'],row['scale'],actions=schedule(row),trace=path)

def bank(rng):
    out=[None]
    for j in range(1,25):
        a=dict(duration=float(rng.choice([.22,.42,.72,1.1,1.65,2.3])),
               hip=0.,pitch=0.,roll=0.,damp=0.,span=0.,neck=0.,yaw=0.,lateral=0.,speed=0.)
        if j%4==0:
            a.update(speed=float(rng.uniform(-.27,.32)),damp=float(rng.uniform(-.22,.33)),neck=float(rng.uniform(-.05,.05)))
        elif j%4==1:
            a.update(style=str(rng.choice(['intercept','opening'])),direction=float(rng.uniform(-.10,.10)),tangent=float(rng.uniform(-.05,.05)),
                     memory=float(rng.uniform(-.1,.45)),relative=float(rng.uniform(-.40,.40)),yawphase=float(rng.uniform(-.16,.16)),
                     neckphase=float(rng.uniform(-.05,.05)),frequency=0.,speed=float(rng.uniform(-.22,.28)))
        elif j%4==2:
            a.update(style='gait',direction=float(rng.uniform(-.06,.06)),tangent=float(rng.uniform(-.07,.07)),
                     memory=float(rng.uniform(-.1,.40)),relative=float(rng.uniform(-.35,.35)),yawphase=float(rng.uniform(-.2,.2)),
                     neckphase=float(rng.uniform(-.08,.08)),frequency=0.,damp=float(rng.uniform(-.15,.32)))
        else:
            a.update(pitch=float(rng.uniform(-.08,.08)),roll=float(rng.uniform(-.08,.08)),span=float(rng.uniform(-.08,.08)),
                     neck=float(rng.uniform(-.04,.04)),speed=float(rng.uniform(-.18,.28)))
        out.append(a)
    return out

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--frozen-sources',action='store_true',help='Restore the exact development snapshot chosen during the initial run')
    arg=cli.parse_args()
    if arg.frozen_sources:
        candidates=read(d.HERE/'extension-source.json')['candidates']
    else:
        prepared=read(d.HERE/'prep-result.json')['winner']
        standard=read(d.HERE/'best.json')
        candidates=sorted([prepared,standard],key=d.key,reverse=True)
    beam=[candidates[0],candidates[0],candidates[1]]
    best=beam[0];history=[];stall=0
    folder=d.HERE/'state-forks';folder.mkdir(exist_ok=True)
    d.save(d.HERE/'extension-source.json',dict(candidates=candidates,mu=.224,track='combined',physics='fork full native MuJoCo at named control tick with unmodified latent stream; time and delayed observations at runtime'))
    with ProcessPoolExecutor(5) as pool:
        for layer in range(16):
            step=folder/f'{layer:02}';step.mkdir(exist_ok=True)
            rng=np.random.default_rng(342813+layer); ctx=[];jobs=[]
            for slot,parent in enumerate(beam):
                lookbacks=([.58,1.27,2.52] if not stall else [.94,1.93,3.96])
                tick=max(3,round(50*(parent['s']-lookbacks[slot])))
                actions=bank(rng);ctx.append((parent,tick,actions))
                jobs.extend((parent,step,slot,group,tick,actions) for group in range(3))
            list(pool.map(branch,jobs))
            nextrows=[];proofs=[]
            for slot,(parent,tick,actions) in enumerate(ctx):
                siblings=[read(step/f'{slot}-{j:02}.json') for j in range(len(actions))]
                assert len({r['fork_sha'] for r in siblings})==1 and siblings[0]['fork_sha'] is not None
                assert abs(siblings[0]['last_both_m']-parent['m'])<1e-12
                proofs.append(dict(slot=slot,seed=parent['seed'],tick=tick,sha=siblings[0]['fork_sha']))
                for i,r in enumerate(siblings):
                    assert r['torque_nm']<=.2000001
                    nextrows.append(dict(parent,extra=parent['extra']+([dict(actions[i],tick=tick)] if i else []),
                                      flat=r['flat_1m'],slope=r['slope_1m'],finish=r['finish_2p5'],m=r['last_both_m'],s=r['seconds'],
                                      why=r['reason'],tilt=r['max_tilt_deg'],torque=r['torque_nm']))
            ranked=sorted([best,*nextrows],key=d.key,reverse=True)
            previous=best['m'];best=ranked[0]
            beam=d.different(ranked,3)
            while len(beam)<3:beam.append(best)
            stall=0 if best['m']-previous>.003 else stall+1
            history.append(dict(layer=layer,branches=len(nextrows),best=best['m'],s=best['s'],proofs=proofs))
            print('extended',layer,best['seed'],best['m'],best['s'],flush=True)
            d.save(d.HERE/'extension-history.json',history)
            d.save(d.HERE/'extension-best.json',best)
            if best['finish'] or stall>=5:break
    final=replay(best,d.HERE/'extension-low.npz')
    assert final['last_both_m']==best['m']
    d.save(d.HERE/'extension-result.json',dict(initial=candidates,best=best,verified=final,branches=sum(h['branches'] for h in history)))

if __name__=='__main__':main()
