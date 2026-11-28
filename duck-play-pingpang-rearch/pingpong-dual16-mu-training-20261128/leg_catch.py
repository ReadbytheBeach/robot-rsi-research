"""Learn bounded stance-leg height corrections when the observed balls start to diverge."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch
import csv
import mujoco
import numpy as np
from material import HERE,RECIPE,actors,save,short_track,study,surface

OUT=HERE/'leg-catch';OUT.mkdir(exist_ok=True)


def make_actions():
    rng=np.random.default_rng(31361)
    actions=[None]
    for i in range(24):
        actions.append(dict(amplitude_m=float(rng.uniform(.0025,.010)),frequency_hz=float(rng.uniform(.85,3.1)),
           phase=float(rng.uniform(-np.pi,np.pi)),stance_only=i%3!=0,differential=float(rng.uniform(-.85,.85)),
           early=i%2==0,pace=float(rng.uniform(-.22,.22)),follow=float(rng.choice([0.,.8,-.8]))))
    return actions


def leg_maps(bc,walk):
    m=bc.m;d=bc.d;indices=[];coefficients=[]
    for side in ('left','right'):
        ids=np.array([m.actuator(side+'_'+j).id for j in ('hip_pitch','knee','ankle')])
        dofs=m.jnt_dofadr[m.actuator_trnid[ids,0]]
        geom=m.geom(side+'_foot_collision').id
        jp=np.zeros((3,m.nv));jr=np.zeros_like(jp)
        mujoco.mj_jac(m,d,jp,jr,d.geom_xpos[geom],int(m.geom_bodyid[geom]))
        J=np.stack([jp[0,dofs],jp[2,dofs],.04*jr[1,dofs]])
        response=J.T@np.linalg.solve(J@J.T+.002**2*np.eye(3),[0.,1.,0.])
        indices.extend(ids);coefficients.extend(np.clip(response,-65.,65.))
    ids=np.array(indices);return ids,np.array(coefficients),m.jnt_range[m.actuator_trnid[ids,0]]


def run(args):
    seed,mat,a,trace=args
    state={'both2':False,'peak':0.,'joint_peak':0.}
    params=actors.configured(study.BASE['params'],RECIPE)
    base=short_track.Meter.observe
    def meter(m,t,x,fail,on,audit,bc):
        base(m,t,x,fail,on,audit,bc)
        if m.valid and on:
            state['peak']=max(x,state['peak'])
            if abs(t-2)<1e-8:state['both2']=True
    with surface(mat),actors.controller(RECIPE,study.BASE['settings']) as mon:
        old=actors.locomotion.Locomotion.control
        def drive(w,d,speed):
            bc=mon['live']
            if a is None or bc is None or bc.d is not d:return old(w,d,speed)
            if 'queue' not in state:
                state['ids'],state['shape'],state['range']=leg_maps(bc,w)
                state['feet']=[bc.m.geom(side+'_foot_collision').id for side in ('left','right')]
                state['queue']=deque([np.zeros(6)]*(1+bc.act_lag),maxlen=1+bc.act_lag)
                state['offset']=np.zeros(6)
            z0,z1=[c.measurements[0] for c in bc.channels]
            delta=z0[:2]-z1[:2];span=max(.005,np.linalg.norm(delta))
            dv=delta@(z0[2:]-z1[2:])/span
            forecast=max(np.linalg.norm(z[:2]+.25*z[2:]) for z in (z0,z1))
            risk=np.clip((forecast-.021)/.035+max(dv,0)/.105,0.,1.)
            t=bc.tick*.02
            if a['early']:risk*=np.clip((2.2-t)/.3,0,1)
            result=old(w,d,float(speed*(1+a['pace']*risk)))
            relative=np.tanh((d.geom_xpos[state['feet'][1],2]-d.geom_xpos[state['feet'][0],2])/.008)
            load=np.array([(1+relative)/2,(1-relative)/2]) if a['stance_only'] else np.ones(2)
            wave=np.sin(2*np.pi*a['frequency_hz']*t+a['phase']+a['follow']*relative)
            projected=(z0 if np.linalg.norm(z0[:2])>=np.linalg.norm(z1[:2]) else z1)
            toward=np.tanh((projected[1]+.25*projected[3])/.03)
            offset=load*a['amplitude_m']*wave*risk*np.array([1+a['differential']*toward,1-a['differential']*toward])
            request=np.clip(state['shape']*np.repeat(offset,3),-.14,.14)
            state['queue'].append(request)
            state['offset']+=np.clip(state['queue'][0]-state['offset'],-.025,.025)
            ids=state['ids'];bounds=state['range']
            d.ctrl[ids]=np.clip(d.ctrl[ids]+state['offset'],bounds[:,0],bounds[:,1])
            state['joint_peak']=max(state['joint_peak'],float(np.max(abs(state['offset']))))
            return result
        with patch.object(actors.locomotion.Locomotion,'control',drive),patch.object(short_track.Meter,'observe',meter):
            r=short_track.run('combined',seed,params,trace=trace,timeout=45.)
    return dict(seed=seed,m=r['last_both_m'],both2=state['both2'],peak=state['peak'],flat=r['flat_1m'],slope=r['slope_1m'],
                finish=r['finish_2p5'],t=r['seconds'],torque=max(r['motor']['peak_nm']),max_joint_change=state['joint_peak'])


def batch(pool,start,n,ids,mats,actions,label):
    jobs=[(s,m,i) for s in range(start,start+n) for m in mats for i in ids]
    rr=list(pool.map(run,[(s,m,actions[i],None) for s,m,i in jobs],chunksize=5))
    for (_,m,i),r in zip(jobs,rr):r.update(material=m,action=i)
    with (OUT/(label+'.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    stats={}
    for i in ids:
        stats[i]={}
        for m in mats:
            sub=[r for r in rr if r['material']==m and r['action']==i]
            stats[i][m]=dict(n=n,finish=sum(r['finish'] for r in sub),slope=sum(r['slope'] for r in sub),flat=sum(r['flat'] for r in sub),
                half=sum(r['peak']>=.5 for r in sub),qtr=sum(r['peak']>=.25 for r in sub),both2=sum(r['both2'] for r in sub),
                mean=float(np.mean([r['m'] for r in sub])),best=max(r['m'] for r in sub))
    save(OUT/(label+'.json'),stats)
    return stats


def rank(v):
    return tuple(sum(x[k] for x in v.values()) for k in ('finish','slope','flat','half','qtr','both2','mean'))


def main():
    actions=make_actions()
    save(OUT/'protocol.json',dict(actions=actions,screen=[17701000,24],select=[17702000,64],heldout=[17703000,192]))
    with ProcessPoolExecutor(4) as pool:
        first=batch(pool,17701000,24,range(len(actions)),['high'],actions,'screen')
        ids=[0,*sorted(range(1,len(actions)),key=lambda i:rank(first[i]),reverse=True)[:5]]
        scored=batch(pool,17702000,64,ids,['high','wide'],actions,'selection')
        best=max(ids[1:],key=lambda i:rank(scored[i]))
        save(OUT/'frozen.json',dict(index=best,spec=actions[best],comparison=0))
        batch(pool,17703000,192,[0,best],['high','wide'],actions,'heldout')


if __name__=='__main__':main()
