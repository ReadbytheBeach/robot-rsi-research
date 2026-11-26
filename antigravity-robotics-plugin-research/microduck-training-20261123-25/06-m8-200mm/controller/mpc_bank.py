"""Run physical branches from a common measured state, replay verified actuator commands."""
import copy
import itertools
import numpy as np

from episode import course,dual
from audit200 import GapWitness
import mpc_foot


def shadow(ctx):
    f=copy.copy(ctx)
    # A parent rollout may have recorded step() on its own instance.
    f.__dict__.pop("step",None)
    f.d=copy.copy(ctx.d)
    f.audit=course.Audit(f.m,f.d,accelerated=True)
    f.gap=GapWitness(f)
    for k in ('settled_xy','settled_distance','floor','floor_streak','air_streak'):
        setattr(f.gap,k,copy.deepcopy(getattr(ctx.gap,k)))
    f.gap.rows=None
    f.dual=dual.Witness(f.audit)
    f.walker=copy.copy(ctx.walker);f.walker.obs=ctx.walker.obs.copy();f.walker.previous_raw=ctx.walker.previous_raw.copy()
    f.stand=copy.copy(ctx.stand);f.stand.obs=ctx.stand.obs.copy();f.stand.previous_raw=ctx.stand.previous_raw.copy()
    f.prev=ctx.prev.copy()
    f.reason=None
    f.trace=None
    f.details={}
    return f


def gather(ctx,options):
    base=dict(horizon=28,turns=80,stable_handoff=True)|options
    presets=options.get('presets',[
        {},dict(horizon=21),dict(horizon=35),dict(horizon=28,command_gain=.76),
        dict(horizon=17),dict(horizon=34,command_gain=.83),dict(horizon=23,command_gain=1.16),
        dict(horizon=37,swap_anchor=True),dict(horizon=31,command_gain=1.24),
        dict(horizon=19,swap_anchor=True),dict(horizon=40),dict(horizon=24,command_gain=.67)])
    rows=[]
    for n,variant in enumerate(presets):
        c=shadow(ctx)
        cfg=base|variant
        c.config=ctx.config|dict(gather_options=cfg)
        commands=[]
        step=c.step
        def recorder(action,stage='gather'):
            commands.append(np.asarray(action).copy())
            return step(action,stage)
        c.step=recorder
        o=mpc_foot.gather(c,cfg)
        distance=float(np.linalg.norm(c.d.xpos[c.audit.nut[1],:2]-c.d.xpos[c.audit.nut[0],:2]))
        rows.append(dict(branch=n,t=round(c.time,4),reason=o['reason'],distance_m=distance))
        if not o['success']:continue
        for a in commands:
            if not ctx.step(a,'gather'):
                return dict(success=False,reason=ctx.reason,branches=rows)
        ctx.walker.obs[:]=c.walker.obs
        ctx.walker.previous_raw=c.walker.previous_raw.copy()
        error=float(np.max(np.abs(ctx.d.qpos-c.d.qpos)))
        if error>1e-7:
            return dict(success=False,reason='planned_gather_mismatch',qpos_error=error,branches=rows)
        return dict(success=True,reason='stable_pair',branches=rows,history=o['history'],
                    selected_variant=variant,qpos_error=error,steps=len(commands))
    return dict(success=False,reason='no_feasible_ground_plan',branches=rows)
