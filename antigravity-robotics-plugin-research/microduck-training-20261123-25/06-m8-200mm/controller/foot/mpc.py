"""Compare contact-causing actuator sequences on exact physics copies, execute measured winners."""
import copy
import json
from pathlib import Path
import sys
import numpy as np
import mujoco

SP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SP))
from foot.preview import Roll
from episode import GroundContext,course,settings,parameters

def rot(yaw):
    s,c=np.sin(yaw),np.cos(yaw)
    return np.array([[c,-s],[s,c]])

def wrap(a):return (a+np.pi)%(2*np.pi)-np.pi

class Planner:
    def __init__(self,ctx,opts):
        self.ctx=ctx;self.opts=opts;self.nuts=ctx.audit.nut
        self.foot=np.array([ctx.m.geom(name+'_foot_collision').id for name in ('left','right')])
        self.rng=np.random.default_rng(42402)
        self.last_gain=0.;self.stuck=0
        self.side_sign={}
        self.path=[];self.roll=Roll(ctx,course.NUT_VERTICES)
    def eval(self,d,moving,foot):
        i=moving;j=1-i
        nut=d.xpos[self.nuts,:2]
        vec=nut[j]-nut[i];gap=np.linalg.norm(vec);norm=vec/max(gap,1e-8)
        if self.opts.get('lateral_goal'):
            if moving not in self.side_sign:self.side_sign[moving]=1. if nut[i,1]>nut[j,1] else -1.
            goal=nut[j]+[0.,self.side_sign[moving]*.022]
            vec=goal-nut[i];norm=vec/max(np.linalg.norm(vec),1e-8)
            radial_error=np.linalg.norm(vec)
        else:radial_error=abs(gap-.022)
        # The front edge of the selected foot should land just behind the moving nut.
        fxy=d.geom_xpos[self.foot[foot],:2]
        yaw=course.forward_yaw(d.qpos[self.ctx.root+3:self.ctx.root+7])
        local=rot(yaw).T@norm
        radius=(.027*abs(local[0])+.019*abs(local[1])+.005)
        want=nut[i]-radius*norm
        delta=fxy-want;back=-delta@norm;cross=abs(delta@[-norm[1],norm[0]])
        cost=radial_error*self.opts.get('gap_weight',5.)+cross*1.5+max(back,0)*.9+max(-back,0)*1.9
        return cost,gap,want
    def simulate(self,cmd,ticks,moving,foot,extra):
        c=self.ctx;m=c.m;d=copy.copy(c.d);walk=copy.copy(c.walker)
        walk.obs=c.walker.obs.copy();walk.previous_raw=c.walker.previous_raw.copy()
        prev=c.prev.copy(); actions=[]
        wa=walk.command
        air=np.zeros(2)
        for k in range(ticks):
            target=wa(d.sensor('imu_ang_vel').data,-d.xmat[c.trunk,6:9],d.qpos[c.q],d.qvel[c.v],cmd)
            if extra is not None:
                leg=foot*9
                target[leg+2:leg+5]+=np.asarray(extra)
            action=np.r_[target,course.OPEN];d.ctrl[:]=prev if c.delay else action
            if self.roll.run(d,air):return 1e3,None
            actions.append(action);prev=action
        cost,_,_=self.eval(d,moving,foot)
        return cost,(actions,walk,d)
    def go(self,moving,foot,k):
        c=self.ctx;d=c.d;opts=self.opts;nuts=d.xpos[self.nuts,:2]
        cost,gap,want=self.eval(d,moving,foot)
        v=want-d.geom_xpos[self.foot[foot],:2];n=v/max(.015,np.linalg.norm(v))
        nbody=rot(c.yaw).T@n
        choices=[]
        for speed in (.24,.35,.48):
            cmd=speed*nbody;choices.append([cmd[0],cmd[1],0])
        vec=nuts[1-moving]-nuts[moving]
        if self.opts.get('lateral_goal'):vec=vec+[0.,self.side_sign[moving]*.022]
        vec/=max(1e-8,np.linalg.norm(vec));nd=rot(c.yaw).T@vec
        for speed in (.20,.28,.4):
            cmd=speed*nd;choices.append([cmd[0],cmd[1],0])
        for j in range(opts.get('branches',24)):
            ang=self.rng.uniform(0,2*np.pi)
            speed=self.rng.uniform(.22,.48)
            if j%2==0:
                ang+=(np.arctan2(nbody[1],nbody[0]));ang-=np.pi
            choices.append([speed*np.cos(ang),speed*np.sin(ang),self.rng.uniform(-.8,.8)])
        best=(1.e5,None)
        for j,cmd in enumerate(choices):
            horizon=opts.get('horizon',26) if j<6 else int(self.rng.integers(12,36))
            extra=None
            if j>=7 and j%3==1:
                extra=self.rng.uniform([-.15,-.25,-.13],[.15,.25,.13])
            score,data=self.simulate(cmd,horizon,moving,foot,extra)
            if score<best[0]:best=(score,(data,cmd,extra) if data is not None else None)
        if best[1] is None:return False
        (actions,walk,end),cmd,extra=best[1]
        for action in actions:
            if not c.step(action,'gather'):return False
        c.walker.obs[:]=walk.obs;c.walker.previous_raw=walk.previous_raw.copy()
        actual=np.max(abs(end.qpos-c.d.qpos))
        after=self.eval(c.d,moving,foot)
        self.path.append(dict(t=c.time,moving=moving,foot=foot,cmd=cmd,discrepancy=float(actual),gap=after[1],
                              nuts=c.d.xpos[self.nuts,:2].tolist(),xy=c.xy.tolist(),foot_xy=c.d.geom_xpos[self.foot[foot],:2].tolist()))
        return True
    def run(self):
        c=self.ctx;dist=[(self.eval(c.d,i,f)[0],i,f) for i in range(2) for f in range(2)]
        _,moving,foot=min(dist);window=[]
        for k in range(self.opts.get('steps',80)):
            if not self.go(moving,foot,k):break
            gap=self.path[-1]['gap'];window.append(gap)
            if self.opts.get('stable',True) and gap<.045 and (not self.opts.get('lateral_goal') or abs(c.d.xpos[self.nuts[0],0]-c.d.xpos[self.nuts[1],0])<.010):
                from mpc_foot import settle_pair
                withdrawn=settle_pair(c,1-moving,self.opts)
                if withdrawn:
                    return dict(success=not c.reason,reason=c.reason or 'stable_pair',withdraw=withdrawn,history=self.path)
            elif not self.opts.get('stable',True) and .016<=gap<=.027:
                return dict(success=True,history=self.path)
            if len(window)>10 and min(window[-9:])>window[-10]-.007:
                ranked=sorted((self.eval(c.d,i,f)[0],i,f) for i in range(2) for f in range(2))
                alternatives=[t for t in ranked if (t[1],t[2])!=(moving,foot)]
                if alternatives:_,moving,foot=alternatives[0]
                window=[]
        return dict(success=False,reason=c.reason or 'no_convergence',history=self.path)
def gather(ctx,opts):
    start=ctx.time
    out=Planner(ctx,opts).run();out['elapsed']=float(ctx.time-start)
    return out

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,default=3000);parser.add_argument('--layout',default='S0')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--steps',type=int,default=70);parser.add_argument('--branches',type=int,default=24)
    parser.add_argument('--delay',type=int,default=0);parser.add_argument('--trace',action='store_true');a=parser.parse_args()
    trace=a.out.with_suffix('.npz') if a.trace else None
    c=GroundContext((a.seed,a.layout,a.delay,parameters(),settings(),trace))
    c.settle();res=gather(c,dict(steps=a.steps,branches=a.branches))
    res.update(c.gap.report());a.out.write_text(json.dumps(res,indent=1,default=float));print(res['success'],c.reason,res['closest_predeparture_m'],c.time)
