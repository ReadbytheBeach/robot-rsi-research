"""Look for high-friction approach examples on the release-aligned primary track."""
from concurrent.futures import ProcessPoolExecutor
from argparse import ArgumentParser
from pathlib import Path
import csv
import json
import numpy as np
from search import HERE, SHORT, SEED, bank, compact, key, read, run, save

FOLDER=HERE/'primary'
ACTIONS=read(SHORT/'replay/fixed-paced-seal.json')['actions']


def rollout(job):
    seed,actions=job
    row=run('combined',seed,actions,'high')
    return dict(row,actions=actions)


def main():
    FOLDER.mkdir(exist_ok=True)
    # Seeds are selected exclusively from pre-existing development sweeps.
    mined=read(SHORT/'replay/combined-mine-14550000.json')
    physical=list(csv.DictReader((SHORT/'training/enrichment/physical.csv').open()))
    # For old enriched starts, take top max distance of any prior realized controller.
    enriched=sorted((r for r in physical if r['track']=='combined'),key=lambda r:-float(r['last_both_m']))
    chosen=[r['seed'] for r in sorted(mined,key=lambda r:-r['last_both_m'])[:48]]
    extra=list(dict.fromkeys(int(r['seed']) for r in enriched))[:64]
    seeds=list(dict.fromkeys(chosen+extra+[SEED,15366428,14402572,14551262]))
    save(FOLDER/'protocol.json',dict(development_seeds=seeds,mu=.416,track='combined',
         candidate_selection='Top traveled releases from archived development traces plus opened examples. Never enter a population success rate.',
         search='Mutation of inherited and newly appended early/late physical pulses. Each candidate starts at release with full noise/delays.'))
    rng=np.random.default_rng(184231)
    with ProcessPoolExecutor(3) as pool:
        pilots=list(pool.map(rollout,[(s,ACTIONS) for s in seeds],chunksize=3))
        save(FOLDER/'pilot.json',[{k:v for k,v in r.items() if k!='actions'} for r in pilots])
        overall=max(pilots,key=key)
        baseline=overall
        beam=sorted(pilots,key=key,reverse=True)[:3]
        print('pilot',len(seeds),[(v['seed'],v['last_both_m']) for v in beam],flush=True)
        hist=[]
        for stage in range(12):
            work=[]
            for i,b in enumerate(beam):
                end=b['seconds']
                for j in range(12):
                    seq=list(b['actions'])
                    t=rng.uniform(max(.10,end-5),max(.15,end-.25)) if j%3 else rng.uniform(.12,max(.25,end*.64))
                    a=bank('high',stage+49,j+i*12)[1+rng.integers(13)]
                    if j%4==0:
                        # Add a sustained gait change while the body is still safely upright.
                        a['duration']=float(rng.choice([1.3,1.9,2.5,3.1]))
                        a['speed']=float(rng.uniform(-.30,.50))
                    seq.append(dict(tick=round(50*t),**a))
                    work.append((b['seed'],seq))
            rows=list(pool.map(rollout,work,chunksize=2))
            ranked=sorted([*beam,overall,*rows],key=key,reverse=True)
            previous=overall;overall=ranked[0];beam=[]
            for row in ranked:
                if all(row['seed']!=b['seed'] or abs(row['last_both_m']-b['last_both_m'])>.002 for b in beam):
                    beam.append(row)
                if len(beam)==3:break
            hist.append(dict(stage=stage,seed=overall['seed'],m=overall['last_both_m'],s=overall['seconds'],n=len(work)))
            save(FOLDER/'history.json',hist);save(FOLDER/'winner.json',overall)
            print('primary',hist[-1],flush=True)
            if overall['finish_2p5']:break
    verified=run('combined',overall['seed'],overall['actions'],'high',trace=FOLDER/'trajectory.npz')
    assert verified['last_both_m']==overall['last_both_m']
    save(FOLDER/'result.json',dict(pilot_count=len(seeds),branches=sum(s['n'] for s in hist),initial=baseline,
         selected_actions=overall['actions'],result=verified))


if __name__=='__main__':main()
