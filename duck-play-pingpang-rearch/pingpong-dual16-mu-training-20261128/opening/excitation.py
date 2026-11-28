"""Test bounded, risk-gated periodic actuation with unchanged flat-paddle contact."""
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from unittest.mock import patch
import numpy as np
import mujoco
import train_opening as t


def candidates():
    rng=np.random.default_rng(812450)
    bank={'medium':None}
    for i in range(24):
        bank[f'osc_{i:02d}']=dict(frequency=float(rng.choice([1.4,2.1,3.2,4.5,5.8])),
            yaw=float(rng.choice([0,-1,1])*rng.uniform(.09,.58)),neck=float(rng.uniform(-.14,.14)),
            tilt=float(rng.uniform(-.19,.19)),duration=float(rng.choice([.85,1.7,3.5])),shape=i%3)
    return bank


def slip(m,d,cache):
    for ct in d.contact:
        i,j=ct.geom1,ct.geom2
        if ct.dist>0 or cache['face'] not in (i,j):continue
        g=i if j==cache['face'] else j
        if g not in cache['balls']:continue
        velocities=[]
        for geom in (g,cache['face']):
            body=m.geom_bodyid[geom]
            spatial=np.zeros(6)
            mujoco.mj_objectVelocity(m,d,mujoco.mjtObj.mjOBJ_BODY,int(body),spatial,0)
            # mjOBJ_BODY is centred at the inertial-frame origin (xipos).
            velocities.append(spatial[3:]+np.cross(spatial[:3],ct.pos-d.xipos[body]))
        rel=velocities[0]-velocities[1]
        tangential=rel-ct.frame[:3]*(ct.frame[:3]@rel)
        cache['samples'].append(float(np.linalg.norm(tangential)))


def run_seed(seed,material='high',name=None,diagnostic=False,trace=None):
    if name is None:name=json.loads((t.HERE/'excitation-frozen.json').read_text())['name']
    config=candidates()[name]
    cache={'samples':[]}
    def update(actor,bc):
        if actor.tick==bc.tick:return
        actor.tick=bc.tick
        if diagnostic and bc.tick<100:
            if 'face' not in cache:
                cache.update(face=bc.channels[0].face,balls=bc.ball_geoms)
            slip(bc.m,bc.d,cache)
        if config is None:return
        q=config
        z=np.array([ch.measurements[0] for ch in bc.channels])
        delta=z[1,:2]-z[0,:2];sep=max(np.linalg.norm(delta),.005);axis=delta/sep
        radial=axis@(z[1,2:]-z[0,2:])
        risk=np.clip(.3+radial/.09,0.,1.)*np.clip((sep+.25*radial-.018)/.045,0.,1.)
        tm=.02*bc.tick
        risk*=np.clip((q['duration']-tm)/.20,0.,1.)*min(1.,(tm+.02)/.08)
        wave=np.sin(2*np.pi*q['frequency']*tm)
        lag=np.cos(2*np.pi*q['frequency']*tm)
        tangent=np.array([-axis[1],axis[0]])
        if q['shape']==0:movement=wave*axis
        elif q['shape']==1:movement=wave*tangent
        else:movement=wave*axis+.65*lag*tangent
        actor.tilt+=np.clip(risk*q['tilt']*movement-actor.tilt,-.07,.07)
        target=risk*np.array([q['yaw']*wave,q['neck']*lag])
        actor.requests+=np.clip(target-actor.requests,-.09,.09)
        actor.active+=int(risk>.05)
    with patch.object(t.Opening,'update',update):
        r=t.run_seed(seed,material,'phase_00' if config else 'medium',trace)
    r['name']=name
    if diagnostic:
        samples=cache['samples']
        r.update(slip_n=len(samples),slip_sum=float(sum(samples)),slip20=sum(v>.020 for v in samples),
                 slip_p90=float(np.quantile(samples,.9)) if samples else 0.)
    return r


def job(c):return run_seed(*c)


def batch(pool,names,materials,start,n,label,diag=False):
    cases=[(s,mat,name,diag) for s in range(start,start+n) for mat in materials for name in names]
    rows=list(pool.map(job,cases,chunksize=4))
    with (t.HERE/(label+'.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    scores={}
    for name in names:
        scores[name]={}
        for mat in materials:
            subset=[r for r in rows if r['name']==name and r['material']==mat]
            assert len({r['seed'] for r in subset})==len(subset)==n
            s={k:sum(r[k] for r in subset) for k in ('finish','slope','flat','half','qtr','both2')}
            s.update(n=n,mean=float(np.mean([r['m'] for r in subset])),peak=max(r['m'] for r in subset))
            if diag:
                ns=sum(r['slip_n'] for r in subset)
                s.update(slip_samples=ns,slip_mean_mm_s=1000*sum(r['slip_sum'] for r in subset)/ns,
                         slip_over20_freq=sum(r['slip20'] for r in subset)/ns)
            scores[name][mat]=s
    t.write(label+'.json',scores)
    return scores


def main():
    configs=candidates()
    t.write('excitation-protocol.json',dict(screen=[17047000,24],select=[17047500,48],independent=[17048000,128],
        candidates=configs,rank='same as train_opening.order; select experimental arm against separately reported original',
        diagnostic='relative tangential contact point velocities sampled at 50Hz at solver-confirmed face contacts in first 2s, pooled by actual contact samples'))
    with ProcessPoolExecutor(4) as pool:
        s=batch(pool,configs,['high'],17047000,24,'excitation-screen')
        top=sorted((n for n in configs if n!='medium'),key=lambda n:t.order(s[n]),reverse=True)[:5]
        sel=batch(pool,['medium',*top],['high','wide'],17047500,48,'excitation-select')
        name=max(top,key=lambda n:t.order(sel[n]))
        t.write('excitation-frozen.json',dict(name=name,policy=configs[name],comparison='medium'))
        val=batch(pool,['medium',name],['high','nominal'],17048000,128,'excitation-validation',True)
    print(val,flush=True)


if __name__=='__main__':main()
