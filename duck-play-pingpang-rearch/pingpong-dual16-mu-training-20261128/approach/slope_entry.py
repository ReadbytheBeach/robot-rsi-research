"""Branch before the incline on support-phase, pace, camera spread and paddle edge reserve."""
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from search import HERE,SEED,read,save,compact,simulate

OUT=HERE/'slope-entry'
MODE='high'
DISTANCES=[.70,.76,.82,.87,.91,.94,.98,1.01,1.04,1.08]


def probe(row, target):
    # Use the recorded frame nearest this actual traveled distance; only logged before a veto and at simultaneous contact.
    pairs=[(int(k),np.asarray(p)) for k,p in row['probes'].items() if p[0]<=target+.035]
    if not pairs:return None
    return min(pairs,key=lambda q:abs(q[1][0]-target))


def order(row):
    ok=row['max_tilt_deg']<29.
    return (bool(ok and row['finish_2p5']),bool(ok and row['slope_1m']),
            row['last']['safe_slope_m'] if ok else 0.,row['last_both_m'] if ok else 0.)


def alternatives(rows,target,count):
    keep=[max(rows,key=order)]
    eligible=[(r,probe(r,target)) for r in rows if r['max_tilt_deg']<29.]
    eligible=[(r,p) for r,p in eligible if p is not None and abs(p[1][0]-target)<.075]
    def sig(f):
        _,p=f
        return np.array([p[1]/.004,p[3]/.018,p[8]/.011,p[9]/.011,p[10]/.04])
    # Diverging versus closing state, reserve after 0.23 s forecast, and gait speed / separations.
    for idx in range(count-1):
        def score(x):
            r,(_,p)=x
            margin=.055-p[1]; forecast=.055-p[6];outward=max(0.,p[3])
            if idx==0:return margin+1.25*forecast-.37*outward-.11*p[4]
            if idx==1:return .7*margin+.66*forecast-.65*p[3]-.42*p[2]
            return .75*margin+.39*forecast-.26*outward+.25*p[8]+.10*r['last_both_m']
        for r,p in sorted(eligible,key=score,reverse=True):
            old=[probe(k,target) for k in keep]
            if all(q is None or np.linalg.norm(sig(p)-sig(q))>.29 for q in old):
                keep.append(r);break
    if len(keep)<count:
        for r in sorted(rows,key=order,reverse=True):
            if all(abs(r['last_both_m']-b['last_both_m'])>.00045 for b in keep):keep.append(r)
            if len(keep)==count:break
    return keep[:count]


def actions(layer,slot):
    rng=np.random.default_rng(727364+layer*511+slot*31);bank=[None]
    for j in range(16):
        a=dict.fromkeys(('pitch','roll','damp','speed','neck','hip','lateral','yaw','span'),0.)
        a['duration']=float(rng.choice([.22,.36,.54,.72,1.,1.4]))
        if j<11:
            # The gait waveform in the original correction is the signed left-minus-right foot height.
            # Ball position/velocity estimates come from delivered camera measurements.
            ang=2*np.pi*(j%6)/6+rng.uniform(-.27,.27)
            amp=rng.uniform(.035,.16)
            a.update(style='gait',frequency=0.,direction=amp*np.cos(ang),tangent=amp*np.sin(ang),
                     relative=rng.uniform(-.95,.95),memory=rng.uniform(-.25,.78),
                     yawphase=rng.uniform(-.37,.37),neckphase=rng.uniform(-.08,.08),
                     speed=rng.uniform(-.23,.48),hip=rng.uniform(-.027,.027))
        else:
            a.update(style='opening',frequency=0.,direction=rng.uniform(-.12,.12),tangent=rng.uniform(-.10,.10),
                     relative=rng.uniform(-.55,.95),memory=rng.uniform(-.10,.70),
                     yawphase=rng.uniform(-.23,.23),neckphase=rng.uniform(-.05,.05),
                     speed=rng.uniform(-.16,.5),damp=rng.uniform(-.1,.55))
        bank.append(a)
    return bank


def main():
    OUT.mkdir(exist_ok=True)
    if not (OUT/'sources.json').exists():
        sources=[read(HERE/'high-catch/winner.json')['actions'], read(HERE/'first-high-metre/frozen.json')['actions'],
                 read(HERE/'high-continuation/result.json')['selected_actions'],read(HERE/'high/result.json')['selected_actions']]
        save(OUT/'sources.json',sources)
    sources=read(OUT/'sources.json')
    save(OUT/'protocol.json',dict(mu=.416,seed=SEED,course='fixed grid, slope foot at world x 1.02 m',launch_progress_m=DISTANCES,
         keep='distance leader plus alternative predicted edge reserve and radial separation states; body tilt constrained under 29 deg for ranking',
         runtime_inputs='camera pair position/velocity, support difference, gait targets, clock; actual progress used to locate the development fork'))
    with ProcessPoolExecutor(4) as pool:
        base=list(pool.map(simulate,[(MODE,SEED,s,None,None) for s in sources]))
        for r,s in zip(base,sources):r['actions']=s
        best=max(base,key=order);baseline=best;beam=base;hist=[]
        for level,target in enumerate(DISTANCES):
            folder=OUT/f'l{level:02d}';folder.mkdir(exist_ok=True)
            jobs=[];parents=[]
            for slot,r in enumerate(beam):
                # First four stages launch at 0.70, 0.76, 0.82 and 0.87 m. For subsequent recovery
                # keep at least 0.22 simulated seconds before the recorded individual termination.
                z=probe(r,target+(.012*(slot-1)))
                if z is None:continue
                tick=min(z[0],max(5,round((r['seconds']-.22)/.02)))
                cand=actions(level,slot)
                parents.append((slot,r,tick,cand,z[1][0]))
                for part in range(2):jobs.append((MODE,SEED,r['actions'],dict(tick=tick,slot=slot,folder=folder,
                                      members=[(i,a) for i,a in enumerate(cand) if i%2==part]),None))
            list(pool.map(simulate,jobs))
            children=[]
            for slot,r,tick,cand,_ in parents:
                rr=[read(folder/f'{slot}-{i:02d}.json') for i in range(len(cand))]
                assert len({q['fork_sha'] for q in rr})==1 and rr[0]['last_both_m']==r['last_both_m']
                for q,a in zip(rr,cand):
                    q['actions']=r['actions']+([dict(tick=tick,**a)] if a else []);children.append(q)
            rows=[best,*beam,*children];best=max(rows,key=order)
            beam=alternatives(rows,DISTANCES[min(level+1,len(DISTANCES)-1)],4)
            hist.append(dict(stage=level,requested_m=target,prebranch_sample_m=[p[-1] for p in parents],
                    fork_s=[p[2]*.02 for p in parents],n=len(children),safe_m=best['last_both_m'],slope_m=best['last']['safe_slope_m'],
                    retained=[dict(total_dual=b['last_both_m'],feature=probe(b,DISTANCES[min(level+1,len(DISTANCES)-1)])[1].tolist()) for b in beam if probe(b,DISTANCES[min(level+1,len(DISTANCES)-1)]) is not None]))
            save(OUT/'history.json',hist);save(OUT/'winner.json',compact(best))
            print(level,target,hist[-1]['prebranch_sample_m'],hist[-1]['safe_m'],hist[-1]['slope_m'],flush=True)
            if best['finish_2p5']:break
        rr=simulate((MODE,SEED,best['actions'],None,OUT/'trajectory.npz'))
        assert rr['last_both_m']==best['last_both_m']
        save(OUT/'result.json',dict(seed=SEED,mu=.416,initial=compact(baseline),result=compact(rr),selected_actions=best['actions'],
             branches=sum(h['n'] for h in hist),probes=rr['probes']))
if __name__=='__main__':main()
