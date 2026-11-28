"""Compare each low-selected schedule on the identical opened seed under three coefficients."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
import argparse
import extend as x
import develop as d

def test(job):
    label,r,mu,enabled=job
    spec=d.e.NS['spec']
    config=deepcopy(spec['params'])
    if 'settle' in r:config['settle_s']=r['settle']
    d.e.NS['spec']={'params':config}
    try:
        with d.surface(mu) as pairs:
            out=d.e.run('combined',r['seed'],r['scale'],actions=x.schedule(r) if enabled else (d.ARCHIVE if r.get('base')=='teacher' else []))
    finally:d.e.NS['spec']=spec
    return dict(schedule=label,seed=r['seed'],settle_s=config.get('settle_s',1.0),named_material=mu,pairs=pairs,
                low_trained_pulses=enabled,flat_1m=out['flat_1m'],last_both_m=out['last_both_m'],seconds=out['seconds'],
                slope_1m=out['slope_1m'],finish=out['finish_2p5'],gates=out['gates'],reason=out['reason'])
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('cases',nargs='+')
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    jobs=[]
    for filename in args.cases:
        data=x.read(d.HERE/filename)
        row=data.get('winner',data.get('best',data))
        jobs.extend((filename,row,mu,pulse) for mu in ('low','nominal','high') for pulse in (False,True))
    with ProcessPoolExecutor(3) as pool:rows=list(pool.map(test,jobs))
    d.save(d.HERE/args.out,rows)
    print([(r['schedule'],r['named_material'],r['low_trained_pulses'],round(r['last_both_m'],4)) for r in rows])
if __name__=='__main__':main()
