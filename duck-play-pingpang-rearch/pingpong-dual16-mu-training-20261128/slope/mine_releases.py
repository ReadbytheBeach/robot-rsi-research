"""Development-only natural release search; controls never receive latent impulses."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json, math, sys
import numpy as np
from high_slope import HERE, configs, run, rank, save

START=18240000
TOTAL=150000

def load(seed,occupied=None):
    rng=np.random.default_rng(seed);rng.random(5)
    while True:
        angle=rng.uniform(-math.pi,math.pi);r=rng.uniform(.006,.032)
        p=np.array((r*math.cos(angle),r*math.sin(angle)))
        if occupied is None or (p-occupied)@(p-occupied)>=.0204**2:break
    v=rng.uniform(-.059,.059,2);lag,act=rng.integers(0,3,size=2);rng.standard_normal(4)
    ticks=np.array([rng.integers(80,180),rng.integers(255,400)])
    directions=rng.uniform(-math.pi,math.pi,2)
    return p,v,ticks,np.stack([np.cos(directions),np.sin(directions)],axis=1),lag+act

def block(lo):
    found=[]
    for s in range(lo,lo+2500):
        a=load(s);ss=np.random.SeedSequence([s,20002]).generate_state(1)[0];b=load(ss,a[0])
        x=a[0]-b[0];v=a[1]-b[1];u=(a[1]+b[1])*.5
        if v@v>.00081:continue
        dt=.02*np.abs(a[2]-b[2]);diff=np.linalg.norm(a[3]-b[3],axis=1)
        # Avoid size-normalized dangerous relative excursion and large common launch motion.
        sep=np.linalg.norm(x+2*v);offset=np.linalg.norm(a[0]+b[0])*.5
        relative=.7*min(2.,np.linalg.norm(v)/.025)+.45*min(2.,sep/.05)+.14*max(0,np.linalg.norm(x)-.03)/.015
        common=.45*np.linalg.norm(u)/.035+.20*offset/.015+.04*(a[4]+b[4])
        first=.73*diff[0]+.65*dt[0];second=.53*diff[1]+.38*dt[1]
        scores=(relative+common+first+second,1.6*relative+common+.6*first+.35*second,
                relative+.6*common+1.25*first+.85*second)
        found.append((s,scores))
    return [sorted(found,key=lambda z:z[1][k])[:14] for k in range(3)]

def main():
    save('mine-protocol.json',dict(range=[START,START+TOTAL-1],purpose='development teachers only; selection uses latent natural perturbations, zero ability to infer any success rate',nominal_count=144,materials=[.416],physics='identical release, independent impulses, no changes to randomized physics'))
    with ProcessPoolExecutor(3) as pool: pools=list(pool.map(block,range(START,START+TOTAL,2500)))
    seeds=[];metrics=[]
    for k in range(3):
        candidates=[z for stage in pools for z in stage[k]]
        best=sorted(candidates,key=lambda z:z[1][k])[:60]
        seeds.extend(i[0] for i in best);metrics.extend(best)
    seeds=list(dict.fromkeys(seeds));base,archive=configs()
    save('mined-selected.json',dict(seeds=seeds,metrics=metrics))
    jobs=[base(s,mode)|{'scale':scale} for s in seeds for mode,scale in (('original',1.),('settle_long',1.06),('steady_then_fast',1.))]
    with ProcessPoolExecutor(4) as pool: rows=list(pool.map(run,jobs,chunksize=3))
    rows.sort(key=rank,reverse=True);save('mined-screen.json',rows)
    print(len(seeds),len(rows),[(z['config']['seed'],z['row']['last_both_m']) for z in rows[:5]],flush=True)

if __name__=='__main__':main()
