"""Tune a causal double-ball controller on the release-aligned 2.5 m physical track."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import csv
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
EXPS = HERE.parents[1]
PILOT = EXPS/'pingpong-dual16-mu-pilot-20261128'
SHORT = EXPS/'pingpong-dual16-short-20261128'
sys.path[:0]=[str(SHORT/'training'), str(SHORT),str(PILOT)]
import study
import actors
import short_track
import contact_pairs as cp

RECIPE = dict(mode='fixed',cruise=.44,ramp=.44,wait=.18)


def write(name,data):
    path=HERE/name
    tmp=path.with_suffix('.part')
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    tmp.replace(path)


def bank():
    controls={'medium':None}
    rng=np.random.default_rng(91627)
    for i in range(40):
        family=('phase','intercept','turn','pressure')[i%4]
        controls[f'{family}_{i:02d}']=dict(family=family,
            horizon=float(rng.choice([.12,.20,.32,.46])),
            duration=float(rng.choice([1.4,2.,3.2,6.])),
            speed=float(rng.uniform(-.36,.40)),
            yaw=float(rng.uniform(-.32,.32)),
            tilt=float(rng.uniform(-.14,.14)),
            centre=float(rng.uniform(-1.7,1.7)),
            neck=float(rng.uniform(-.065,.065)))
    return controls


@contextmanager
def material_surface(material):
    if material=='wide':
        with cp.surface('wide') as info:yield info
    else:
        value={'high':.416,'nominal':.32}.get(material,material)
        if not isinstance(value,(float,int)):raise ValueError(material)
        with patch.object(cp,'HISTORIC',float(value)),cp.surface('historic_fixed') as info:
            yield info


class Opening:
    def __init__(self,policy):
        self.policy=policy
        self.tick=None
        self.active=0
        self.both2=False
        self.first_quarter=None
        self.first_half=None
        self.both_m=0.
        self.obs=[0.,0.]
        self.delayed=None
        self.requests=np.zeros(2)
        self.tilt=np.zeros(2)
        self.speed=1.

    def update(self,bc):
        if self.policy is None or self.tick==bc.tick:return
        self.tick=bc.tick
        p=self.policy
        t=.02*bc.tick
        envelope=np.clip((p['duration']-t)/.18,0.,1.)
        if envelope==0:
            self.speed=1.;self.tilt[:]=0;self.requests[:]=0
            return
        channels=bc.channels
        z=np.array([c.measurements[0] for c in channels])
        pos,vel=z[:,:2],z[:,2:]
        delta=pos[1]-pos[0]; sep=max(float(np.linalg.norm(delta)),.005)
        axis=delta/sep
        tangent=np.array([-axis[1],axis[0]])
        dv=vel[1]-vel[0]
        radial=float(dv@axis)
        transverse=float(dv@tangent)
        centre=np.mean(pos+p['horizon']*vel,axis=0)
        radial_risk=np.clip((sep+p['horizon']*radial-.040)/.055,0.,1.)
        projected=pos+p['horizon']*vel
        edge_risk=np.clip((max(np.linalg.norm(projected,axis=1))-.030)/.035,0.,1.)
        risk=max(radial_risk,edge_risk)
        # Relative foot height is determined by measured joints and body attitude.
        feet=[bc.m.geom(n+'_foot_collision').id for n in ('left','right')]
        phase=np.tanh((bc.d.geom_xpos[feet[0],2]-bc.d.geom_xpos[feet[1],2])/.009)
        closing=np.clip(-float(delta@dv)/max(.00001,float(dv@dv)),0.,p['horizon'])
        near=np.exp(-((np.linalg.norm(delta+closing*dv)-.016)/.021)**2)
        if p['family']=='phase':
            signal=phase
            direction=tangent*phase
        elif p['family']=='intercept':
            signal=near*np.tanh(transverse/.034) if radial<0 else 0.
            direction=tangent*signal
        elif p['family']=='turn':
            signal=np.tanh(transverse/(sep*2.3))*np.tanh(radial/.045)
            direction=tangent*signal
        else:
            weights=np.linalg.norm(projected,axis=1)
            signal=np.tanh((weights[1]-weights[0])/.012)
            direction=axis*signal
        risk*=envelope
        self.active+=int(risk>.05)
        target=1.+risk*p['speed']
        self.speed+=np.clip(target-self.speed,-.13,.13)
        command=risk*(p['tilt']*direction-p['centre']*centre)
        self.tilt+=np.clip(np.clip(command,-.15,.15)-self.tilt,-.035,.035)
        self.requests+=np.clip(risk*np.array([p['yaw']*signal,p['neck']*phase])-self.requests,-.04,.04)

    def joint_command(self,ch):
        if self.delayed is None:
            self.delayed=deque([np.zeros(2)]*(1+ch.act_lag),maxlen=1+ch.act_lag)
            self.joints=np.array([ch.m.actuator(n).id for n in ('head_yaw','neck_pitch')])
            self.bounds=ch.m.jnt_range[ch.m.actuator_trnid[self.joints,0]]
        self.delayed.append(self.requests.copy())
        ch.d.ctrl[self.joints]=np.clip(ch.d.ctrl[self.joints]+self.delayed[0],self.bounds[:,0],self.bounds[:,1])


def run_seed(seed,material='high',name=None,trace=None,track='combined'):
    if name is None:
        frozen=json.loads((HERE/'selected.json').read_text())
        name=frozen['name']; policy=frozen['parameters']
    else:
        policy=bank()[name]
    actor=Opening(policy)
    params=actors.configured(study.BASE['params'],RECIPE)
    base_observe=short_track.Meter.observe
    def observe(m,t,dist,fail,on,audit,bc):
        base_observe(m,t,dist,fail,on,audit,bc)
        if m.valid and on:
            actor.both_m=max(actor.both_m,dist)
            if actor.first_quarter is None and dist>=.25:actor.first_quarter=t
            if actor.first_half is None and dist>=.50:actor.first_half=t
            if abs(t-2.)<1e-8:actor.both2=True
    with material_surface(material) as contacts,actors.controller(RECIPE,study.BASE['settings']) as mon:
        old_drive=actors.locomotion.Locomotion.control;old_head=actors.ball.BallChannel.control
        def drive(w,d,speed):
            bc=mon['live']
            if bc is not None and d is bc.d:actor.update(bc);speed*=actor.speed
            return old_drive(w,d,speed)
        def head(ch,estimate=None):
            bc=mon['live']
            if bc is None or ch is not bc.channels[0] or policy is None:return old_head(ch,estimate)
            actor.update(bc)
            bias=getattr(ch,'plate_bias',np.zeros(2));ch.plate_bias=bias+actor.tilt
            try:
                out=old_head(ch,estimate)
                actor.joint_command(ch)
                return out
            finally:ch.plate_bias=bias
        with patch.object(short_track.Meter,'observe',observe),patch.object(actors.locomotion.Locomotion,'control',drive),patch.object(actors.ball.BallChannel,'control',head):
            r=short_track.run(track,seed,params,trace=trace,timeout=45.)
        mu=[contacts[n][1] for n in cp.NAMES]
    if material=='high': assert mu==[.416,.416]
    return dict(name=name,material=material,track=track,seed=int(seed),flat=r['flat_1m'],slope=r['slope_1m'],
                finish=r['finish_2p5'],both2=actor.both2,qtr=actor.first_quarter is not None,half=actor.first_half is not None,
                m=r['last_both_m'],both_peak=actor.both_m,t=r['seconds'],reason=r['reason'],mu_a=mu[0],mu_b=mu[1],
                torque=max(r['motor']['peak_nm']),active=actor.active)


def job(args):return run_seed(*args)


def batch(pool,names,first,n,materials,file):
    jobs=[(s,mat,name) for s in range(first,first+n) for mat in materials for name in names]
    rows=list(pool.map(job,jobs,chunksize=4))
    with (HERE/(file+'.csv')).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    summary={}
    for name in names:
        summary[name]={}
        for mat in materials:
            subset=[r for r in rows if r['name']==name and r['material']==mat]
            assert len({r['seed'] for r in subset})==len(subset)==n and all(r['torque']<=.20000001 for r in subset)
            counts={k:sum(r[k] for r in subset) for k in ('finish','slope','flat','half','qtr','both2')}
            summary[name][mat]=dict(n=n,**counts,mean=float(np.mean([r['m'] for r in subset])),p90=float(np.quantile([r['m'] for r in subset],.90)),peak=max(r['m'] for r in subset))
    write(file+'.json',summary)
    return summary


def order(v):
    by=list(v.values())
    return tuple(sum(a[k] for a in by) for k in ('finish','slope','flat','half'))+(
        sum(a['qtr']+.35*a['both2']+1.3*a['mean']*a['n'] for a in by),)


def main():
    controls=bank()
    write('protocol.json',dict(bank=controls,screen=[17040000,24],select=[17041000,64],holdout=[17042000,160],materials=['high','wide'],
          rank='lexicographic totals finish/whole-slope/flat one/half metre then quarter + 0.35*both-contact at 2s + 1.3*sum(last-both metre)',
          random_policy_seed=91627,source=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    with ProcessPoolExecutor(6) as pool:
        a=batch(pool,controls,17040000,24,['high'],'screen')
        winners=sorted((n for n in controls if n!='medium'),key=lambda n:order(a[n]),reverse=True)[:8]
        print('screen',winners,{n:a[n] for n in winners[:1]},flush=True)
        b=batch(pool,['medium',*winners],17041000,64,['high','wide'],'selection')
        winner=max(b,key=lambda n:order(b[n]))
        write('selected.json',dict(name=winner,parameters=controls[winner],holdout_start=17042000,n=160,
              comparison='medium',selection_score=order(b[winner])))
        print('selected',winner,b[winner],flush=True)
        h=batch(pool,list(dict.fromkeys(['medium',winner])),17042000,160,['high','wide','nominal'],'validation')
        print('validation',h,flush=True)


if __name__=='__main__':main()
