"""Warm-start a PPO residual using delayed observations and real double-contact rewards."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch
import argparse
import json
import sys
import numpy as np
from material import HERE,RECIPE,actors,cp,save,short_track,study,surface

LEGACY=HERE.parent/'pingpong-dual16-antigravity-20261128'/'rl_route'
sys.path.insert(0,str(LEGACY))
import rl_actor as original

OUT=HERE/'ppo'
OUT.mkdir(exist_ok=True)
OBS=28
EXTRA=('separation_speed','edge_margin','projected_margin','gait_sine','gait_cosine')


def load_weights(label):
    with np.load(OUT/f'{label}.npz') as data:
        return {k:v.copy() for k,v in data.items()}


def observe(controller):
    a,b=controller.channels
    za,zb=a.measurements[0],b.measurements[0]
    dp=za[:2]-zb[:2]
    separation_speed=float(dp@(za[2:]-zb[2:]))/max(.006,float(np.linalg.norm(dp)))
    r=max(np.linalg.norm(za[:2]),np.linalg.norm(zb[:2]))
    future=max(np.linalg.norm(za[:2]+.25*za[2:]),np.linalg.norm(zb[:2]+.25*zb[2:]))
    phase=a.tick*.02*2*np.pi/.55
    return np.clip([separation_speed/.12,(.055-r)/.045,(.055-future)/.055,np.sin(phase),np.cos(phase)],-4,4)


class Rollout(original.Rollout):
    def after_step(self,controller,radius):
        self.frames+=1


def episode(job):
    w,seed,material,sampler,track,trace=job
    run=Rollout(w,study.BASE['settings'],None if sampler is None else np.random.default_rng(sampler))
    parent=original.make_controller(run)
    class Controller(parent):
        def sense(self):
            return np.r_[super().sense(),observe(self)]
    both2=False
    maximum=0.
    ticks=0
    old_observe=short_track.Meter.observe
    def meter(check,t,s,fail,on,audit,bc):
        nonlocal both2,maximum,ticks
        old_observe(check,t,s,fail,on,audit,bc)
        good=bool(check.valid and on)
        if abs(t-2.)<1e-8:both2=good
        if good:ticks+=1
        if sampler is not None and run.pay:
            r=max(bc.last_radii)
            clearance=np.clip((.055-r)/.055,0,1)
            next_max=max(maximum,s) if good else maximum
            past_gate=int(maximum/.25)
            progress=next_max-maximum
            run.pay[-1]+=28*progress+.70*(int(next_max/.25)-past_gate)
            run.pay[-1]+=(.003+.016*clearance if good else -.010)-.002*float(bc.held@bc.held)
            if good and abs(t-2.)<1e-8:run.pay[-1]+=.45
            maximum=next_max
    p=actors.configured(study.BASE['params'],RECIPE)
    with surface(material),patch.object(cp.ball,'BallController',Controller),patch.object(original,'project',lambda x,y:(x,y)),patch.object(short_track.Meter,'observe',meter):
        res=short_track.run(track,seed,p,trace=trace,timeout=45.)
    row=dict(seed=seed,material=material,m=res['last_both_m'],flat=res['flat_1m'],slope=res['slope_1m'],
             finish=res['finish_2p5'],both2=both2,t=res['seconds'],reason=res['reason'],steps=run.frames,
             both_frames=ticks,torque=max(res['motor']['peak_nm']))
    if sampler is None:return row
    run.pay[-1]+=20 if res['success'] else -1.0
    row['reward']=float(sum(run.pay))
    return row,tuple(np.asarray(z,np.float32) for z in (run.obs,run.raw,run.lp,run.pay))


def run_seed(seed,material='high',track='combined',trace=None,label=None):
    if label is None:label=json.loads((OUT/'frozen.json').read_text())['label']
    return episode((load_weights(label),seed,material,None,track,trace))


def summary(rows):
    return dict(n=len(rows),finish=sum(r['finish'] for r in rows),slope=sum(r['slope'] for r in rows),flat=sum(r['flat'] for r in rows),
                half=sum(r['m']>=.5 for r in rows),quarter=sum(r['m']>=.25 for r in rows),both2=sum(r['both2'] for r in rows),
                mean=float(np.mean([r['m'] for r in rows])),max_m=max(r['m'] for r in rows),frames=sum(r['steps'] for r in rows))


def rank(stats):
    return tuple(stats[key] for key in ('finish','slope','flat','half','quarter','both2','mean'))


def train():
    import torch
    from torch import nn
    import train_ppo as trainer
    torch.manual_seed(18568)
    gen=np.random.default_rng(35016)
    warm=json.loads((LEGACY/'selected.json').read_text())['settings']['weights']
    epochs=24;batch=48
    save(OUT/'protocol.json',dict(epochs=epochs,episodes_per_epoch=batch,extra_features=EXTRA,
         conditions=['high','wide','nominal'],dev_start=17200000,checkpoint_start=17210000,checkpoint_n=96,
         ranking=['finish','slope','flat','half','quarter','both2','mean'],warm_parent=str(LEGACY/'selected.json')))
    w=original.arrays(warm)
    hidden=w['w1'].shape[0]
    pi=nn.Sequential(nn.Linear(OBS,hidden),nn.Tanh(),nn.Linear(hidden,original.ACT))
    value=nn.Sequential(nn.Linear(OBS,32),nn.Tanh(),nn.Linear(32,1))
    with torch.no_grad():
        pi[0].weight.zero_();pi[0].weight[:,:original.OBS].copy_(torch.tensor(w['w1']))
        for dest,k in [(pi[0].bias,'b1'),(pi[2].weight,'w2'),(pi[2].bias,'b2')]:dest.copy_(torch.tensor(w[k]))
    ls=nn.Parameter(torch.tensor(w['logstd'],dtype=torch.float32))
    optim=torch.optim.Adam([dict(params=list(pi.parameters())+[ls],lr=.0006),dict(params=value.parameters(),lr=.0018)])
    history=[]
    w=trainer.to_numpy(pi,ls);np.savez_compressed(OUT/'warm.npz',**w)
    neutral={k:x.copy() for k,x in w.items()}
    neutral['w2'][:]=0;neutral['b2'][:]=0
    np.savez_compressed(OUT/'neutral.npz',**neutral)
    checkpoints=['neutral','warm']
    with ProcessPoolExecutor(5) as pool:
        for epoch in range(epochs):
            materials=['high','wide','high','nominal']
            jobs=[(w,17200000+batch*epoch+i,materials[i%4],894000+epoch*batch+i,'combined',None) for i in range(batch)]
            episodes=list(pool.map(episode,jobs,chunksize=3))
            rows=[r for r,_ in episodes]
            X,A,old,adv,targets=trainer.batch_adv(episodes,value)
            for _ in range(4):
                indices=gen.permutation(len(X))
                for j in np.array_split(indices,max(1,int(np.ceil(len(X)/128)))):
                    dist=torch.distributions.Normal(pi(X[j]),ls.exp())
                    logp=dist.log_prob(A[j]).sum(1);ratio=(logp-old[j]).exp()
                    gain=torch.min(ratio*adv[j],ratio.clamp(.82,1.18)*adv[j]).mean()
                    critic=nn.functional.smooth_l1_loss(value(X[j])[:,0],targets[j])
                    loss=-gain+.5*critic-.0015*dist.entropy().sum(1).mean()
                    optim.zero_grad();loss.backward()
                    nn.utils.clip_grad_norm_([*pi.parameters(),*value.parameters(),ls],.65);optim.step()
                    with torch.no_grad():ls.clamp_(-1.45,-.3)
            w=trainer.to_numpy(pi,ls)
            result=summary(rows);result.update(epoch=epoch+1,policy_decisions=len(X),reward=float(np.mean([r['reward'] for r in rows])))
            history.append(result);save(OUT/'curve.json',history)
            if epoch+1 in (6,12,18,24):
                label=f'ppo-{epoch+1}';checkpoints.append(label);np.savez_compressed(OUT/f'{label}.npz',**w)
            print(epoch+1,result['both2'],result['max_m'],flush=True)
        scores={}
        for label in checkpoints:
            weights=load_weights(label)
            jobs=[(weights,s,'high',None,'combined',None) for s in range(17210000,17210096)]
            rows=list(pool.map(episode,jobs,chunksize=4));scores[label]=summary(rows)
        chosen=max(checkpoints,key=lambda label:rank(scores[label]))
        save(OUT/'frozen.json',dict(label=chosen,stats=scores,conditions='picked on fixed .416'))
        print('frozen',chosen,scores,flush=True)


if __name__=='__main__':
    train()
