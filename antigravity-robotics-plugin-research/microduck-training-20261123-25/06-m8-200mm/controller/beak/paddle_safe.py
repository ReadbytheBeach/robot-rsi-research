"""Approach a free nut without sweeping the other during ground staging; test actuators on copies."""
import copy
import json
import math
from pathlib import Path

import numpy as np

from align_pair import vector, wrap
from episode import course, HOME, OPEN
from paddle_control import params_for, walls_distance
from sweep_push import Sweep
from foot.preview import Roll

HERE = Path(__file__).resolve().parent
BANK = json.loads((HERE.parent / 'paddle-bank.json').read_text())

def move_heading(position,yaw,station,heading,gain=9.):
    f=vector(yaw); s=np.array([-f[1],f[0]])
    diff=station-position
    raw=np.array([diff@f,diff@s])
    cmd=np.clip(gain*raw,[-.45,-.38],[.49,.38])
    for i,dead in enumerate((.21,.26)):
        if abs(raw[i])>.004 and abs(cmd[i])<dead:
            cmd[i]=math.copysign(dead,raw[i])
    return np.r_[cmd,np.clip(4.*wrap(heading-yaw),-1.,1.)]

def pose_at(xy,source,mirror,shift,aim_err):
    obj=xy[source]; delta=xy[1-source]-obj
    v=BANK[0];impact=np.array(v['xy'])*[1,mirror]
    heading=wrap(math.atan2(delta[1],delta[0])-math.atan2(impact[1],impact[0])+aim_err)
    f=vector(heading); s=np.array([-f[1],f[0]])
    return obj-(v['vec'][0]+shift[0])*f-(mirror*v['vec'][1]+shift[1])*s,heading

def waypoint(pos, goal, nuts):
    """Shortest few-edge walk around the two floor parts; base disks cover both feet."""
    import heapq
    radius=.083
    def clear(a,b):
        delta=b-a;den=delta@delta
        if den<1e-10:return True
        for c in nuts:
            u=np.clip(((c-a)@delta)/den,0,1);d=np.linalg.norm(c-(a+u*delta))
            if d<radius:
                if (np.linalg.norm(a-c)<radius and u<.001) or (np.linalg.norm(b-c)<radius and u>.999):continue
                return False
        return True
    if clear(pos,goal):return goal
    angles=np.arange(12)*np.pi/6
    ring=np.c_[np.cos(angles),np.sin(angles)]*.098
    points=[pos,goal]+[p for c in nuts for p in c+ring if min(np.linalg.norm(p-o) for o in nuts)>=radius]
    dist={0:0.};parent={};todo=[(0.,0)]
    while todo:
        val,i=heapq.heappop(todo)
        if i==1:break
        if val>dist[i]:continue
        for j in range(1,len(points)):
            if i==j:continue
            cost=val+np.linalg.norm(points[i]-points[j])
            if cost>=dist.get(j,float('inf')) or not clear(points[i],points[j]):continue
            dist[j]=cost;parent[j]=i;heapq.heappush(todo,(cost,j))
    if 1 in parent:
        k=1
        while parent[k]!=0:k=parent[k]
        return points[k]
    near=nuts[np.argmin(np.linalg.norm(nuts-pos,axis=1))]
    away=pos-near
    return pos+away/max(np.linalg.norm(away),1e-6)*.04

def copy_walker(ctx):
    w=copy.copy(ctx.walker);w.obs=ctx.walker.obs.copy();w.previous_raw=ctx.walker.previous_raw.copy()
    return w

def pose_branch(ctx,source,mirror,station,heading,command,duration):
    d=copy.copy(ctx.d);w=copy_walker(ctx);prev=ctx.prev.copy();cmds=[];air=ctx.gap.air_streak.copy()
    original=d.xpos[ctx.audit.nut,:2].copy()
    for _ in range(duration):
        a=np.r_[w.command(d.sensor('imu_ang_vel').data,-d.xmat[ctx.trunk,6:9],d.qpos[ctx.q],d.qvel[ctx.v],command),OPEN]
        cmds.append(a);d.ctrl[:]=prev if ctx.delay else a;prev=a
        if ctx.beak_roll.run(d,air,tilt_min=.59):return None
    xy=d.xpos[ctx.audit.nut,:2]
    gap=np.linalg.norm(xy[0]-xy[1]);gap0=np.linalg.norm(original[0]-original[1])
    moved=np.linalg.norm(xy[1-source]-original[1-source])
    moved+=.6*np.linalg.norm(xy[source]-original[source])
    p=d.qpos[ctx.root:ctx.root+2];yaw=course.forward_yaw(d.qpos[ctx.root+3:ctx.root+7])
    dist=np.linalg.norm(p-station);ang=abs(wrap(heading-yaw));clearance=float(np.linalg.norm(p-xy,axis=1).min());score=dist+.045*ang+9*moved+max(0.,gap-gap0)+3*max(0.,.078-clearance)
    return score,cmds,w.obs[0,34:48].copy(),w.previous_raw.copy()

def flat_cost(d, ids):
    # A nut resting on its thin edge is about 3.25 mm higher than one on its face.
    return max(0.,float(d.xpos[ids,2].max())-.00335)*12.


def stroke(ctx,v,mirror,source,offset,hold_n,prefer_flat=False):
    # The candidate emits joint targets for the original free-body robot and scene.
    d=copy.copy(ctx.d);prev=ctx.prev.copy();air=ctx.gap.air_streak.copy();cmds=[]
    ids=ctx.audit.nut; start=d.xpos[ids,:2].copy();gap0=np.linalg.norm(start[0]-start[1])
    home=np.r_[HOME,OPEN]
    cfg=v.copy();cfg[3]=cfg[3]*mirror+offset[0];cfg[7]=cfg[7]*mirror+offset[1];cfg[4]+=offset[2]
    pp,mode=params_for(ctx,cfg)
    for i in range(hold_n+185):
        if i<hold_n:
            # Establish a repeatable load on both feet before replaying the reach.
            a=home
        else:
            if i==hold_n:ctr=Sweep(ctx.m,d,pp,mode)
            a=ctr.step(d)
        cmds.append(a); d.ctrl[:]=prev if ctx.delay else a;prev=a
        if ctx.beak_roll.run(d,air,tilt_min=.59):return None
        if i==hold_n+110:
            if np.linalg.norm(d.xpos[ids[source],:2]-start[source])<.001:return None
    gap=float(np.linalg.norm(d.xpos[ids[0],:2]-d.xpos[ids[1],:2]))
    old_error=abs(gap0-.0215);new_error=abs(gap-.0215)
    if prefer_flat:
        old_error+=flat_cost(ctx.d,ids)
        new_error+=flat_cost(d,ids)
    if gap<.0158:return None
    if prefer_flat and new_error>=old_error-.0015:return None
    if not prefer_flat and gap>=gap0-.0015:return None
    return new_error,gap,cmds

def gather(ctx,options):
    ctx.beak_roll=Roll(ctx,course.NUT_VERTICES)
    prefer_flat=options.get("prefer_flat",False)
    start=ctx.time;src=None;mirror=1;lock=0.;last_try=-100;records=[];nprobe=0;steps=0
    stale=ctx.time;last_choice=None;switch=0
    shifts=[(0.,0.),(-.005,0.),(.006,0.),(0.,-.008),(0.,.007),(.011,-.010),(-.008,.008)]
    angles=[0.,.15,-.15,.35,-.33]
    while ctx.time-start<options.get('timeout',135) and not ctx.reason:
        xy=ctx.d.xpos[ctx.audit.nut,:2].copy();gap=np.linalg.norm(xy[0]-xy[1])
        if .0155<=gap<=.0255 and (not prefer_flat or flat_cost(ctx.d,ctx.audit.nut)<.004):return dict(success=True,reason='ground_pair_ready',data=records,probes=nprobe,moves=steps)
        if src is None or ctx.time>lock:
            choices=[]
            for src1 in (0,1):
                for mir1 in (1,-1):
                    station,h=pose_at(xy,src1,mir1,(0.,0.),0.)
                    risk=max(0.,.09-walls_distance(ctx.scene,station))
                    dist=np.linalg.norm(station-ctx.xy)
                    preference=-.030 if last_choice==(src1,mir1) else 0.
                    choices.append((dist+.03*abs(wrap(h-ctx.yaw))+2*risk+preference,src1,mir1))
            choices.sort()
            choice=choices[min(switch,len(choices)-1)];_,src,mirror=choice
            last_choice=(src,mirror);lock=ctx.time+options.get('station_budget',8.)
            shift_i=0;phase0=ctx.time;last_try=-100
        shift_i=int((ctx.time-phase0)/1.8)%len(shifts)
        station,h=pose_at(xy,src,mirror,shifts[shift_i],angles[(shift_i//2)%len(angles)])
        f=vector(ctx.yaw);s=np.array([-f[1],f[0]])
        dx=(xy[src]-ctx.xy)@f;dy=(xy[src]-ctx.xy)@s
        if .070<dx<.140 and abs(dy)<.066 and abs(wrap(h-ctx.yaw))<.7 and ctx.time-last_try>.27:
            last_try=ctx.time
            best=None
            # The first hold separates current foot phase from the ground-reaching motion.
            n=int(options.get('preview_bank',5))
            for j in range(n):
                idx=(0,3,9,2,12,1,5,8)[j%8]%len(BANK)
                off=[(0,0,0),(0,0,0),(0,0,0),(.15*mirror,.08*mirror,-.04),(-.22*mirror,-.08*mirror,.08),(0,0,0),(.1,0,-.05),(0,0,0)][j%8]
                hold=(15,0,26,12,8,23,16,0)[j%8]
                cand=stroke(ctx,BANK[idx]['vec'],mirror,src,off,hold,prefer_flat);nprobe+=1
                if cand and (best is None or cand[0]<best[0]):best=cand
                if best and ((prefer_flat and best[0]<.003) or (not prefer_flat and (.016<best[1]<.025 or gap-best[1]>.023))):break
            if best and (prefer_flat or gap-best[1]>.003 or best[1]<.025):
                records.append(dict(time=ctx.time,gap=gap,target=best[1],src=src))
                for a in best[2]:
                    if not ctx.step(a,'gather'):break
                ctx.walker.obs[0,34:48]=0.;ctx.walker.previous_raw=ctx.prev[:14].copy()
                stale=ctx.time;switch=0;src=None;last_try=-100;continue
        staging=waypoint(ctx.xy,station,xy)
        if np.linalg.norm(staging-station)>.012:
            dv=staging-ctx.xy
            station=staging
            if np.linalg.norm(dv)>.055:h=math.atan2(dv[1],dv[0])
        base=move_heading(ctx.xy,ctx.yaw,station,h)
        cmds=[base,base*[.8,1.4,.95],base*[1.4,.8,1.13],np.r_[base[0],0.,base[2]],np.r_[0.,base[1],base[2]],np.r_[base[:2],0.]]
        if np.linalg.norm(ctx.xy-station)<.05:cmds+=[np.r_[0.,.36,0.],np.r_[0.,-.36,0.],np.array([.30,0.,0.]),np.array([-.26,0.,0.])]
        dest=[]
        for cmd in cmds:
            cand=pose_branch(ctx,src,mirror,station,h,cmd,12)
            if cand:dest.append(cand)
        if not dest:src=None;switch=(switch+1)%4
        else:
            _,acts,hist,raw=min(dest,key=lambda q:q[0])
            for a in acts:
                if not ctx.step(a,'gather'):break
            ctx.walker.obs[0,34:48]=hist;ctx.walker.previous_raw=raw
            steps+=1
        if ctx.time-stale>15.:
            src=None;switch=(switch+1)%4;stale=ctx.time
        if not dest and not ctx.reason:
            # Try reverse/turn escape variants from the genuine current state.
            rescue=[]
            for cm in ((-.46,0.,0.),(-.32,.29,0.),(-.32,-.29,0.),(.4,.32,0.),(.4,-.32,0.),(0.,0.,1.),(0.,0.,-1.),(0.,0.,0.)):
                rr=pose_branch(ctx,src or 0,mirror,station,h,cm,8)
                if rr:rescue.append(rr)
            if not rescue:break
            _,acts,hist,raw=min(rescue,key=lambda q:q[0])
            for a in acts:
                if not ctx.step(a,'gather'):break
            ctx.walker.obs[0,34:48]=hist;ctx.walker.previous_raw=raw
    return dict(success=False,reason=ctx.reason or 'paddle_timeout',data=records,probes=nprobe,moves=steps)
