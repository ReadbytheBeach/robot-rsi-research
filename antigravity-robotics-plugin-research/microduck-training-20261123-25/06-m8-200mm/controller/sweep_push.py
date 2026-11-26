"""Learn displacement from short open-jaw sweeps; only motor targets move the live bodies."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import copy
import json
from pathlib import Path
import sys
import numpy as np
import mujoco

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import episode
from align_pair import vector,wrap
from episode import course


class Sweep:
    def __init__(self, m, d, params, mode):
        self.pick=course.NutPickController(m,d,params)
        self.mode=mode
        self.st=d.time

    def step(self,d):
        target=self.pick.step(d)
        t=d.time-self.st
        phase,amplitude,head=self.mode
        rise=np.clip((t-phase)/.38,0,1)
        recover=np.clip((2.45-t)/.55,0,1)
        target[7]+=amplitude*rise*recover
        target[6]+=head*rise*recover
        target[-1]=course.OPEN
        return target


def short_sim(ctx,params,mode,horizon=3.8,trace=False):
    model=ctx.m;d=copy.copy(ctx.d)
    audit=course.Audit(model,d,accelerated=True)
    previous=ctx.prev.copy();ctrl=Sweep(model,d,params,mode)
    nut0=d.xpos[audit.nut,:2].copy();air=np.zeros(2);actions=[]
    for i in range(round(horizon/.02)):
        action=ctrl.step(d)
        if trace:actions.append(action)
        d.ctrl[:]=previous if ctx.delay else action
        previous=action
        for _ in range(round(.02/model.opt.timestep)):
            mujoco.mj_step(model,d)
            audit.sample('gather',[])
            if audit.problem: return None
            air=np.where(audit.z>.001,air+model.opt.timestep,0.)
            if max(air)>=.02-1e-8: return None
    return d.xpos[audit.nut,:2].copy()-nut0,actions


def calibrate(job):
    i,x,y,mode,delay=job
    # Development primitive from an actual 200 mm pair; only the calibration position varies.
    import functools
    cfg=episode.settings();params=episode.parameters()
    other=np.array([x+.2,y])
    ctx=episode.GroundContext((910101,'S0',delay,params,cfg,None),diagnostic_xy=[[x,y],other])
    ctx.settle()
    r=short_sim(ctx,params,mode)
    return {'i':i,'x':x,'y':y,'mode':mode,'delay':delay,'delta':None if r is None else r[0][0].tolist()}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args()
    jobs=[]
    for x in (.055,.068,.078,.088,.099,.11,.12):
        for y in (-.043,-.032,-.016,0,.016,.032,.043):
            for mode in [(0,0,0),(.78,.55,0),(.78,-.55,0),(.88,.8,.07),(.88,-.8,.07)]:
                jobs.append((len(jobs),x,y,mode,0))
    with ProcessPoolExecutor(a.workers) as pool,a.out.open('w') as output:
        for r in pool.map(calibrate,jobs,chunksize=1):
            output.write(json.dumps(r)+'\n');output.flush()
