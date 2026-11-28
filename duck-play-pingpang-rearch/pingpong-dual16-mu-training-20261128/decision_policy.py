"""Train two observation-triggered decisions using paired MuJoCo action returns."""
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch
import json
import sys
import numpy as np
from material import HERE,save
sys.path.insert(0,str(HERE/'opening'))
import train_opening as op

OUT=HERE/'decisions';OUT.mkdir(exist_ok=True)
EXPERTS=['medium','phase_08','turn_02','intercept_05','pressure_11','phase_24']
PARAM=op.bank()
CUES=['span','separation_rate','relative_side_speed','edge_margin','projected_edge','centre_forward','centre_lateral','edge_closing_speed','tilt_forward']


def features(bc):
    ch=bc.channels[0]
    a,b=(c.measurements[0] for c in bc.channels)
    dx=b[:2]-a[:2];span=max(.001,float(np.linalg.norm(dx)));axis=dx/span;dv=b[2:]-a[2:]
    edge=max(a,b,key=lambda z:np.linalg.norm(z[:2]))
    return np.array([span,axis@dv,abs(np.array([-axis[1],axis[0]])@dv),.055-np.linalg.norm(edge[:2]),
                     max(np.linalg.norm(z[:2]+.30*z[2:]) for z in (a,b)),(a[0]+b[0])*.5,
                     (a[1]+b[1])*.5,edge[:2]@edge[2:]/max(.004,np.linalg.norm(edge[:2])),
                     ch.d.site_xmat[ch.site].reshape(3,3)[2,0]],dtype=float)


def predict(tree,x):
    while 'feature' in tree:
        tree=tree['left'] if x[tree['feature']]<=tree['threshold'] else tree['right']
    return tree['action']


def rollout(job):
    seed,material,trees,forced,tick,track,trace=job
    captured={};parent=op.Opening
    class Routed(parent):
        def update(self,bc):
            t=bc.tick
            if t in (0,35) and t not in captured:
                x=features(bc);captured[t]=x.tolist()
                if forced is not None and t==tick:
                    self.policy=PARAM[EXPERTS[forced]]
                elif str(t) in trees:
                    self.policy=PARAM[EXPERTS[predict(trees[str(t)],x)]]
                if self.policy is None:
                    self.speed=1.;self.tilt[:]=0;self.requests[:]=0
            return super().update(bc)
        def joint_command(self,ch):
            if self.policy is not None:super().joint_command(ch)
    with patch.object(op,'Opening',Routed):
        row=op.run_seed(seed,material,name=EXPERTS[1],trace=trace,track=track)
    row['features']=captured.get(tick);row['forced']=forced
    return row


def reward(r):
    return (r['m']+.16*r['both2']+.20*r['qtr']+.45*r['half']+
            1.3*r['flat']+2*r['slope']+5*r['finish'])


def learn(x,values,depth,min_samples):
    action=int(np.argmax(values.mean(axis=0)))
    leaf={'action':action,'examples':len(x)}
    if depth<=0 or len(x)<2*min_samples:return leaf
    best=values[:,action].sum()+.05
    split=None
    for k in range(x.shape[1]):
        for c in np.unique(np.quantile(x[:,k],[.20,.35,.5,.65,.80])):
            left=x[:,k]<=c
            if min(sum(left),sum(~left))<min_samples:continue
            score=values[left].sum(axis=0).max()+values[~left].sum(axis=0).max()
            if score>best:
                best=score;split=(k,float(c),left)
    if split is None:return leaf
    k,c,left=split
    return dict(feature=k,threshold=c,left=learn(x[left],values[left],depth-1,min_samples),
                right=learn(x[~left],values[~left],depth-1,min_samples))


def collect(pool,seeds,tick,policy):
    jobs=[(s,'high' if i%3!=2 else 'wide',policy,a,tick,'combined',None)
          for i,s in enumerate(seeds) for a in range(len(EXPERTS))]
    rows=list(pool.map(rollout,jobs,chunksize=3));x=[];y=[]
    for i in range(0,len(rows),len(EXPERTS)):
        group=rows[i:i+len(EXPERTS)]
        if group[0]['features'] is None:
            assert all(r['features'] is None for r in group);continue
        assert all(np.array_equal(r['features'],group[0]['features']) for r in group)
        x.append(group[0]['features']);y.append([reward(r) for r in group])
    return np.array(x),np.array(y),rows


def run_seed(seed,material='high',track='combined',trace=None,trees=None):
    if trees is None:trees=json.loads((OUT/'frozen.json').read_text())['trees']
    return rollout((seed,material,trees,None,-1,track,trace))


def train():
    save(OUT/'protocol.json',dict(experts=EXPERTS,cues=CUES,release_starts=[17300000,17300167],
         continuation_starts=[17301000,17301191],select_starts=[17302000,17302079],ticks=[0,35],
         reward='last both m + .16 both2 + .20 quarter + .45 half + 1.3 flat + 2 slope + 5 finish'))
    with ProcessPoolExecutor(5) as pool:
        policy={};history={}
        for tick,start,n in ((0,17300000,168),(35,17301000,192)):
            x,y,rows=collect(pool,range(start,start+n),tick,policy)
            save(OUT/f'train-{tick}.json',rows)
            candidates=[policy]
            for depth in (0,1,2,3):
                candidates.append({**policy,str(tick):learn(x,y,depth,16)})
            stats=[]
            # Both opportunities use the same development validation cohort. The final cohort is sealed separately.
            for tree in candidates:
                jobs=[(s,'high' if i%3!=2 else 'wide',tree,None,-1,'combined',None)
                      for i,s in enumerate(range(17302000,17302080))]
                rr=list(pool.map(rollout,jobs,chunksize=4))
                stats.append(dict(n=len(rr),finish=sum(r['finish'] for r in rr),slope=sum(r['slope'] for r in rr),
                          flat=sum(r['flat'] for r in rr),half=sum(r['half'] for r in rr),
                          both2=sum(r['both2'] for r in rr),mean_score=float(np.mean([reward(r) for r in rr]))))
            def quality(j):return tuple(stats[j][k] for k in ('finish','slope','flat','half','mean_score'))
            win=max(range(len(stats)),key=quality)
            policy=candidates[win];history[str(tick)]=dict(trained_states=len(x),scores=stats,selected=win)
            print(tick,len(x),win,stats[win],flush=True)
        save(OUT/'frozen.json',dict(trees=policy,history=history,experts=EXPERTS,cues=CUES))


if __name__=='__main__':train()
