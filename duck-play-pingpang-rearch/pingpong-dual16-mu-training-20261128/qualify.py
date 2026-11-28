"""Choose on a separate cohort, then evaluate a frozen controller from release."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch
import argparse
import csv
import hashlib
import json
import sys
import numpy as np
from material import HERE,cp,save,short_track,surface
import decision_policy as decisions
import residual
import train_opening as opening

OUT=HERE/'qualification';OUT.mkdir(exist_ok=True)
ARMS=('medium','opening','ppo','decisions','high_schedule','record_schedule')
FILES={'medium':[],'opening':['opening/selected.json'],'ppo':['ppo/frozen.json'],
       'decisions':['decisions/frozen.json'],'high_schedule':['approach/high/result.json'],
       'record_schedule':['approach/record/result.json']}
SELECTION=range(17400100,17400180)
BLIND=range(17410000,17410300)


def read(p):return json.loads(p.read_text())


def immutable(arm):
    paths=list(FILES[arm])
    if arm=='ppo':paths.append('ppo/'+read(HERE/paths[0])['label']+'.npz')
    paths+=['qualify.py','material.py']
    if arm in ('medium','opening','decisions'):paths+=['opening/train_opening.py']
    if arm=='decisions':paths+=['decision_policy.py']
    if arm=='ppo':paths+=['residual.py']
    return {f:hashlib.sha256((HERE/f).read_bytes()).hexdigest() for f in paths}


def trial(args):
    arm,mat,track,seed=args
    material_value=.224 if mat=='low' else mat
    state={'peak':0.,'both2':False}
    original=short_track.Meter.observe
    def observe(m,t,x,fail,on,audit,bc):
        original(m,t,x,fail,on,audit,bc)
        if m.valid and on:
            state['peak']=max(state['peak'],x)
            if abs(t-2.)<1e-8:state['both2']=True
    with patch.object(short_track.Meter,'observe',observe):
        if arm in ('medium','opening'):
            r=opening.run_seed(seed,material_value,name='medium' if arm=='medium' else None,track=track)
        elif arm=='decisions':
            r=decisions.run_seed(seed,material_value,track=track)
        elif arm=='ppo':
            r=residual.run_seed(seed,mat,track=track)
        else:
            actions=read(HERE/FILES[arm][0])['selected_actions']
            with surface(mat):z=cp.transfer.run(track,seed,actions=actions)
            r=dict(flat=z['flat_1m'],slope=z['slope_1m'],finish=z['finish_2p5'],m=z['last_both_m'],
                   t=z['seconds'],reason=z['reason'],torque=z['torque_nm'])
    assert r['torque']<=.20000001
    return dict(arm=arm,mat=mat,track=track,seed=seed,flat=r['flat'],slope=r['slope'],finish=r['finish'],
                last_m=r['m'],both_peak_m=state['peak'],both2=state['both2'],t=r['t'],reason=r['reason'],torque=r['torque'])


def aggregate(rows):
    return dict(n=len(rows),flat=sum(r['flat'] for r in rows),slope=sum(r['slope'] for r in rows),
                finish=sum(r['finish'] for r in rows),both2=sum(r['both2'] for r in rows),
                half=sum(r['both_peak_m']>=.50 for r in rows),quarter=sum(r['both_peak_m']>=.25 for r in rows),
                mean_m=float(np.mean([r['last_m'] for r in rows])),max_m=max(r['last_m'] for r in rows),
                best_seed=max(rows,key=lambda r:r['last_m'])['seed'])


def csvout(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def protocol():
    save(OUT/'protocol.json',dict(arms=ARMS,development=[SELECTION.start,SELECTION.stop-1],
         blind=[BLIND.start,BLIND.stop-1],objective='2.5 m with both gates and a one-second terminal stop; 270/300 for empirical 90%',
         select='Combined course at high and native wide, on the same independent development starts. '
                'Lexicographic total finish, complete uphill, flat, half, quarter, both at two seconds, mean valid distance. Tie goes to earlier arm.',
         final='Winning policy: 3 tracks at high & wide; combined at low as transfer; also paired medium control on combined high & wide.'))


def select(arms):
    with ProcessPoolExecutor(6) as pool:
        for arm in arms:
            digests=immutable(arm);rows=list(pool.map(trial,[(arm,m,'combined',s) for s in SELECTION for m in ('high','wide')],chunksize=5))
            assert digests==immutable(arm)
            csvout(OUT/(arm+'-select.csv'),rows)
            scores={m:aggregate([r for r in rows if r['mat']==m]) for m in ('high','wide')}
            save(OUT/(arm+'-select.json'),dict(hashes=digests,scores=scores))
            print(arm,scores,flush=True)


def final():
    data={arm:read(OUT/(arm+'-select.json')) for arm in ARMS}
    for a in ARMS:assert data[a]['hashes']==immutable(a)
    def rank(a):
        return tuple(sum(v[k] for v in data[a]['scores'].values()) for k in ('finish','slope','flat','half','quarter','both2','mean_m'))
    winner=max(ARMS,key=rank)
    seal=dict(winner=winner,hashes=immutable(winner),comparison=list(ARMS),score={a:rank(a) for a in ARMS},
              first_seed=BLIND.start,n=len(BLIND))
    save(OUT/'frozen.json',seal)
    arms=[(winner,m,t) for m in ('high','wide') for t in ('combined','flat','incline')]+[(winner,'low','combined')]
    arms+= [q for q in [('medium','high','combined'),('medium','wide','combined')] if q not in arms]
    rows=[]
    with ProcessPoolExecutor(8) as pool:
        for arm,m,track in arms:
            rr=list(pool.map(trial,[(arm,m,track,s) for s in BLIND],chunksize=6))
            assert len(rr)==len({r['seed'] for r in rr})==300
            rows.extend(rr);print(arm,m,track,aggregate(rr),flush=True)
    assert seal['hashes']==immutable(winner)
    csvout(OUT/'blind.csv',rows)
    result={'/'.join(a):aggregate([r for r in rows if (r['arm'],r['mat'],r['track'])==a]) for a in arms}
    save(OUT/'blind.json',result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('protocol','select','final'));p.add_argument('arms',nargs='*')
    a=p.parse_args()
    if a.action=='protocol':protocol()
    elif a.action=='select':select(a.arms or ARMS)
    else:final()
