"""Limited development curriculum for high outward relative release velocity on the physical primary track."""
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'opening'))
import train_opening as t
import release_groups as groups

CUT=json.loads((t.HERE/'release-subgroups.json').read_text())['historical_cutoffs_mm_s'][-1]
def store(name,v):
    p=HERE/name
    tmp=p.with_suffix('.part')
    tmp.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(p)

def seeds(first,n,hard):
    items=[];s=first
    while len(items)<n:
        pos,vel,mu=groups.release(s)
        value=groups.features(pos,vel,mu)['separation_rate_mm_s']
        if not hard or value>CUT:items.append(dict(seed=s,offline_release_radial_mm_s=value))
        s+=1
    return items

def proposals():
    rng=np.random.default_rng(51637);members={}
    for i in range(32):
        family=['neck_roll','cross_tilt','reversal','first_step'][i%4]
        members[f'{family}_{i:02d}']=dict(family=family,duration=float(rng.choice([.18,.26,.34,.42,.50])),
            gate=float(rng.choice([.014,.023,.033,.040])),onset=float(rng.choice([0.,.02,.06,.10])),
            neck=float(rng.uniform(-.15,.15)),yaw=float(rng.uniform(-.29,.29)),
            tilt=float(rng.uniform(-.18,.18)),speed=float(rng.uniform(.09,.64)),intercept=float(rng.uniform(.06,.28)),
            orientation=float(rng.choice([-1.,1.])))
    return members

def run(seed,policy,params=None):
    # Release truth is intentionally absent in this callable.
    p=params
    state={'gate':0.,'boost':0.,'onset':None,'peak':0.}
    baseline=t.Opening.update
    control=t.actors.controller
    def update(actor,bc):
        if actor.tick==bc.tick:return
        if 'nom' in state:
            actor.tilt[:],actor.requests[:],actor.speed=state['nom']
        baseline(actor,bc)
        state['nom']=(actor.tilt.copy(),actor.requests.copy(),actor.speed)
        if p is None:return
        at=.02*bc.tick
        state['boost']=0.
        if at>.5 or at<p['onset'] or at>p['duration']:return
        z=np.array([ch.measurements[0] for ch in bc.channels])
        delta=z[1,:2]-z[0,:2];span=max(.004,np.linalg.norm(delta));axis=delta/span
        dv=z[1,2:]-z[0,2:];rad=float(dv@axis)
        if 'launch_gate' not in state:
            state['launch_gate']=float(np.clip((rad-p['gate'])/.023,0.,1.))
        g=state['launch_gate']
        if not g:return
        tangent=np.array([-axis[1],axis[0]])
        c=(at-p['onset']+.02)/max(.02,p['duration']-p['onset']+.02)
        amp=g*np.sin(np.pi*np.clip(c,0.,1.))
        if abs(amp)<=1.e-8:return
        if state['onset'] is None:state['onset']=at
        state['peak']=max(state['peak'],amp)
        style=p['family']
        zpos=z[:,:2]+p['intercept']*z[:,2:]
        who=np.linalg.norm(zpos[1])-np.linalg.norm(zpos[0])
        side=np.tanh(who/.009)
        ctr=np.mean(zpos,axis=0)
        if style=='neck_roll':
            yaw=p['yaw']*np.sign(axis[0]*axis[1]+.00001);neck=p['neck']*p['orientation']
            lean=-1.4*ctr;boost=.35*p['speed']
        elif style=='cross_tilt':
            lean=p['tilt']*axis*side-.75*ctr
            yaw=p['yaw']*side;neck=p['neck']*abs(side);boost=0.
        elif style=='reversal':
            sign=1. if c<.54 else -1.
            lean=sign*(p['tilt']*tangent*p['orientation']-.6*ctr)
            yaw=sign*p['yaw']*p['orientation'];neck=sign*p['neck'];boost=p['speed']*(1. if c<.54 else .15)
        else:
            yaw=p['yaw']*np.tanh(axis[1]*rad/.04)
            neck=p['neck'];lean=-1.55*ctr+p['tilt']*axis*side;boost=p['speed']
        actor.tilt[:]=np.clip(actor.tilt+amp*lean,-.24,.24)
        actor.requests[:]=np.clip(actor.requests+amp*np.array([yaw,neck]),[-.35,-.17],[.35,.17])
        state['boost']=float(amp*boost)
    @contextmanager
    def early_controller(*args,**kwargs):
        with control(*args,**kwargs) as mon:
            old=t.actors.locomotion.Locomotion.control
            def drive(walk,data,speed):
                bc=mon['live']
                if bc is not None and data is bc.d and state['boost']>0:
                    speed=max(speed,state['boost'])
                return old(walk,data,speed)
            with patch.object(t.actors.locomotion.Locomotion,'control',drive):yield mon
    with patch.object(t.Opening,'update',update),patch.object(t.actors,'controller',early_controller):
        r=t.run_seed(seed,'high','phase_08')
    assert r['mu_a']==r['mu_b']==.416 and r['torque']<=.20000001
    return dict(r,arm=policy,trigger_s=state['onset'],peak=state['peak'])

def job(job):return run(*job)

def batch(pool,names,cohorts,bank):
    jobs=[(i['seed'],n,bank[n]) for cohort in cohorts.values() for i in cohort for n in names]
    return list(pool.map(job,jobs,chunksize=2))

def summary(rr):
    return dict(n=len(rr),**{k:sum(r[k] for r in rr) for k in ('both2','qtr','flat','slope','finish')},
                mean_m=float(np.mean([r['m'] for r in rr])),max_m=max(r['m'] for r in rr),
                mean_s=float(np.mean([r['t'] for r in rr])),triggered=sum(r['trigger_s'] is not None for r in rr))

def score(rows,n):
    rr=[r for r in rows if r['arm']==n]
    return sum(5*r['flat']+2*r['qtr']+r['both2']+.12*min(2.,r['t'])+.8*r['m'] for r in rr)/len(rr)

def main():
    started=time.monotonic();bank={'phase_08':None,**proposals()}
    history=seeds(17561000,20,True);select=seeds(17562000,48,True)
    ordinary=seeds(17565000,96,False);hard=seeds(17564000,80,True)
    cohorts=dict(hard=hard,ordinary=ordinary)
    ids=[r['seed'] for q in (history,select,ordinary,hard) for r in q];assert len(ids)==len(set(ids))
    store('protocol.json',dict(material=.416,control_hz=50,track='combined',budget='32 candidates x 20; top 5 x 48; independent 80 conditioned and 96 unfiltered, all paired with phase_08; single pass',
       threshold_mm_s=CUT,curriculum=history,selection=select,hard=hard,ordinary=ordinary,bank=bank,
       hard_definition='archived quartile from 768 prior starts; reconstruct natural physical release only for offline cohort selection, not controller input',
       objective='mean(5 flat +2 quarter + both2 + .12*min(t,2)+.8*last_both_m); freeze best novel intervention even if baseline ahead; one dual-cohort test',
       source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    with ProcessPoolExecutor(7) as pool:
        rows=batch(pool,bank,dict(hard=history),bank);store('screen.json',rows)
        chosen=sorted((n for n in bank if n!='phase_08'),key=lambda n:score(rows,n),reverse=True)[:5]
        print('screen',chosen,round(time.monotonic()-started,1),flush=True)
        dev=batch(pool,['phase_08',*chosen],dict(hard=select),bank);store('select.json',dev)
        winner=max(chosen,key=lambda n:score(dev,n))
        sig=hashlib.sha256(json.dumps(bank[winner],sort_keys=True).encode()).hexdigest()
        store('frozen.json',dict(winner=winner,parameters=bank[winner],parameter_sha=sig,scores={n:score(dev,n) for n in ['phase_08',*chosen]}))
        print('frozen',winner,round(time.monotonic()-started,1),flush=True)
        held=batch(pool,['phase_08',winner],cohorts,bank);store('paired-holdout.json',held)
    metrics={}
    for topic,cohort in cohorts.items():
        selected={i['seed'] for i in cohort}
        metrics[topic]={}
        for name in ['phase_08',winner]:
            rr=[r for r in held if r['arm']==name and r['seed'] in selected]
            assert set(r['seed'] for r in rr)==selected and len(rr)==len(selected)
            metrics[topic][name]=summary(rr)
        pairs={name:{r['seed']:r for r in held if r['arm']==name and r['seed'] in selected} for name in ['phase_08',winner]}
        metrics[topic]['paired']={}
        for k in ('both2','qtr','flat'):
            pairs0,pairs1=pairs['phase_08'],pairs[winner]
            metrics[topic]['paired'][k]=dict(gain=sum((not pairs0[s][k]) and pairs1[s][k] for s in selected),
                                        loss=sum(pairs0[s][k] and (not pairs1[s][k]) for s in selected))
    store('validation.json',dict(results=metrics,elapsed_s=time.monotonic()-started))
    print(metrics,round(time.monotonic()-started,1),flush=True)

if __name__=='__main__':main()
