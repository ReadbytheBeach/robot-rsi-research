"""Continue fixed-grid double-contact trajectories using shared full physical prefix states."""
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import argparse
import json
import os
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
EXPS = HERE.parent.parent
PILOT = EXPS / 'pingpong-dual16-mu-pilot-20261128'
SHORT = EXPS / 'pingpong-dual16-short-20261128'
sys.path[:0] = [str(PILOT), str(SHORT/'diversity')]
import contact_pairs as cp
import viable_prefix as vp

SEED = 12600381
MATERIAL = {'record': cp.HISTORIC, 'high': .416}
BASES = {'record': SHORT/'replay/fixed-paced-seal.json', 'uphill': SHORT/'diversity/uphill/selected.json',
         'yaw': SHORT/'diversity/yaw_approach/selected.json','fixed':SHORT/'replay/fixed-selected.json'}


def read(path):
    return json.loads(path.read_text())


def save(path, info):
    tmp=path.with_suffix('.partial')
    tmp.write_text(json.dumps(info,indent=2,ensure_ascii=False)+'\n')
    tmp.replace(path)


@contextmanager
def material(mode):
    with patch.object(cp,'HISTORIC',MATERIAL[mode]), cp.surface('historic_fixed'):
        yield


def run(track, seed, actions, mode, trace=None):
    with material(mode):
        return cp.transfer.run(track,seed,1.,actions=actions,trace=trace)


def simulate(job):
    mode,seed,schedule,fork,trace=job
    with material(mode), patch.object(vp,'SEED',seed):
        return vp.simulate(schedule, fork=fork, trace=trace)


def bank(mode, level, slot):
    rng=np.random.default_rng(202982 + (73000 if mode=='high' else 0) + level*77+slot*11)
    rows=[None]
    for i in range(13):
        a=dict.fromkeys(('pitch','roll','damp','speed','neck','hip','lateral','yaw','span'),0.)
        a['duration']=float(rng.choice([.18,.30,.46,.70,.98,1.36,1.85]))
        if i<=3:
            a.update(speed=float(rng.uniform(-.32,.5)),yaw=float(rng.uniform(-.32,.32)),neck=float(rng.uniform(-.04,.04)))
        elif i<=7:
            a.update(style=['opening','intercept'][i%2],direction=float(rng.uniform(-.14,.14)),tangent=float(rng.uniform(-.14,.14)),
                     relative=float(rng.uniform(-1.4,1.4)),memory=float(rng.uniform(-.4,1.0)),yawphase=float(rng.uniform(-.55,.55)),
                     neckphase=float(rng.uniform(-.065,.065)),frequency=float(rng.choice([0,1.4,2.1])),speed=float(rng.uniform(-.13,.22)))
        elif i<=10:
            a.update(span=float(rng.uniform(-.2,.2)),yaw=float(rng.uniform(-.68,.68)),hip=float(rng.uniform(-.04,.04)),
                     damp=float(rng.uniform(-.25,.65)),speed=float(rng.uniform(-.18,.41)))
        else:
            a.update(pitch=float(rng.uniform(-.024,.024)),roll=float(rng.uniform(-.024,.024)),speed=float(rng.uniform(-.075,.2)),
                     yaw=float(rng.uniform(-.09,.09)))
        rows.append(a)
    return rows


def key(row):
    return row['finish_2p5'],row['slope_1m'],row['flat_1m'],row['last_both_m'] if row['max_tilt_deg']<29 else 0.


def compact(r):
    return {k:v for k,v in r.items() if k!='probes'}


def run_search(mode,workers):
    folder=HERE/mode
    folder.mkdir(exist_ok=True)
    starting={k:read(p)['actions'] for k,p in BASES.items()}
    starting.update(native=cp.transfer.TEACHER,no_pulses=[])
    save(folder/'protocol.json',dict(mu=MATERIAL[mode],seed=SEED,starting=list(starting),
        source_paths={k:str(v) for k,v in BASES.items()},max_stages=13,bank=14,branches_per_stage=4,
        variant='Shared-state branching on complete retained teacher or selected prefixes. Time grid from 16%, 28%, '
                '40%, 51%, 61%, 69%, 76%, 82%, 87% of the current longest life, then failure-relative retries. '
                'Branch selection includes longest valid progress and alternative contact/relative-speed/edge states.'))
    with ProcessPoolExecutor(workers) as pool:
        base=list(pool.map(simulate,[(mode,SEED,s,None,None) for s in starting.values()]))
        for (name,s),r in zip(starting.items(),base):
            r.update(actions=s,source=name)
        best=max(base,key=key)
        save(folder/'starting.json',[compact(s) for s in base])
        print(mode,'originals',[(r['source'],round(r['last_both_m'],4)) for r in base],flush=True)
        if mode=='record':assert best['last_both_m']==1.4344716654053211
        beam=sorted(base,key=key,reverse=True)[:4]
        hist=[]
        count=0
        fractions=[.16,.28,.40,.51,.61,.69,.76,.82,.87]
        for stage in range(13):
            layer=folder/f'l{stage:02d}'
            layer.mkdir(exist_ok=True)
            live=dict();jobs=[]
            for slot,row in enumerate(beam):
                dur=row['seconds']
                if stage<len(fractions):
                    when=max(.10,min(dur-.16,(fractions[stage]+(slot%3-1)*.018)*dur))
                else:
                    back=[1.8,3.7,.83,5.2][(stage+slot)%4]
                    when=max(.16,dur-back)
                tick=max(4,int(when*50))
                actions=row['actions']
                candidates=bank(mode,stage,slot)
                live[slot]=(actions,tick,candidates,row)
                for part in range(2):
                    jobs.append((mode,SEED,actions,dict(tick=tick,slot=slot,folder=layer,
                                members=[(i,a) for i,a in enumerate(candidates) if i%2==part]),None))
            list(pool.map(simulate,jobs))
            children=[]
            for slot,(s,tick,candidates,parent) in live.items():
                siblings=[read(layer/f'{slot}-{i:02d}.json') for i in range(len(candidates))]
                assert len({r['fork_sha'] for r in siblings})==1
                assert abs(siblings[0]['last_both_m']-parent['last_both_m'])<1e-10
                for a,r in zip(candidates,siblings):
                    r.update(actions=s+([dict(a,tick=tick)] if a is not None else []))
                    children.append(r)
            count+=len(children)
            rows=[best,*beam,*children]
            best=max(rows,key=key)
            # Longest plus a physically distinct near-frontier trajectory and two earlier states
            # with different edge reserve or relative radial velocity at the next window.
            kept=[best]
            def add(row):
                if all(abs(row['last_both_m']-v['last_both_m'])>.0001 or abs(row['seconds']-v['seconds'])>.03 for v in kept):
                    kept.append(row)
            for row in sorted(rows,key=key,reverse=True):
                add(row)
                if len(kept)>=2:break
            at=5*round((best['seconds']*min(.96,(fractions[min(stage+1,8)] if stage<9 else .87)))*10)
            for row in vp.select(rows,at):
                add(row)
                if len(kept)>=4:break
            if len(kept)<4:
                for row in sorted(rows,key=key,reverse=True):
                    add(row)
                    if len(kept)>=4:break
            beam=kept[:4]
            hist.append(dict(stage=stage,selected=[round(r['last_both_m'],6) for r in beam],seconds=best['seconds'],
                 m=best['last_both_m'],n=count,gate=best['gates'],fork_seconds=[t[1]*.02 for t in live.values()]))
            save(folder/'history.json',hist)
            save(folder/'winner.json',compact(best))
            print(mode,hist[-1]['stage'],hist[-1]['selected'],flush=True)
            if best['finish_2p5']:break
    rr=simulate((mode,SEED,best['actions'],None,folder/'trajectory.npz'))
    assert rr['last_both_m']==best['last_both_m'] and rr['last']==best['last']
    save(folder/'result.json',dict(mu=MATERIAL[mode],seed=SEED,branches=count,initial=compact(max(base,key=key)),
        result=compact(rr),selected_actions=best['actions'],probes=rr['probes']))
    print(mode,'done',count,rr['last_both_m'],rr['last'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=MATERIAL);parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args();run_search(args.mode,args.workers)
