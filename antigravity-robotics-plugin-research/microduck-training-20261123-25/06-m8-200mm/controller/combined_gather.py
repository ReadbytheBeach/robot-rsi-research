"""Rehearse bounded near-station alternatives then issue motor targets once on the live robot."""
import copy
import importlib
import time
import numpy as np

import episode
from audit200 import GapWitness
from align_pair import align


def clone(ctx, record=True):
    """Copy only for prediction. No setter in this module writes source poses or velocities."""
    branch=copy.copy(ctx)
    branch.d=copy.copy(ctx.d)
    branch.step=episode.GroundContext.step.__get__(branch,episode.GroundContext)
    branch.trace=None
    branch.prev=ctx.prev.copy()
    branch.config=copy.deepcopy(ctx.config)
    branch.audit=episode.course.Audit(ctx.m,branch.d,accelerated=True)
    branch.dual=episode.dual.Witness(branch.audit)
    branch.gap=GapWitness(branch)
    for key in ('settled_distance','settled_xy','floor_streak','air_streak'):
        setattr(branch.gap,key,copy.deepcopy(getattr(ctx.gap,key)))
    branch.gap.initial_xy=ctx.gap.initial_xy.copy()
    for name in ('walker','stand'):
        policy=copy.copy(getattr(ctx,name))
        policy.obs=policy.obs.copy();policy.previous_raw=policy.previous_raw.copy()
        setattr(branch,name,policy)
    branch.details={};branch.commands=[]
    if record:
        step=branch.step
        def capture(action,stage='gather',*args,**kwargs):
            good=step(action,stage,*args,**kwargs)
            if good:branch.commands.append((np.asarray(action).copy(),stage))
            return good
        branch.step=capture
    return branch


def finish(ctx,branch,entry):
    for action,phase in branch.commands:
        if not ctx.step(action,phase):
            return False
    ctx.walker.obs[:]=branch.walker.obs
    ctx.walker.previous_raw=branch.walker.previous_raw.copy()
    ctx._gathered_entry=entry
    return True


def gather(ctx,options):
    start=time.process_time()
    cases=options.get('branches',[
        {'horizon':28,'turns':80,'stable_handoff':True},
        {'horizon':20,'turns':115,'stable_handoff':True},
        {'horizon':36,'turns':70,'stable_handoff':True},
    ])
    reports=[]
    for index,case in enumerate(cases):
        branch=clone(ctx)
        opts=case.copy();module=opts.pop('module','mpc_foot')
        branch.config['gather_options']=opts
        r=importlib.import_module(module).gather(branch,opts)
        gap=float(np.linalg.norm(np.diff(branch.d.xpos[branch.audit.nut,:2],axis=0)))
        item=dict(candidate=index,method=module,ground_result=r.get('reason'),gap_m=gap,ground_s=round(branch.time,3))
        reports.append(item)
        if branch.reason or not r.get('success'):continue
        entry=align(branch,ctx.params,ctx.config)
        item['align_result']=branch.reason or ('ready' if entry else 'timeout')
        if entry is None or branch.reason:continue
        ok=finish(ctx,branch,entry)
        delta=float(np.max(np.abs(ctx.d.qpos-branch.d.qpos)))
        if delta>1e-8:
            return dict(success=False,reason='predicted_motor_replay_mismatch',error=delta,cases=reports)
        return dict(success=ok,reason=ctx.reason or 'qualified_near_station',selected=index,
                    max_replay_qpos_error=delta,teacher_cpu_s=time.process_time()-start,cases=reports)
    return dict(success=False,reason='no_safe_gather_and_alignment',cases=reports,
                teacher_cpu_s=time.process_time()-start)

