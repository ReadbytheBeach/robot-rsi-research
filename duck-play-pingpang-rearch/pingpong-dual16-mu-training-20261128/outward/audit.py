"""Check the offline outward grouping against actual released matter states and baseline parity."""
from unittest.mock import patch
import json
import numpy as np
import train as x

def measure(seed,name,policy):
    observed={}
    original=x.t.actors.ball.BallController.reset
    walk=x.t.actors.locomotion.Locomotion.control
    drive=[]
    def reset(bc,*args,**kw):
        r=original(bc,*args,**kw)
        poses=[];vs=[]
        for c in bc.channels:
            mat=bc.d.site_xmat[c.site].reshape(3,3)
            poses.append((mat.T@(bc.d.qpos[c.adr:c.adr+3]-bc.d.site_xpos[c.site]))[:2])
            vs.append((mat.T@bc.d.qvel[c.dof:c.dof+3])[:2])
        observed['bc']=bc
        observed['release']=x.groups.features(np.array(poses),np.array(vs),[.416,.416])['separation_rate_mm_s']
        return r
    def record(w,d,speed):
        mon=observed.get('bc')
        if mon is not None and mon.d is d and mon.tick<26:drive.append([.02*mon.tick,speed])
        return walk(w,d,speed)
    with patch.object(x.t.actors.ball.BallController,'reset',reset),patch.object(x.t.actors.locomotion.Locomotion,'control',record):
        r=x.run(seed,name,policy)
    return r,observed['release'],drive

def main():
    protocol=json.loads((x.HERE/'protocol.json').read_text());frozen=json.loads((x.HERE/'frozen.json').read_text())
    rows=[]
    for spec in protocol['curriculum'][:4]+protocol['hard'][:3]:
        s=spec['seed']
        b,rad,bw=measure(s,'phase_08',None)
        raw=x.t.run_seed(s,'high','phase_08')
        assert (raw['m'],raw['both2'],raw['t'],raw['flat'])==(b['m'],b['both2'],b['t'],b['flat'])
        f,rad2,fw=measure(s,frozen['winner'],frozen['parameters'])
        assert abs(rad-rad2)<1e-10 and abs(rad-spec['offline_release_radial_mm_s'])<1e-10
        rows.append(dict(seed=s,offline_radial=spec['offline_release_radial_mm_s'],native_radial=rad,
                         baseline_drive=bw,frozen_drive=fw,first_trigger_s=f['trigger_s']))
    x.store('audit.json',dict(frozen=frozen['winner'],verified=rows))
    print('actual release and unmodified phase08 parity',len(rows))
if __name__=='__main__':main()
