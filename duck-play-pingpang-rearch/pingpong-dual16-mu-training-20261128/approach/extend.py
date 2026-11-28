"""Reoptimize gait at release, mid-course and late recovery on consecutive selected parents."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import argparse
import numpy as np
from search import HERE,read,run,save,key


def trial(job):
    mode,track,seed,actions=job
    r=run(track,seed,actions,mode)
    return dict(r,actions=actions)


def main(label):
    src=HERE/label
    folder=HERE/(label+'-continuation');folder.mkdir(exist_ok=True)
    init=read(src/'result.json')
    mode='record' if label=='record' else 'high';track='combined' if label=='primary' else 'fixed'
    seed=init['result']['seed'];actions=init['selected_actions']
    base=trial((mode,track,seed,actions))
    assert base['last_both_m']==init['result']['last_both_m']
    save(folder/'protocol.json',dict(source=str(src/'result.json'),weights='Prioritize ordered route gates, then last dual contact below 29 degrees trunk tilt.',
        rounds=12,parents=3,candidates_per_parent=16,track=track,seed=seed,mu=init.get('mu',.416)))
    rng=np.random.default_rng({'high':91871,'record':7823,'primary':92771}[label])
    beam=[base];best=base;history=[];no_gain=0
    with ProcessPoolExecutor(3) as pool:
        for stage in range(12):
            jobs=[]
            for n in range(48):
                p=beam[n%len(beam)];duration=p['seconds']
                # Use a much longer or shorter gait command from early windows; alternate with tiny phase shifts
                # of an existing correction (sensor feedback still runs inside that action).
                bank=[dict(a) for a in p['actions']]
                if n%5==0 and bank:
                    pos=int(rng.integers(len(bank)));a=bank[pos]
                    a['tick']=max(0,a['tick']+int(rng.choice([-8,-4,-2,-1,1,2,4,8])))
                    a['duration']=max(.08,a['duration']*rng.uniform(.76,1.27))
                else:
                    if n%4==0:t=rng.uniform(.08,duration*.55)
                    elif n%4==1:t=rng.uniform(duration*.48,duration*.82)
                    else:t=rng.uniform(max(.15,duration-4.1),duration-.17)
                    a=dict.fromkeys(('pitch','roll','neck','yaw','hip','lateral','speed','span','damp'),0.)
                    a.update(tick=round(t/.02),speed=rng.uniform(-.35,.58),duration=float(rng.choice([.18,.40,.8,1.3,2.2,3.4])))
                    if n%3:
                        a['damp']=rng.uniform(-.19,.23);a['neck']=rng.uniform(-.040,.040)
                    if n%7==0:
                        a['yaw']=rng.uniform(-.27,.27);a['hip']=rng.uniform(-.022,.022)
                    bank.append(a)
                jobs.append((mode,track,seed,bank))
            rows=list(pool.map(trial,jobs,chunksize=2))
            ordered=sorted([*beam,best,*rows],key=key,reverse=True)
            old=best;best=ordered[0];beam=[]
            for row in ordered:
                if all(abs(row['last_both_m']-b['last_both_m'])>.0008 or abs(row['seconds']-b['seconds'])>.1 for b in beam):
                    beam.append(row)
                if len(beam)==3:break
            no_gain=0 if best['last_both_m']>old['last_both_m']+.002 else no_gain+1
            history.append(dict(stage=stage,n=len(rows),m=best['last_both_m'],s=best['seconds'],top=[r['last_both_m'] for r in beam]))
            save(folder/'winner.json',best);save(folder/'history.json',history)
            print(label,stage,best['last_both_m'],best['seconds'],flush=True)
            if no_gain>=4 or best['finish_2p5']:break
    result=run(track,seed,best['actions'],mode,folder/'trajectory.npz')
    assert result['last_both_m']==best['last_both_m']
    save(folder/'result.json',dict(initial=base,result=result,selected_actions=best['actions'],seed=seed,mu=init.get('mu',.416),
           branches=sum(v['n'] for v in history),track=track))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('label',choices=('high','primary','record'));main(a.parse_args().label)
