"""Branch measured walking and ankle commands to push a free floor nut toward its partner."""
import copy
from itertools import product
import math
import numpy as np
import mujoco

from episode import HOME, OPEN, course


def unit(v):
    return v/max(1e-7,np.linalg.norm(v))


def foot_points(m,d,foot):
    x=d.geom_xpos[foot,:2]
    mat=d.geom_xmat[foot].reshape(3,3)
    mesh=int(m.geom_dataid[foot])
    a=m.mesh_vertadr[mesh];b=a+m.mesh_vertnum[mesh]
    return m.mesh_vert[a:b]@mat.T+d.geom_xpos[foot]


def branch_roll(ctx, options):
    if not options.get('fast_branch', False):
        return None
    from foot.preview import Roll
    if not hasattr(ctx, '_native_foot_roll'):
        ctx._native_foot_roll = Roll(ctx, course.NUT_VERTICES)
    return ctx._native_foot_roll


def advance(ctx,d,walker,prev,command,tag,anchor,steps,live,stop_at_gap=True):
    opts=ctx.config.get('gather_options',{})
    xy0=d.xpos[ctx.audit.nut,:2].copy()
    moving=1-anchor
    desired=unit(xy0[anchor]-xy0[moving])
    left=np.array([-desired[1],desired[0]])
    u,v,rot,push,which=command
    feet=[ctx.m.geom(n+'_foot_collision').id for n in ('left','right')]
    jaw=OPEN
    worst_air=np.zeros(2)
    air=np.zeros(2)
    min_dist=3.
    contact_tick=0
    reason=None
    part_offsets=np.fromiter((ctx.m.joint(n+'_free').dofadr[0] for n in ('nut_a','nut_b')),int)
    roll = None if live else branch_roll(ctx, opts)
    for i in range(steps):
        yaw=course.forward_yaw(d.qpos[ctx.root+3:ctx.root+7])
        c,s=np.cos(yaw),np.sin(yaw)
        cmdxy=u*desired+v*left
        bodycmd=(c*cmdxy[0]+s*cmdxy[1],-s*cmdxy[0]+c*cmdxy[1],rot)
        out=walker.command(d.sensor('imu_ang_vel').data,-d.xmat[ctx.trunk,6:9],d.qpos[ctx.q],d.qvel[ctx.v],bodycmd)
        if push:
            # Position feedback on the selected foot lifts or lowers the ankle within motor limits.
            j=feet[which];z=float(d.geom_xpos[j,2])
            dofs=ctx.v[[2,3,4]] if which==0 else ctx.v[[11,12,13]]
            indices=[2,3,4] if which==0 else [11,12,13]
            jac=np.zeros((3,ctx.m.nv));mujoco.mj_jacGeom(ctx.m,d,jac,None,j)
            vec=jac[2,dofs]
            dz=min(0.,.005-z)
            out[indices]+=np.clip(push*vec*dz/(vec@vec+.00025),-.22,.22)
        action=np.r_[out,jaw]
        if live:
            if not ctx.step(action,'gather'):
                reason=ctx.reason;break
        else:
            d.ctrl[:]=prev if ctx.delay else action;prev=action
            if roll is not None:
                if roll.run(d, air, contact_guard=opts.get('branch_contact_guard', False), tilt_min=.63, max_x=.545):
                    reason='unsafe'
            else:
                for _ in range(ctx.standard):
                    mujoco.mj_step(ctx.m,d)
                    low=np.array([d.xpos[n,2]+(course.NUT_VERTICES@d.xmat[n,6:9]).min() for n in ctx.audit.nut])
                    air=np.where(low>.001,air+ctx.m.opt.timestep,0.)
                    worst_air=np.maximum(worst_air,air)
                    if min(d.xmat[ctx.trunk,8],1)<.63 or max(air)>=.02-1e-8 or d.qpos[ctx.root]>.545:
                        reason='unsafe';break
            if reason:break
        delta=d.xpos[ctx.audit.nut[1],:2]-d.xpos[ctx.audit.nut[0],:2]
        min_dist=min(min_dist,np.linalg.norm(delta))
        if stop_at_gap and min_dist<opts.get('stop_gap_m',.024) and min_dist>.0155:
            # Stop issuing driving commands at the first measured handoff distance.
            break
    xy=d.xpos[ctx.audit.nut,:2]
    dr=np.linalg.norm(xy[1]-xy[0])
    dirn=unit(xy[anchor]-xy[moving])
    distback=10
    front=[]
    for g in feet:
        foot=foot_points(ctx.m,d,g)[:,:2]
        support=(foot-xy[moving])@dirn
        face=foot[support>=support.max()-.003].mean(axis=0)
        elbow=xy[moving]-.007*dirn
        offset=face-elbow
        perp=np.array([-dirn[1],dirn[0]])
        side=np.abs((foot-elbow)@perp).min()
        distback=min(distback,np.linalg.norm(offset)+.7*max(0,offset@dirn))
    score=dr + .32*min(distback,.15) + .025*np.linalg.norm(d.qvel[part_offsets[moving]:part_offsets[moving]+2])
    if dr<=.026:score=dr-1
    if opts.get('stable_handoff'):
        delta=np.linalg.norm(xy[anchor]-np.asarray(ctx.initial[anchor][:2]))
        score+=.65*max(0.,delta-.008)
    if reason:score+=5
    return score,dr,distback,i+1,reason


def settle_pair(ctx,anchor,options):
    """Test backing away, pausing and turning until both objects stay still and feet clear."""
    nut=ctx.audit.nut; m=ctx.m
    feet=[m.geom(n+'_foot_collision').id for n in ('left','right')]
    qvel=[m.joint(n+'_free').dofadr[0] for n in ('nut_a','nut_b')]
    def candidate(act,backup,live=False):
        d=ctx.d if live else copy.copy(ctx.d)
        walker=ctx.walker if live else copy.copy(ctx.walker)
        if not live:walker.obs=walker.obs.copy();walker.previous_raw=walker.previous_raw.copy()
        prev=ctx.prev.copy()
        tail=22;worst_air=np.zeros(2);air=np.zeros(2)
        roll = None if live else branch_roll(ctx, options)
        for i in range(backup+tail):
            action=act if i<backup else (0.,0.,0.)
            output=walker.command(d.sensor('imu_ang_vel').data,-d.xmat[ctx.trunk,6:9],
                                  d.qpos[ctx.q],d.qvel[ctx.v],action)
            command=np.r_[output,OPEN]
            if live:
                if not ctx.step(command,'gather'):return None
            else:
                d.ctrl[:]=prev if ctx.delay else command;prev=command
                if roll is not None:
                    if roll.run(d, air, contact_guard=options.get('branch_contact_guard', False), tilt_min=.64, max_x=.545):
                        return None
                else:
                    for _ in range(ctx.standard):
                        mujoco.mj_step(m,d)
                        z=np.array([d.xpos[n,2]+(course.NUT_VERTICES@d.xmat[n,6:9]).min() for n in nut])
                        air=np.where(z>.001,air+m.opt.timestep,0.)
                        if max(air)>=.02-1e-8 or d.xmat[ctx.trunk,8]<.64 or d.qpos[ctx.root]>.545:return None
        xy=d.xpos[nut,:2]
        g=np.linalg.norm(xy[1]-xy[0])
        dist=min(np.linalg.norm(d.geom_xpos[feet,:2][:,None,:]-xy[None,:,:],axis=2).flat)
        vel=max(np.linalg.norm(d.qvel[v:v+3]) for v in qvel)
        if not (.016<=g<=options.get('handoff_max_m',.027)) or vel>.012 or dist<.045:return None
        if options.get('lateral_goal') and abs(xy[1,0]-xy[0,0])>options.get('lateral_goal_dx',.004):return None
        return abs(g-.021)+.1*max(0,.075-dist)+vel
    bank=[]
    for uv,ticks in product(((0.,0.,0.),(-.4,0.,0.),(-.4,-.26,0.),(-.4,.26,0.),
                         (-.55,.48,0.),(-.55,-.48,0.),(0.,.47,0.),(0.,-.47,0.),
                         (.22,.45,0.),(.22,-.45,0.)),(18,38)):
        score=candidate(uv,ticks)
        if score is not None:bank.append((score,uv,ticks))
    if not bank:return None
    score,uv,ticks=min(bank)
    candidate(uv,ticks,True)
    return dict(command=uv,ticks=ticks,objective=float(score))


def gather(ctx,options):
    start=ctx.time;history=[];last=None;stalled=0
    feet=[ctx.m.geom(n+'_foot_collision').id for n in ('left','right')]
    a=ctx.d.xpos[ctx.audit.nut,:2]
    anchor=int(np.argmax(np.linalg.norm(a-np.asarray(ctx.xy),axis=1)))
    if options.get('swap_anchor'):anchor=1-anchor
    if 'anchor' in options:anchor=options['anchor']
    horizon=options.get('horizon',30)
    report=lambda ok,msg:dict(success=ok,reason=msg,history=history,elapsed=ctx.time-start)
    for turn in range(options.get('turns',120)):
        if ctx.reason:return report(False,ctx.reason)
        pts=ctx.d.xpos[ctx.audit.nut,:2]
        g=np.linalg.norm(pts[1]-pts[0]);mov=1-anchor
        if options.get('stable_handoff') and g<.056:
            retreat=settle_pair(ctx,anchor,options)
            if retreat:
                history.append(dict(t=ctx.time,withdraw=retreat))
                return report(not ctx.reason,ctx.reason or 'stable_pair')
        if not options.get('stable_handoff') and g<=options.get('stop_gap_m',.024) and g>=.015:
            return report(True,'near_pair')
        # Intentional path to approach from behind, scored with predicted pushes if contact occurs.
        direction=unit(pts[anchor]-pts[mov])
        flank=np.array([-direction[1],direction[0]])
        eye=pts[mov]-.027*direction
        foot=min(range(2),key=lambda j:np.linalg.norm(ctx.d.geom_xpos[feet[j],:2]-eye))
        offset=eye-ctx.d.geom_xpos[feet[foot],:2]
        aim=unit(offset)
        forward=float(aim@direction);side=float(aim@flank)
        if last is not None and g>=last-.0001:stalled+=1
        else:stalled=0
        last=g
        trial=[]
        gain=options.get('command_gain',1.)
        for amp in (.25,.55):
            trial.extend([(amp*forward,amp*side,0,0,foot),(amp,0,0,0,foot)])
        for amp,side,push in product((.30,.60),(-.22,0.,.22),(0,1.)):
            trial.append((amp,side,0.,push,foot))
        for slope in (-.6,.6):
            trial.extend([(.15,slope,0.,1.,foot),(.16,0,slope,0.,foot)])
        trial.extend([(-.24,-.1,0,0.,foot),(-.24,.1,0,0.,foot)])
        trials=[]
        for u,v,r,pressure,which in trial:
            act=(u*gain,v*gain,r,pressure,which)
            branch=copy.copy(ctx.d);walk=copy.copy(ctx.walker)
            walk.obs=ctx.walker.obs.copy();walk.previous_raw=ctx.walker.previous_raw.copy()
            s=advance(ctx,branch,walk,ctx.prev.copy(),act,'branch',anchor,horizon,False,stop_at_gap=(not options.get('stable_handoff') or g>.028))
            trials.append((s[0],s[1],s[2],s[3],act,s[4]))
        selected=min(trials,key=lambda s:s[0])
        if selected[-1]:return report(False,'no_safe_command')
        s=advance(ctx,ctx.d,ctx.walker,ctx.prev,selected[4],'live',anchor,selected[3],True,stop_at_gap=(not options.get('stable_handoff') or g>.028))
        history.append(dict(t=round(ctx.time,3),distance=g,end=s[1],goal_distance=s[2],action=selected[4]))
        if options.get('verbose'):print(history[-1],flush=True)
        if stalled>12 and s[2]>.08:
            anchor=1-anchor;stalled=0
        if ctx.time-start>options.get('timeout',95):break
    return report(False,'gather_timeout')


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    from episode import GroundContext,settings,parameters
    from runner import result
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=51010061)
    p.add_argument('--options',default='{}');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--trace',action='store_true');p.add_argument('--layout',default='S0')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    opts=json.loads(a.options)
    ctx=GroundContext((a.seed,a.layout,0,parameters(),settings()|dict(gather_options=opts),a.out/'trace.npz' if a.trace else None));ctx.settle()
    o=gather(ctx,opts);ctx.details['gather']=o;ctx.reason=o['reason']
    (a.out/'result.json').write_text(json.dumps(result(ctx),indent=2)+'\n')
    print(ctx.reason,ctx.time,o['history'][-1] if o['history'] else None)
