"""Check solver contact parameters and tangential load and slip at the contact point."""
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch
import mujoco
import numpy as np

from sweep import ARMS, MAX_ARM, OPENED, START, cp, run_case, save
from motors import MotorAudit


def audit(job):
    policy,seed,track,arm=job
    old=MotorAudit.step
    observed={}
    steps=0
    settings={}

    def sample(audit,n=10):
        nonlocal steps
        m,d=audit.m,audit.d
        face,a,b=[m.geom(k).id for k in ('paddle_face',*cp.NAMES)]
        pairs={frozenset([face,a]):'A_face',frozenset([face,b]):'B_face',frozenset([a,b]):'A_B'}
        for _ in range(n):
            old(audit,1)
            steps+=1
            for i in range(d.ncon):
                c=d.contact[i]; g1,g2=int(c.geom1),int(c.geom2)
                name=pairs.get(frozenset([g1,g2]))
                if not name or c.dist>0 or c.efc_address<0:
                    continue
                base=np.maximum(m.geom_friction[g1],m.geom_friction[g2])
                if name=='A_B' or arm=='wide':
                    expected=base[0]
                elif arm=='top_band':
                    expected=.411+.005*(base[0]-.32)/.096
                else:
                    expected=ARMS[arm]
                assert np.array_equal(c.friction,[expected,expected,base[1],base[2],base[2]])
                assert np.array_equal(c.solref,np.array([.006,.68]))
                assert c.dim==6
                cfg=dict(friction5=c.friction.tolist(),solref=c.solref.tolist(),solimp=c.solimp.tolist())
                if name in settings:assert settings[name]==cfg
                settings[name]=cfg
                forces=np.zeros(6);mujoco.mj_contactForce(m,d,i,forces)
                if forces[0]<=.00001:continue
                velocities=[]
                for geom in (g1,g2):
                    v=np.zeros(6)
                    mujoco.mj_objectVelocity(m,d,mujoco.mjtObj.mjOBJ_GEOM,geom,v,0)
                    velocities.append(v[3:]+np.cross(v[:3],c.pos-d.geom_xpos[geom]))
                tangent=(c.frame.reshape(3,3)@(velocities[0]-velocities[1]))[1:]
                observed.setdefault(name,[]).append([steps,np.linalg.norm(tangent),forces[0],np.linalg.norm(forces[1:3])])
    with patch.object(MotorAudit,'step',sample):
        out=run_case(job)
    result={}
    for name, readings in observed.items():
        time_step,v,fn,ft=np.array(readings).T
        mu=settings[name]['friction5'][0]
        result[name]=dict(**settings[name],n_loaded=len(v),median_slip_mmps=1000*np.median(v),
                p90_slip_mmps=1000*np.quantile(v,.90),frac_slip_over_1mmps=float(np.mean(v>.001)),
                normal_force_mN_mean=1000*fn.mean(),tangential_force_mN_mean=1000*ft.mean(),
                frac_tangential_near_scalar_bound=float(np.mean(ft/(mu*fn)>=.95)))
        first=time_step<=100
        if first.any():
            result[name]['first_200ms'] = dict(n_loaded=int(first.sum()), mean_normal_mN=1000*fn[first].mean(),
                    mean_tangential_mN=1000*ft[first].mean(),mean_scalar_bound_mN=1000*mu*fn[first].mean(),
                    near_bound_fraction=float(np.mean(ft[first]/(mu*fn[first])>=.95)),p90_slip_mmps=1000*np.quantile(v[first],.9))
    assert 'A_face' in result and 'B_face' in result
    return dict(row=out,physics_steps=steps,observations=result)


def main():
    jobs=[('teacher',OPENED,'fixed',arm) for arm in ARMS]
    jobs += [('teacher',s,'combined',arm) for s in range(START,START+12)
             for arm in ('wide',MAX_ARM,'fixed-0.320000','fixed-0.224000','top_band')]
    with ProcessPoolExecutor(3) as pool:
        runs=list(pool.map(audit,jobs,chunksize=1))
    for r in runs:
        if r['row']['seed']==OPENED and r['row']['arm']=='wide':
            assert r['row']['last_both_m']==1.4344716654053211 and 'A_B' in r['observations']
    save('contact-audit.json',dict(dt=.002,load_min_n=.00001,checks='actual solver contacts including A–B; original twisting/rolling/normal; force and relative tangential velocity on loaded contacts',
                definitions='norm of 2D tangential force divided by mu*normal force is a scalar ceiling comparison, ignoring torsional and rolling loads. '
                            'Slip is the relative contact point velocity projected on the instantaneous tangent plane, sampled post-solve each 2ms.',
                runs=runs))
    for r in runs[:len(ARMS)]:
        a=r['observations']['A_face'];print(r['row']['arm'],a['friction5'],a['p90_slip_mmps'],a['frac_tangential_near_scalar_bound'],flush=True)


if __name__=='__main__':main()
