"""Learn a release-conditioned policy switch from the first delivered camera observations."""
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
from unittest.mock import patch

import numpy as np
import train_opening as t


def release_features(bc):
    z=np.array([ch.measurements[0] for ch in bc.channels])
    delta=z[1,:2]-z[0,:2];dv=z[1,2:]-z[0,2:]
    centre=.5*(z[1,:2]+z[0,:2]); span=max(.003,np.linalg.norm(delta))
    axis=delta/span;tangent=np.array([-axis[1],axis[0]])
    worst=max(np.linalg.norm(row[:2]+.28*row[2:]) for row in z)
    return np.array([1.,span/.055,(axis@dv)/.09,(tangent@dv)/.09,worst/.055,
                     centre[0]/.055,centre[1]/.055,np.linalg.norm(delta+.32*dv)/.11])


def apply(seed,material,select=None,trace=None,track='combined'):
    sampled={}
    original=t.Opening.update
    def update(actor,bc):
        if not sampled:
            assert bc.tick==0
            x=release_features(bc);sampled['x']=x.tolist()
            sampled['name']=select(x) if select else 'medium'
            actor.policy=t.bank()[sampled['name']]
        return original(actor,bc)
    original_joint=t.Opening.joint_command
    def joint(actor,ch):
        if actor.policy is not None:return original_joint(actor,ch)
    with patch.object(t.Opening,'update',update),patch.object(t.Opening,'joint_command',joint):
        result=t.run_seed(seed,material,'phase_00',trace,track)
    result['name']=sampled['name']
    return result,sampled['x']


def feature_job(seed):
    row,x=apply(seed,'high')
    assert row['name']=='medium'
    return dict(seed=seed,row=row,features=x)


def run_seed(seed,material='high',trace=None,track='combined'):
    cfg=json.loads((t.HERE/'regime-frozen.json').read_text())
    names=cfg['names'];w=np.array(cfg['weights'])
    def select(x):
        return names[int(np.argmax(x@w))]
    result,_=apply(seed,material,select,trace,track)
    return result


def val_job(c):
    seed,material,actor=c
    return run_seed(seed,material) if actor=='regime' else t.run_seed(seed,material)


def fit(x,y,alpha):
    # A non-penalized intercept retains the empirical mean of each candidate.
    p=np.diag([0.,*[alpha]*(x.shape[1]-1)])
    return np.linalg.solve(x.T@x+p,x.T@y)


def main():
    t.write('regime-protocol.json',dict(development='same 64 selection states and the same 9 candidates as the base study',
        features=['bias','span','radial velocity','cross velocity','predicted worst radius','centroid x','centroid y','predicted span'],
        objective='quarter + 0.35 * both2 + 1.3*metres + 3*half + 10*flat + 100*finish; held-out-fold prediction',
        folds=4,alphas=[4,16,48,128,512,1e8],holdout=[17046000,128],materials=['high','wide'],
        sha=hashlib.sha256(t.Path(__file__).read_bytes()).hexdigest()))
    rows=list(csv.DictReader((t.HERE/'selection.csv').open()))
    seeds=sorted({int(r['seed']) for r in rows})
    names=sorted({r['name'] for r in rows})
    with ProcessPoolExecutor(4) as pool:
        features=list(pool.map(feature_job,seeds,chunksize=3))
        t.write('regime-features.json',features)
        x=np.array([f['features'] for f in features])
        y=np.zeros((len(seeds),len(names)))
        for row in rows:
            i=seeds.index(int(row['seed']));j=names.index(row['name'])
            if row['name']=='medium' and row['material']=='high':
                assert float(row['m'])==features[i]['row']['m'] and float(row['t'])==features[i]['row']['t']
            score=1.3*float(row['m'])
            for k,c in [('qtr',1),('both2',.35),('half',3),('flat',10),('finish',100)]:
                score+=c*(row[k]=='True')
            y[i,j]+=.5*score
        alphas=(4.,16.,48.,128.,512.,1e8)
        cv={}
        for alpha in alphas:
            val=np.zeros(len(x))
            for fold in range(4):
                idx=np.arange(len(x))%4==fold
                weights=fit(x[~idx],y[~idx],alpha)
                pred=np.argmax(x[idx]@weights,axis=1)
                val[idx]=y[idx,pred]
            cv[alpha]=float(val.mean())
        alpha=max(alphas,key=lambda a:(cv[a],a))
        weights=fit(x,y,alpha)
        t.write('regime-frozen.json',dict(names=names,weights=weights.tolist(),alpha=alpha,cv=cv))
        cases=[(s,mat,a) for s in range(17046000,17046128) for mat in ['high','wide'] for a in ['global','regime']]
        values=list(pool.map(val_job,cases,chunksize=4))
    for row,(_,_,a) in zip(values,cases):row['selection']=a
    with (t.HERE/'regime-holdout.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=values[0]);w.writeheader();w.writerows(values)
    scores={}
    for mat in ['high','wide']:
        scores[mat]={}
        for actor in ['global','regime']:
            subset=[r for r in values if r['material']==mat and r['selection']==actor]
            assert len({r['seed'] for r in subset})==len(subset)==128
            scores[mat][actor]={k:sum(r[k] for r in subset) for k in ('flat','slope','finish','both2','qtr','half')}
            scores[mat][actor].update(m=float(np.mean([r['m'] for r in subset])),max_m=max(r['m'] for r in subset),
                    policy_use={n:sum(r['name']==n for r in subset) for n in names})
    t.write('regime-validation.json',scores)
    print(scores,flush=True)


if __name__=='__main__':main()
