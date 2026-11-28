"""Paired fixed sliding-coefficient comparison on the unchanged 2.5 m track."""
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch
import csv
import hashlib
import json
import os
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
PILOT = HERE.parents[1] / 'pingpong-dual16-mu-pilot-20261128'
sys.path.insert(0, str(PILOT))
import contact_pairs as cp
import friction_pilot as old
sys.path.insert(0, str(cp.ROOT / 'training'))
import study
import actors

N = 144
START = 17640000
OPENED = 12600381
VALUES = (.224, .272, .32, cp.HISTORIC, .392, .404, .416)
ARMS = {f'fixed-{mu:.6f}':mu for mu in VALUES}
ARMS.update(wide=None, top_band=None)
MAX_ARM = 'fixed-0.416000'
RECIPE = dict(mode='fixed', cruise=.44, ramp=.44, wait=.18)


def save(name, data):
    dest = HERE / name
    tmp = dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(dest)


@contextmanager
def material(arm):
    if arm == 'wide':
        with cp.surface('wide') as info:
            yield info
        return
    mode, centre, hw = ('historic', .411, .005) if arm=='top_band' else ('historic_fixed', ARMS[arm], 0.)
    with patch.object(cp, 'HISTORIC', centre), cp.surface(mode, halfwidth=hw) as info:
        yield info


def run_case(args):
    policy, seed, track, arm = args
    native_observe = cp.st.Meter.observe
    physical = {'both_2s': False, 'half_m': False}

    def observe(meter, t, distance, fail, on, audit, controller):
        native_observe(meter, t, distance, fail, on, audit, controller)
        if meter.valid and on and distance >= .5:
            physical['half_m'] = True
        if abs(t-2.) < 1e-8:
            physical['both_2s'] = bool(meter.valid and on)

    with material(arm) as info, patch.object(cp.st.Meter, 'observe', observe):
        if policy == 'teacher':
            out = cp.transfer.run(track, seed, old.TEACHER['scale'], actions=old.TEACHER['actions'])
            torque = out['torque_nm']
        else:
            assert track=='combined' and policy=='medium'
            params=actors.configured(study.BASE['params'], RECIPE)
            with actors.controller(RECIPE, study.BASE['settings']):
                out=cp.st.run(track,seed,params,timeout=45.)
            torque=max(out['motor']['peak_nm'])
    assert torque<=.200001
    return dict(policy=policy,seed=seed,track=track,arm=arm,mu_A=info[cp.NAMES[0]][1],
                mu_B=info[cp.NAMES[1]][1],**physical,alive_2s=out['seconds']>2.,
                last_both_m=out['last_both_m'],flat=out['flat_1m'],slope=out['slope_1m'],
                finish=out['finish_2p5'],seconds=out['seconds'],reason=out['reason'],
                peak_torque_nm=torque)


def summarize(rows):
    groups={arm: sorted((r for r in rows if r['arm']==arm),key=lambda r:r['seed']) for arm in ARMS}
    seed_range=list(range(START,START+N))
    for arm,rr in groups.items():
        assert [r['seed'] for r in rr]==seed_range
        if arm.startswith('fixed-'):
            assert all(r['mu_A']==r['mu_B']==ARMS[arm] for r in rr)
        if arm=='top_band':
            assert all(.406-1e-12<=r[k]<=.416+1e-12 for r in rr for k in ['mu_A','mu_B'])
    distances={arm:np.array([r['last_both_m'] for r in rr]) for arm,rr in groups.items()}
    boot=np.random.default_rng(291601).integers(0,N,(10000,N))
    out={}
    for arm,rr in groups.items():
        d=distances[arm]
        result=dict(n=N,mean_m=d.mean(),median_m=np.median(d),p90_m=np.quantile(d,.9),max_m=d.max(),
                    longest_seed=rr[int(d.argmax())]['seed'])
        for key in ('alive_2s','both_2s','half_m','flat','slope','finish'):
            result[key]=sum(r[key] for r in rr)
        for label in ('wide',MAX_ARM):
            delta=1000*(d-distances[label])
            result['paired_diff_mm_vs_'+label]=dict(mean=delta.mean(),ci95=np.quantile(delta[boot].mean(axis=1),[.025,.975]).tolist())
        out[arm]=result
    return out


def main():
    save('protocol.json',dict(seed_start=START,n=N,opened=OPENED,arms=ARMS,policies=['teacher','medium'],
            primary='strict release-aligned combined 2.5 m, independent random starts',
            comparison='one shared seed per arm and policy; paired bootstrap percentile 95% for mean last simultaneous contact progress',
            band='top_band affinely maps original effective [0.224,0.416] onto [0.406,0.416]',
            endpoints='2.00 seconds with both touching and no veto; >2s survival separate; half metre requires contact on that step; 2.5m finish requires 1s parked',
            frozen_teacher_sha256=hashlib.sha256(old.TEACHER_FILE.read_bytes()).hexdigest(),
            medium=RECIPE))
    opened=[run_case(('teacher',OPENED,'fixed',arm)) for arm in ARMS]
    assert next(r for r in opened if r['arm']=='wide')['last_both_m']==1.4344716654053211
    save('opened.json',opened)
    print('opened', [(r['arm'], round(r['last_both_m'],3)) for r in opened],flush=True)
    summaries={}
    for policy in ('teacher','medium'):
        jobs=[(policy,seed,'combined',arm) for seed in range(START,START+N) for arm in ARMS]
        with ProcessPoolExecutor(int(os.environ.get('MICRODUCK_SWEEP_WORKERS','6'))) as pool:
            rows=list(pool.map(run_case,jobs,chunksize=4))
        with (HERE/f'{policy}-paired.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
        summaries[policy]=summarize(rows)
        save('summary.json',summaries)
        for arm, r in summaries[policy].items():
            print(policy,arm,round(r['mean_m'],4),r['both_2s'],r['half_m'],r['flat'],r['finish'],flush=True)


if __name__=='__main__':main()
