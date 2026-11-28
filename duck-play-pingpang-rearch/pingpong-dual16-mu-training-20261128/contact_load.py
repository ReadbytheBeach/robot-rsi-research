"""Estimate measured tangential force utilization from actual 500 Hz solver contacts."""
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch
import mujoco
import numpy as np
from material import HERE, RECIPE, save, study, surface
from motors import MotorAudit


def run(job):
    seed,material=job
    samples=[]
    step=MotorAudit.step
    def observe(audit,n=10):
        d=audit.d
        face,_,a,b=audit.geom_ids[3:]
        for _ in range(n):
            step(audit,1)
            for i,con in enumerate(d.contact):
                if con.efc_address<0 or con.dist>0 or face not in con.geom or not (a in con.geom or b in con.geom):
                    continue
                f=np.zeros(6)
                mujoco.mj_contactForce(audit.m,d,i,f)
                if f[0]<=1.e-5:continue
                samples.append((float(np.hypot(f[1],f[2])/(con.friction[0]*f[0])),float(f[0]),con.friction[0]))
    with surface(material),patch.object(MotorAudit,'step',observe):
        r=study.episode(('medium',RECIPE,'combined',seed,None,None))
    z=np.array(samples);assert len(z) and np.allclose(z[:,2],.416 if material=='high' else .32)
    return dict(seed=seed,material=material,points=len(z),near_limit=int(np.sum(z[:,0]>=.9)),
                median_ratio=float(np.median(z[:,0])),p90_ratio=float(np.quantile(z[:,0],.9)),
                distance=r['last_both_m'],flat=r['flat_1m'],finish=r['finish_2p5'])


if __name__=='__main__':
    with ProcessPoolExecutor(3) as pool:
        rows=list(pool.map(run,[(s,m) for s in range(17276000,17276016) for m in ('nominal','high')]))
    out={}
    for m in ('nominal','high'):
        arm=[r for r in rows if r['material']==m]
        out[m]=dict(n=len(arm),samples=sum(r['points'] for r in arm),fraction_near_limit=sum(r['near_limit'] for r in arm)/sum(r['points'] for r in arm),
                    median_of_run_medians=float(np.median([r['median_ratio'] for r in arm])))
    save(HERE/'contact-load.json',dict(arms=out,rows=rows,normal_force_filter_N=1e-5))
