"""Compare empty-paddle settling time before the usual physical release."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import csv
import json
import numpy as np
import develop as d


def trial(job):
    seed,settle,scale,extra=job
    params=deepcopy(d.e.BASE)
    params['settle_s']=settle
    saved=d.e.NS['spec']
    d.e.NS['spec']={'params':params}
    try:
        with d.surface('low'):r=d.e.run('combined',seed,scale,actions=extra)
    finally:d.e.NS['spec']=saved
    return dict(seed=seed,settle=settle,scale=scale,extra=extra,flat=r['flat_1m'],slope=r['slope_1m'],finish=r['finish_2p5'],
                m=r['last_both_m'],s=r['seconds'],why=r['reason'],tilt=r['max_tilt_deg'],torque=r['torque_nm'])


def replay(best):
    params=deepcopy(d.e.BASE);params['settle_s']=best['settle']
    saved=d.e.NS['spec'];d.e.NS['spec']={'params':params}
    try:
        with d.surface('low'):
            r=d.e.run('combined',best['seed'],best['scale'],actions=best['extra'],trace=d.HERE/'prepared-low.npz')
            b=d.e.run('combined',best['seed'],best['scale'],actions=[])
    finally:d.e.NS['spec']=saved
    assert r['last_both_m']==best['m']
    return r,b


def main():
    seeds=set(json.loads(d.KNOWN.read_text())['seeds'])
    file=d.SHORT/'training/enrichment/physical.csv'
    with file.open() as f:
        rows=sorted([r for r in csv.DictReader(f) if r['track']=='combined' and int(r['seed']) in seeds],key=lambda r:-float(r['last_both_m']))
    subset=list(dict.fromkeys(int(r['seed']) for r in rows))[:18]
    settles=[.54,.82,1.18,1.46,1.76]
    scales=[1.,1.15]
    d.save(d.HERE/'prep-protocol.json',dict(seeds=subset,basis='top 18 prior physical records on primary track from the 358 allowed starts',
      empty_paddle_stationary_seconds=settles,scale=scales,release='preserve original ball release offsets/velocities/latent draws, scored origin established only after empty paddle settles'))
    with ProcessPoolExecutor(4) as pool:
        initial=list(pool.map(trial,[(s,t,k,[]) for s in subset for t in settles for k in scales],chunksize=3))
        d.save(d.HERE/'prep-initial.json',initial)
        beam=d.different(initial,4,True);best=beam[0];hist=[]
        for layer in range(10):
            rng=np.random.default_rng(217300+layer);jobs=[]
            for r in beam:
                for j in range(8):
                    act=d.pulse(r,rng,j+layer,layer)
                    jobs.append((r['seed'],r['settle'],r['scale'],r['extra']+[act]))
            vals=list(pool.map(trial,jobs,chunksize=2));candidates=sorted([*beam,*vals],key=d.key,reverse=True)
            beam=d.different(candidates,3)
            alternate=next((r for r in candidates if all(r['seed']!=p['seed'] for p in beam)),None)
            if alternate:beam.append(alternate)
            best=beam[0]
            hist.append(dict(layer=layer,seed=best['seed'],m=best['m'],s=best['s'],n=len(vals)))
            print('prep',hist[-1],flush=True);d.save(d.HERE/'prep-history.json',hist)
            if best['finish']:break
    r,b=replay(best)
    d.save(d.HERE/'prep-result.json',dict(initial=len(initial),branches=sum(r['n'] for r in hist),winner=best,verified=r,initial_same_start=b))


if __name__=='__main__':main()
