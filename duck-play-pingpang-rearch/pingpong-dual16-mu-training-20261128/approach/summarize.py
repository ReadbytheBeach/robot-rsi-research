"""Read all closed runs and verify the last recorded simultaneous physical contact."""
from pathlib import Path
import json
import numpy as np
from search import HERE,SHORT,read,save


def dual_frame(folder):
    meta=read(folder/'trajectory.json')
    with np.load(folder/'trajectory.npz') as z:
        t=z['t']; ok=z['ball_contacts'].all(axis=1)
        if not meta['success']:ok &= t<meta['seconds']-1e-10
        def last(mask):
            i=np.flatnonzero(mask)[-1];m=float(z['progress_m'][i]);world=m+meta['initial_x_m']
            slope=float(np.clip(world-1.02,0.,1.)) if folder.name not in ('primary','primary-continuation') else float(np.clip(m-1.,0.,1.))
            return dict(t=float(t[i]),m=m,slope_m=slope,radii_mm=(1000*z['ball_radii'][i]).tolist())
        dual=last(ok);strict=last(ok&(z['ball_radii'].max(axis=1)<=.055))
    assert abs(dual['m']-meta['last_both_m'])<1e-10
    return {'last_dual':dual,'both_centered':strict,'terminal':meta['reason'],'gates':meta['gates'],
            'seconds':meta['seconds'],'tilt_peak_deg':meta['max_tilt_deg'],'torque_peak_nm':max(meta['motor']['peak_nm']),
            'terminal_x':meta['final_x_m']}


def main():
    outputs={}
    for name in ('record','record-continuation','high','high-continuation','high-catch','orientation','slope-entry','slope-entry-tilt','primary','primary-continuation'):
        folder=HERE/name
        if not (folder/'result.json').is_file():continue
        res=read(folder/'result.json')
        val=dual_frame(folder);val['trials']=res['branches'];val['rate']=read(folder/'fresh.json') if (folder/'fresh.json').is_file() else None
        val['initial_m']=(res['initial']['last_both_m'] if 'initial' in res else None)
        outputs[name]=val
    save(HERE/'audit.json',outputs)
    print([(s,z['trials'],round(z['last_dual']['m'],5)) for s,z in outputs.items()])

if __name__=='__main__':main()
