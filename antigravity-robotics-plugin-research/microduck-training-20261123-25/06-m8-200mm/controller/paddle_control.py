"""Closed-loop ground gathering with a bank of strictly open-jaw trained push motions."""
import copy
import json
import math
from pathlib import Path
import mujoco
import numpy as np
from align_pair import vector,wrap
from episode import course
from sweep_push import Sweep

HERE=Path(__file__).resolve().parent


def params_for(ctx, v):
    x,y,phase,amp,head,neck,basehead,baseyaw,rate,knee,hip=v
    p=ctx.params.copy()
    p.update(neck=p['neck']+neck,head=p['head']+basehead,bite_yaw=baseyaw,rate=p['rate']*rate,
             knee=p['knee']+knee,hip=p['hip']+hip)
    return p,(phase,amp,head)


def rollout(ctx, v, moving, duration=3.80):
    m=ctx.m;d=copy.copy(ctx.d);prev=ctx.prev.copy()
    p,mode=params_for(ctx,v);control=Sweep(m,d,p,mode)
    audit=course.Audit(m,d,accelerated=True);air=np.zeros(2)
    origin=d.xpos[audit.nut,:2].copy();gap0=np.linalg.norm(origin[1]-origin[0])
    cmds=[]
    for i in range(round(duration/.02)):
        a=control.step(d);cmds.append(a)
        d.ctrl[:]=prev if ctx.delay else a;prev=a
        for _ in range(ctx.standard):
            mujoco.mj_step(m,d);audit.sample('gather',[])
            air=np.where(audit.z>.001,air+m.opt.timestep,0.)
            if max(air)>=.02-1e-8 or audit.problem:
                return None
        if i==105 and np.linalg.norm(d.xpos[audit.nut[moving],:2]-origin[moving])<.001:
            return None
    xy=d.xpos[audit.nut,:2]
    end_gap=np.linalg.norm(xy[1]-xy[0])
    if end_gap < .015 or end_gap>gap0-.002:return None
    return float(end_gap),cmds


def walls_distance(scene,xy):
    boxes=scene['boxes']
    c=np.array([b['center'][:2] for b in boxes])
    h=np.array([b['half_size'][:2] for b in boxes])
    a=np.array([b.get('yaw_rad',0.) for b in boxes]);dx,dy=(np.asarray(xy)-c).T
    z=np.column_stack((abs(np.cos(a)*dx+np.sin(a)*dy),abs(-np.sin(a)*dx+np.cos(a)*dy)))-h
    return float((np.linalg.norm(np.maximum(z,0),axis=1)+np.minimum(z.max(axis=1),0)).min())


def gather(ctx,options):
    bank=json.loads((HERE/'paddle-bank.json').read_text())
    start=ctx.time
    last_preview=-100.
    moved=0;probes=0;records=[];selected=None
    last_select=-100
    while ctx.time-start<options.get('timeout',127.) and not ctx.reason:
        xy=ctx.d.xpos[ctx.audit.nut,:2].copy();gap=float(np.linalg.norm(xy[1]-xy[0]))
        if .015<gap<options.get('target_gap',.025):
            return dict(success=True,reason='ground_pair_ready',data=records,trials=probes)
        if ctx.time-last_select>4 or selected is None:
            alternatives=[]
            canon=bank[0]
            for src in (0,1):
                split=xy[1-src]-xy[src];angle=np.arctan2(split[1],split[0])
                for mirror in [1,-1]:
                    local=np.asarray(canon['xy'])*[1,mirror]
                    heading=wrap(angle-math.atan2(local[1],local[0]))
                    f=vector(heading);side=np.array([-f[1],f[0]])
                    station=xy[src]-canon['vec'][0]*f-mirror*canon['vec'][1]*side
                    cost=np.linalg.norm(station-ctx.xy)+.04*abs(wrap(heading-ctx.yaw))
                    cost+=3*max(0.,.125-walls_distance(ctx.scene,station))
                    if selected==(src,mirror):cost-=.035
                    alternatives.append((cost,src,mirror))
            _,src,mirror=min(alternatives);selected=(src,mirror);last_select=ctx.time
        src,mirror=selected
        split=xy[1-src]-xy[src];angle=np.arctan2(split[1],split[0])
        k=int(max(0,ctx.time-last_preview)*5)%len(bank) if probes else 0
        reference=bank[0]
        local=np.asarray(reference['xy'])*[1,mirror]
        heading=wrap(angle-math.atan2(local[1],local[0]))
        f=vector(heading);side=np.array([-f[1],f[0]])
        station=xy[src]-reference['vec'][0]*f-mirror*reference['vec'][1]*side
        error=station-ctx.xy;yaw_error=wrap(heading-ctx.yaw)
        current_f=vector(ctx.yaw);current_side=np.array([-current_f[1],current_f[0]])
        local_x,local_y=(xy[src]-ctx.xy)@current_f,(xy[src]-ctx.xy)@current_side
        if .070<local_x<.137 and abs(local_y-mirror*.025)<.026 and abs(yaw_error)<.70 and ctx.time-last_preview>=.16:
            last_preview=ctx.time
            winner=None
            for model in bank[:options.get('candidates',8)]:
                v=model['vec'].copy()
                if mirror<0:v[3]=-v[3];v[7]=-v[7]
                probes+=1
                r=rollout(ctx,v,src)
                if r and (winner is None or r[0]<winner[0]):winner=r
                if winner and (winner[0]<.025 or gap-winner[0]>.024):break
            if winner and gap-winner[0]>min(.004,.5*(gap-.023)):
                records.append(dict(t=round(ctx.time,3),before=gap,forecast=winner[0],source=src))
                for action in winner[1]:
                    if not ctx.step(action,'gather'):break
                moved+=1
                ctx.walker.obs[0,34:48]=0.;ctx.walker.previous_raw=ctx.prev[:14].copy()
                last_preview=-100.;continue
        x,y=error@current_f,error@current_side
        cmd=np.clip([4.2*x,5.*y,3.*yaw_error],[-.24,-.29,-.86],[.29,.29,.86])
        mag=max(abs(cmd[:2]))
        if .002<np.linalg.norm(error)<.065 and 1e-6<mag<.15:cmd[:2]*=.15/mag
        if not ctx.walk_step(cmd):break
    return dict(success=False,reason=ctx.reason or 'paddle_gather_timeout',data=records,trials=probes)

