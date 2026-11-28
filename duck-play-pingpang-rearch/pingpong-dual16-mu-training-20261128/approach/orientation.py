"""Retain alternative A/B order at 8 s, then train recovery along those counterfactuals."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from search import HERE,SEED,BASES,read,save,simulate,bank,key,vp,compact

OUT=HERE/'orientation'
MODE='record'


def reconstruct(pool):
    source=HERE/MODE
    starting={k:read(p)['actions'] for k,p in BASES.items()}
    starting.update(native=vp.engine.TEACHER,no_pulses=[])
    base=list(pool.map(simulate,[(MODE,SEED,s,None,None) for s in starting.values()]))
    for s,r in zip(starting.values(),base):r.update(actions=s)
    best=max(base,key=key);beam=sorted(base,key=key,reverse=True)[:4];valid=[]
    fractions=[.16,.28,.40,.51,.61,.69,.76,.82,.87]
    for stage in range(5):
        children=[]
        for slot,row in enumerate(beam):
            tick=max(4,int(max(.10,min(row['seconds']-.16,(fractions[stage]+(slot%3-1)*.018)*row['seconds']))*50))
            for i,a in enumerate(bank(MODE,stage,slot)):
                r=read(source/f'l{stage:02d}'/f'{slot}-{i:02d}.json')
                if i==0:assert abs(r['last_both_m']-row['last_both_m'])<1e-10
                r['actions']=row['actions']+([dict(a,tick=tick)] if a else [])
                if '400' in r['probes'] and r['probes']['400'][8]>.002:valid.append(r)
                children.append(r)
        rows=[best,*beam,*children];best=max(rows,key=key);kept=[best]
        def add(row):
            if all(abs(row['last_both_m']-v['last_both_m'])>.0001 or abs(row['seconds']-v['seconds'])>.03 for v in kept):kept.append(row)
        for row in sorted(rows,key=key,reverse=True):
            add(row)
            if len(kept)>=2:break
        at=5*round(best['seconds']*min(.96,fractions[stage+1])*10)
        for row in vp.select(rows,at):
            add(row)
            if len(kept)>=4:break
        if len(kept)<4:
            for row in sorted(rows,key=key,reverse=True):
                add(row)
                if len(kept)>=4:break
        beam=kept[:4]
    return valid


def feature(row,at):
    keys=[k for k in row['probes'] if abs(int(k)-at)<=7]
    if not keys:return None
    k=min(keys,key=lambda k:abs(int(k)-at))
    p=row['probes'][k]
    return np.array([*p,float(k)])


def main():
    OUT.mkdir(exist_ok=True)
    with ProcessPoolExecutor(3) as pool:
        seed_pool=reconstruct(pool)
        seed_pool.sort(key=lambda r:(r['seconds'],r['last_both_m']),reverse=True)
        beam=[]
        for r in seed_pool:
            if all(abs(r['last_both_m']-b['last_both_m'])>.003 for b in beam):beam.append(r)
            if len(beam)>=3:break
        assert 2<=len(beam)<=3
        save(OUT/'protocol.json',dict(seed=SEED,material=MODE,looked_at='Signed A/B separation on paddle at 8.0 seconds. Largest x-direction opening impulse from the teacher at 11.6–11.7 s points negative x. Favor B on positive x before it during search only; no seed, torque or upcoming impulse fed to the controller.',
             starting_pool=len(seed_pool),starting=[compact(r) for r in beam]))
        best=max(beam,key=key);hist=[]
        for level in range(13):
            layer=OUT/f'l{level:02d}';layer.mkdir(exist_ok=True)
            jobs=[];live=[];front=min(11.60,7.58+.36*level)
            for j,r in enumerate(beam):
                t=min(front+(.13*j),r['seconds']-(.45+.15*j))
                tick=max(4,round(50*t))
                candidates=bank(MODE,level+32,j+11)
                live.append((r,tick,candidates))
                for g in range(2):
                    jobs.append((MODE,SEED,r['actions'],dict(tick=tick,slot=j,folder=layer,members=[(i,a) for i,a in enumerate(candidates) if i%2==g]),None))
            list(pool.map(simulate,jobs))
            children=[]
            for j,(r,tick,candidates) in enumerate(live):
                group=[read(layer/f'{j}-{i:02d}.json') for i in range(len(candidates))]
                assert group[0]['last_both_m']==r['last_both_m'] and len({g['fork_sha'] for g in group})==1
                for c,a in zip(group,candidates):
                    c['actions']=r['actions']+([dict(a,tick=tick)] if a else [])
                    children.append(c)
            rows=[*beam,*children,best];best=max(rows,key=key);keep=[best]
            # Select across a deliberately advanced time if any such prefix is reachable.
            at=5*round(min(max(r['seconds'] for r in rows)-.20,front+.65,11.55)*10)
            alternatives=[(r,feature(r,at)) for r in rows]
            alternatives=[(r,p) for r,p in alternatives if p is not None and r['max_tilt_deg']<29]
            for index in (0,1):
                def score(it):
                    r,p=it
                    if index==0:return p[8]-.42*p[1]+.07*r['last_both_m']-.15*abs(p[10])
                    return p[8]+.30*p[10]-.90*p[1]-.5*p[4]+.05*r['last_both_m']
                for r,p in sorted(alternatives,key=score,reverse=True):
                    if all(abs(r['last_both_m']-b['last_both_m'])>.0007 for b in keep):
                        keep.append(r);break
            beam=keep
            hist.append(dict(level=level,n=len(children),s=best['seconds'],m=best['last_both_m'],probe_s=at*.02,
                 selected=[[float(feature(r,at)[8]*1000),r['seconds']] if feature(r,at) is not None else None for r in beam]))
            save(OUT/'history.json',hist);save(OUT/'winner.json',compact(best));print(hist[-1],flush=True)
            if best['finish_2p5']:break
        final=simulate((MODE,SEED,best['actions'],None,OUT/'trajectory.npz'))
        assert final['last_both_m']==best['last_both_m']
        save(OUT/'result.json',dict(seed=SEED,branches=sum(h['n'] for h in hist),final=compact(final),probes=final['probes'],actions=best['actions']))
if __name__=='__main__':main()
