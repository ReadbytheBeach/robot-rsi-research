"""Fork identical high-friction uphill states and vary short gait and neck pulses."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
from high_slope import HERE, MAX_ARM, read, save, run, rank

def job(args):
    cfg,fork=args;run(cfg,fork=fork)

def main():
    opened=HERE/'sprint-start.json'
    if not opened.exists():save(opened.name,read(HERE/'best.json'))
    best=read(opened)
    beam=[best];log=[];rng=np.random.default_rng(663415);stale=0
    for layer in range(12):
        if best['row']['success']:break
        base=sorted(beam,key=rank,reverse=True)[0]
        stage=HERE/'matched'/f'{layer:02d}';stage.mkdir(parents=True,exist_ok=True)
        schedule=[]
        for slot in range(4):
            source=beam[slot%len(beam)];r=source['row'];cfg=source['config'];end=r['seconds']
            frac=[.28,.50,.70,.88][slot];frac=np.clip(frac+rng.uniform(-.075,.075),.13,.96)
            if layer%4==2 and slot==0:frac=rng.uniform(.045,.17)
            tick=max(3,min(round(end/.02)-4,round(frac*end/.02)))
            bank=[None]
            for i in range(12):
                a=dict.fromkeys(('pitch','roll','damp','speed','neck','hip','lateral','yaw','span'),0.)
                a['duration']=(.48,1.30,2.45,3.6)[i//3]
                a['speed']=(.16,.34,.52)[i%3]
                if (layer+slot)%3==1:
                    a['damp']=(.16,.05,-.065)[i%3];a['neck']=(.014,0.,-.022)[i%3]
                elif (layer+slot)%3==2:
                    a['speed']=rng.uniform(-.3,.34); a['yaw']=rng.uniform(-.22,.22);a['span']=rng.uniform(-.18,.18)
                bank.append(a)
            schedule.append((source,tick,bank))
        steps=[]
        for s,(source,tick,bank) in enumerate(schedule):
            for j in range(2):steps.append((source['config'],dict(tick=tick,slot=s,folder=stage,
                        members=[(i,a) for i,a in enumerate(bank) if i%2==j])))
        with ProcessPoolExecutor(4) as pool:list(pool.map(job,steps))
        candidates=beam.copy()
        for slot,(source,tick,bank) in enumerate(schedule):
            vals=[read(stage/f'{slot}-{i:02d}.json') for i in range(len(bank))]
            assert len({v['fork_sha'] for v in vals})==1
            assert abs(vals[0]['last_both_m']-source['row']['last_both_m'])<1e-12
            for i,(a,r) in enumerate(zip(bank,vals)):
                cfg=deepcopy(source['config'])
                if a:cfg['actions'].append(a|{'tick':tick})
                candidates.append(dict(config=cfg,arm=MAX_ARM,mu=[.416,.416],row=r))
        ordered=sorted(candidates,key=rank,reverse=True)
        best=ordered[0]
        if best['row']['slope_1m'] and not best['row']['success']:
            brakes=[(buf,ramp,wait) for buf in (-.060,-.035,-.018,0.,.014,.028,.05,.085)
                    for ramp in (.03,.16,.32) for wait in (0.,.20)]
            with ProcessPoolExecutor(4) as pool:
                terminal=list(pool.map(run,[best['config']|{'brake':b} for b in brakes],chunksize=2))
            ordered=sorted(ordered+terminal,key=rank,reverse=True);best=ordered[0]
        keep=set();beam=[]
        for i in ordered:
            key=(round(i['row']['last_both_m'],4),round(i['row']['seconds'],2))
            if key in keep:continue
            keep.add(key);beam.append(i)
            if len(beam)==3:break
        stale=stale+1 if abs(best['row']['last_both_m']-base['row']['last_both_m'])<.001 and best['row']['stable_finish_s']<=base['row']['stable_finish_s'] else 0
        r=best['row'];log.append(dict(layer=layer,branches=sum(len(x[2]) for x in schedule),m=r['last_both_m'],t=r['seconds'],g=r['slope_1m'],hold=r['stable_finish_s'],park=r['success']))
        print(log[-1],flush=True);save('sprint-progress.json',log);save('sprint-best.json',best)
        if stale>=4:break
    final=run(best['config'],trace=HERE/'sprint.npz')
    for k in ('gates','success','stable_finish_s','last_both_m'):
        assert final['row'][k]==best['row'][k]
    save('sprint-best.json',final)
    save('sprint-seal.json',dict(config=final['config'],seed_range=[17782000,17782127]))
    with ProcessPoolExecutor(4) as pool:rows=list(pool.map(run,[final['config']|{'seed':s} for s in range(17782000,17782128)],chunksize=4))
    save('sprint-holdout.json',dict(n=len(rows),slope=sum(z['row']['slope_1m'] for z in rows),park=sum(z['row']['success'] for z in rows),max_m=max(z['row']['last_both_m'] for z in rows),rows=[z['row'] for z in rows]))

if __name__=='__main__':main()
