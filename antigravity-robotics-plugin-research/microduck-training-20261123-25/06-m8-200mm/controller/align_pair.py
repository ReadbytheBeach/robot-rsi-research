"""Align the actual walking robot to a gathered pair, then screen a single physical bite."""
import copy
import math
from pathlib import Path
import sys

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import course


def wrap(angle):
    return (angle + np.pi) % (2 * np.pi) - np.pi


def vector(heading):
    return np.array([math.cos(heading), math.sin(heading)])


def carry_preview(ctx, d, audit, previous, control, duration, config):
    """Screen slip and pivot from the predicted grasp using the original walking controller."""
    import episode
    plant=copy.copy(ctx)
    plant.d=d
    plant.config=config
    plant.released=[]
    plant.final_drift=0.
    plant.probes=0
    plant.stand=copy.copy(ctx.stand)
    plant.stand.obs=ctx.stand.obs.copy()
    plant.stand.previous_raw=ctx.stand.previous_raw.copy()
    plant.audit=audit
    plant.trace=None
    plant.prev=previous.copy()
    plant.routes=[]
    plant.reason=None
    plant.walker=copy.copy(ctx.walker)
    plant.walker.obs=ctx.walker.obs.copy()
    plant.walker.obs[0,34:48]=control.obs[0,34:48]
    plant.walker.previous_raw=previous[:14].copy()
    start=float(d.time)
    origin=d.qpos[ctx.root:ctx.root+2].copy()
    class StopPreview(Exception):
        pass
    approved=False
    def step(action,phase,ids=(),**kwargs):
        nonlocal approved
        check_finish=config.get('pair_align',{}).get('preview_finish',False)
        if not check_finish and phase!='cross':
            approved=True
            raise StopPreview()
        if d.time>=240. or d.time-start>=duration:
            approved=not check_finish and np.linalg.norm(d.qpos[ctx.root:ctx.root+2]-origin) > min(.24,duration*.045)
            raise StopPreview()
        d.ctrl[:]=plant.prev if plant.delay else action
        plant.prev=np.copy(action)
        n=max(8,ctx.standard) if kwargs.get('fine',False) else ctx.standard
        ctx.m.opt.timestep=.02/n
        audit.check_basket=kwargs.get('score_basket',False)
        for _ in range(n):
            mujoco.mj_step(ctx.m,d)
            audit.sample(phase,ids)
            if audit.problem:
                raise StopPreview()
        return True
    def event(name,*args):
        nonlocal approved
        if name=='place' and not config.get('pair_align',{}).get('preview_finish',False):
            approved=True
            raise StopPreview()
    plant.step=step
    plant.event=event
    timestep=ctx.m.opt.timestep
    try:
        episode.deliver(plant,previous)
        approved=plant.reason=='success'
    except StopPreview:
        pass
    finally:
        ctx.m.opt.timestep=timestep
    return approved


def preview(ctx, params, history, horizon):
    m, d = ctx.m, copy.copy(ctx.d)
    audit = course.Audit(m, d, accelerated=True)
    controller = course.NutPickController(m, d, params, history)
    previous = ctx.prev.copy()
    times = [None, None]
    airborne = np.zeros(2)
    longest = 0.
    for k in range(round(horizon/.02)):
        action = controller.step(d)
        d.ctrl[:] = previous if ctx.delay else action
        previous = action
        for _ in range(round(.02/m.opt.timestep)):
            mujoco.mj_step(m, d)
            audit.sample("pick", [])
            if audit.problem:
                return False
            for n in (0,1):
                airborne[n] = airborne[n] + m.opt.timestep if audit.z[n] > .001 else 0.
                if times[n] is None and airborne[n] >= .02-1e-7:
                    times[n] = float(d.time-airborne[n]+m.opt.timestep)
            longest = max(longest, float(min(audit.held)))
        if k >= 155 and longest + (horizon-.02*(k+1)) < 2.-1e-7:
            return False
    if None in times or abs(times[0]-times[1]) > .0200001 or min(audit.held) < 2.-1e-7:
        return False
    duration=ctx.config.get("pair_align",{}).get("carry_preview_s",0.)
    if not duration:
        return 'original'
    from transport_variants import variants
    for tag, cfg in variants(ctx.config):
        if tag!='original' and not ctx.config.get('pair_align',{}).get('transport_variants',False):
            break
        plant=copy.copy(d)
        checker=course.Audit(m,plant,accelerated=True)
        checker.mouth_force[:]=audit.mouth_force
        checker.held[:]=audit.held
        checker.best[:]=audit.best
        if carry_preview(ctx,plant,checker,previous,controller,duration,cfg):
            return tag
    return False


def align(ctx, params, settings):
    if getattr(ctx,"_gathered_entry",None) is not None:
        return ctx._gathered_entry
    config = settings.get("pair_align", {})
    start = float(ctx.d.time)
    root = ctx.m.joint("trunk_base_freejoint").qposadr[0]
    ids = ctx.audit.nut
    bank = [params] + [params | q for q in settings.get("first_preview",{}).get("alternatives",[])]
    state = ctx.d.qpos
    candidate_count = 0
    last_scan = -10.
    chosen_sign = None
    errors = []
    max_time = config.get("limit_s", 38.)
    while float(ctx.d.time)-start < max_time and not ctx.audit.problem:
        xy = state[root:root+2]
        observed = ctx.d.xpos[ids,:2]
        midpoint = observed.mean(axis=0)
        width = observed[1]-observed[0]
        yaw = course.forward_yaw(state[root+3:root+7])
        normal = math.atan2(width[1],width[0]) - np.pi/2
        if chosen_sign is None:
            scores = []
            for flip in (0,1):
                heading = normal+np.pi*flip
                goal = midpoint - .083*vector(heading)
                scores.append(np.linalg.norm(goal-xy)+.055*abs(wrap(heading-yaw))+.035*abs(wrap(heading)))
            chosen_sign=int(np.argmin(scores))
        heading=normal+np.pi*chosen_sign
        forward=vector(yaw); side=np.array([-forward[1],forward[0]])
        dx,dy=float((midpoint-xy)@forward),float((midpoint-xy)@side)
        age=float(ctx.d.time)-start
        # Slightly vary approach distance when exact foot phase or head pitch vetoes a bite.
        reach=[.082,.078,.086,.080,.084][int(age/3.2)%5]
        target=midpoint-reach*vector(heading)
        e=target-xy
        yaw_error=wrap(heading-yaw)
        if abs(dx-.082)<.013 and abs(dy)<.012 and abs(yaw_error)<.37 and age-last_scan>=.20:
            last_scan=age
            history=ctx.walker.obs[0,34:48].copy()
            candidates = [dict(q) for q in bank]
            gain_yaw = float(np.clip(6*dy, -.10,.10))
            gain_head = float(np.clip(4*(dx-.082),-.085,.085))
            candidates += [q | dict(bite_yaw=q.get("bite_yaw",0.)+gain_yaw,
                                    head=q["head"]+gain_head) for q in bank[:2]]
            for p in candidates:
                candidate_count+=1
                preset=preview(ctx,p,history,settings.get("pick_s",5.08))
                if preset:
                    return dict(params=p,history=history,transport_preset=preset,elapsed_s=age,trials=candidate_count,
                                relative_xy=[dx,dy],heading_error=yaw_error)
        vx,vy=np.clip([5.*(e@forward),6.2*(e@side)],[-.25,-.28],[.30,.28])
        mag=max(abs(vx),abs(vy))
        if .003 < np.linalg.norm(e) < .065 and 1e-9<mag<.18:
            vx,vy=np.array([vx,vy])*.18/mag
        cmd=(vx,vy,np.clip(3*yaw_error,-.86,.86))
        target_angles=ctx.walk(cmd)
        if len(target_angles)==14:
            target_angles=np.r_[target_angles,course.OPEN]
        if not ctx.step(target_angles,"align"):
            break
        if int(age*50)%25==0:
            errors.append([round(age,2),round(dx,4),round(dy,4),round(yaw_error,3)])
    ctx.alignment_diagnostics={"candidates":candidate_count,"poses":errors}
    return None
