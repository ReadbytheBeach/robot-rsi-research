"""Dense directional two-axis catches before the remaining 0.416 near-metre loss."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from search import HERE,SEED,read,save,simulate,key,compact

OUT=HERE/'high-catch'
MODE='high'


def main():
    OUT.mkdir(exist_ok=True)
    if not (OUT/'start.json').exists():
        save(OUT/'start.json',read(HERE/'high-continuation/winner.json'))
    source=read(OUT/'start.json')
    seed=source['seed']
    best=simulate((MODE,seed,source['actions'],None,None));best.update(actions=source['actions'])
    assert best['last_both_m']==source['last_both_m']
    best0=best
    beam=[best]*4;hist=[]
    save(OUT/'protocol.json',dict(mu=.416,seed=seed,control_period=.02,objective='First flat metre against the unmodified scorer, then continue the same episode safely toward the physical slope.',
        grid='Four timed subsecond directional actions. Six equally spaced orientations about the paddle, both feed-forward tilt and feedback relative to the two ball centres. Widest windows precede the observed terminal air ticks. Eight adaptive stages maximum.'))
    with ProcessPoolExecutor(4) as pool:
        for level in range(8):
            layer=OUT/f'l{level:02d}'; layer.mkdir(exist_ok=True)
            live=[];jobs=[]
            for slot,r in enumerate(beam):
                end=r['seconds']; loss_back=[1.42,1.0,.68,.39][(slot+level)%4]
                tick=round((end-loss_back)/.02)
                rng=np.random.default_rng(735840+level*31+slot)
                angles=np.arange(6)*np.pi/3+rng.uniform(0,.9)
                cand=[None]
                for typ in range(3):
                    for a in angles:
                        mag=float(rng.uniform(.040,.16) if typ<2 else rng.uniform(.016,.055))
                        action=dict.fromkeys(('pitch','roll','speed','yaw','hip','lateral','neck','span','damp'),0.)
                        action.update(duration=float(rng.choice([.16,.28,.42,.64,.88])))
                        if typ==0:
                            action['pitch']=mag*np.cos(a);action['roll']=mag*np.sin(a)
                            action['damp']=rng.uniform(0,.5)
                        if typ==1:
                            action.update(style='opening',direction=mag*np.cos(a),tangent=mag*np.sin(a),
                                         relative=rng.uniform(-.65,.8),memory=rng.uniform(-.28,.55),
                                         yawphase=rng.uniform(-.24,.24),neckphase=rng.uniform(-.060,.060),frequency=0.)
                        if typ==2:
                            action.update(hip=mag*np.cos(a),lateral=mag*np.sin(a),yaw=rng.uniform(-.17,.27),
                                          speed=rng.uniform(.05,.52),neck=rng.uniform(-.045,.045))
                        cand.append(action)
                live.append((r,tick,cand))
                for part in range(2):
                    jobs.append((MODE,seed,r['actions'],dict(tick=tick,slot=slot,folder=layer,members=[(k,a) for k,a in enumerate(cand) if k%2==part]),None))
            list(pool.map(simulate,jobs))
            children=[]
            for slot,(r,tick,cand) in enumerate(live):
                siblings=[read(layer/f'{slot}-{i:02d}.json') for i in range(len(cand))]
                assert siblings[0]['last_both_m']==r['last_both_m'] and len({q['fork_sha'] for q in siblings})==1
                for a,q in zip(cand,siblings):
                    q['actions']=r['actions']+([dict(tick=tick,**a)] if a is not None else []);children.append(q)
            ranked=sorted([best,*beam,*children],key=key,reverse=True)
            best=ranked[0];beam=[]
            for q in ranked:
                if all(abs(q['last_both_m']-p['last_both_m'])>.00045 or abs(q['seconds']-p['seconds'])>.03 for p in beam):beam.append(q)
                if len(beam)==4:break
            hist.append(dict(level=level,n=len(children),m=best['last_both_m'],s=best['seconds'],flat=best['flat_1m'],top=[r['last_both_m'] for r in beam]))
            save(OUT/'history.json',hist);save(OUT/'winner.json',compact(best));print(hist[-1],flush=True)
            if best['finish_2p5']:break
    rr=simulate((MODE,seed,best['actions'],None,OUT/'trajectory.npz'))
    assert rr['last_both_m']==best['last_both_m']
    save(OUT/'result.json',dict(result=compact(rr),initial=compact(best0),seed=seed,selected_actions=best['actions'],branches=sum(r['n'] for r in hist),mu=.416))
if __name__=='__main__':main()
