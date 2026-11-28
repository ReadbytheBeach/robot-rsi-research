"""Independent 1° ramp. Learn bounded actions at fixed maximum ball–face sliding friction."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from unittest.mock import patch
import argparse,csv,json,sys
import numpy as np

HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'pingpong-dual16-short-20261128'
sys.path[:0]=[str(HERE.parent/'friction'),str(OLD/'geometry/isolation')]
from sweep import material,MAX_ARM,cp
import start_modes as sm
import fit_preparation as prep

def read(path):
    return json.loads(path.read_text())
def save(name,data):
    path=HERE/name
    tmp=path.with_suffix('.part')
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)

def configs():
    p=OLD/'replay'; iso=OLD/'geometry/isolation'
    original=read(p/'first-slope-pass-proof.json')
    brake=read(p/'slope-brake.json.stats')
    base=lambda seed,mode='original':dict(seed=seed,mode=mode,scale=1.,values=None,actions=[],brake=None)
    out=[base(original['actual']['seed'])|{'actions':original['actions']}]
    b=brake['selected'];out.append(base(b['seed'])|{'actions':brake['input']['actions'],'brake':[b[k] for k in ('finish_buffer','stop_ramp_s','max_wait')]})
    for seed,mode in ((14402734,'settle_short'),(14402572,'settle_long')):
        d=read(iso/f'sprint-{seed}/result.json')
        values=read(iso/'prep-fit-1-14402734/fit.json')['best']['values'] if seed==14402734 else None
        out.append(base(seed,mode)|dict(actions=d['actions'],values=values))
    return base,out

def run(config,arm=MAX_ARM,trace=None,fork=None):
    p=sm.parameters(config['mode']) if config['values'] is None else prep.prepare(config['mode'],config['values'])
    if config.get('brake') is not None:
        buf,ramp,wait=config['brake']
        for q in [p,*p.get('by_order',{}).values(),*(v['overrides'] for v in p.get('latency_profiles',[]))]:
            q['finish_buffer']=buf;q['stop_ramp_s']=ramp
            if wait:q['stop_gate']=dict(radius=.02,velocity=.12,max_wait_s=wait)
            else:q.pop('stop_gate',None)
    with material(arm) as info, patch.dict(cp.transfer.NS,spec=dict(cp.transfer.previous.spec,params=p)):
        r=cp.transfer.run('incline',config['seed'],config['scale'],actions=config['actions'],trace=trace,fork=fork)
    if fork is not None:return None
    return dict(config=config,arm=arm,mu=[info[n][1] for n in cp.NAMES],row=r)

def rank(z):
    r=z['row']
    return (r['success'],r['slope_1m'],min(1,r['stable_finish_s']),r['last_both_m'] if r['max_tilt_deg']<30 else 0.)

def screen():
    base,archive=configs()
    anchors=[dict(ref=r,upper=run(c),wide=run(c,'wide')) for c,r in zip(archive,[1.057638828419607,1.0277153888384778,1.0389947736000003,1.0108164131951227])]
    for z in anchors:assert abs(z['wide']['row']['last_both_m']-z['ref'])<1e-12
    save('known-transfers.json',anchors)
    p=OLD/'replay';iso=OLD/'geometry/isolation'; e=OLD/'training/enrichment'
    old_a=sorted(read(p/'incline-mine-14550000.json'),key=lambda z:z['last_both_m'],reverse=True)[:96]
    old_b=sorted(read(iso/'mine.json')['rows'],key=lambda z:z['end'],reverse=True)[:96]
    with (e/'physical.csv').open() as f:prev=sorted([r for r in csv.DictReader(f) if r['track']=='incline'],key=lambda x:float(x['last_both_m']),reverse=True)
    subset=list(dict.fromkeys(int(r['seed']) for r in prev))[:128]
    jobs=[*archive,*[base(z['seed']) for z in old_a],*[base(z['seed'],z['mode']) for z in old_b],*[base(i) for i in subset]]
    for c in archive:
        for scale in (.85,.95,1.06,1.15,1.25,1.40):
            jobs.append(dict(c,scale=scale))
    jobs=list({json.dumps(c,sort_keys=True):c for c in jobs}.values())
    save('protocol.json',dict(target='isolated physical 1 degree uphill ramp from release, both contacting at 1 horizontal metre and parked a full second; no ball reset',mu=.416,
        full_width='original effective ball-paddle distribution as archive control',screen=jobs,rate_seed=[17781000,17781127],use='screen deliberately uses previously opened development starts; never count these as independent holdout'))
    with ProcessPoolExecutor(6) as pool: rows=list(pool.map(run,jobs,chunksize=3))
    rows.sort(key=rank,reverse=True);save('screen.json',rows)
    print('anchors',[(z['upper']['config']['seed'],z['upper']['row']['last_both_m']) for z in anchors],flush=True)
    print('screen',len(jobs),[(r['config']['seed'],r['config']['mode'],r['row']['last_both_m']) for r in rows[:8]],flush=True)

def new_action(rng,finish,i):
    t=finish*rng.uniform(.24,.85) if i%4 else rng.uniform(.06,max(.09,min(3.2,finish-.22)))
    if i%6==4:t=max(.08,finish-rng.uniform(.30,2.4))
    a={k:0. for k in ('pitch','roll','damp','speed','neck','hip','lateral','yaw','span')}
    a.update(tick=max(1,round(t/.02)),duration=float(rng.choice([.18,.42,.82,1.4,2.3,3.4])))
    if i%5==0:a.update(pitch=rng.uniform(-.08,.08),roll=rng.uniform(-.09,.09),damp=rng.uniform(-.28,.38))
    elif i%5==1:a.update(span=rng.uniform(-.11,.11),yaw=rng.uniform(-.14,.14),speed=rng.uniform(-.16,.27))
    else:a.update(speed=rng.uniform(-.32,.52),neck=rng.uniform(-.04,.04),damp=rng.uniform(-.2,.31))
    return a

def add_jobs(best,rng,count,layer):
    jobs=[];c=best['config'];r=best['row'];end=r['seconds']
    for i in range(count):
        q=deepcopy(c)
        if (r['slope_1m'] and i%3!=0) or (r['last_both_m']>.8 and i%5==4):
            q['brake']=[float(rng.choice([-.04,-.02,0.,.01,.025,.045,.065,.09])),float(rng.choice([.02,.04,.1,.2,.32,.55])),float(rng.choice([0.,.08,.12,.24,.42]))]
        elif layer in (0,2,5,9) and i%6==3:
            q['scale']=np.clip(c['scale']+rng.normal(0,.11),.65,1.5)
        elif layer in (0,3,7) and i%8==6:
            v=prep.start(c['mode']) if c['values'] is None else np.array(c['values'])
            v=np.clip(v+rng.normal(size=len(v))*prep.SCALES*.18,prep.LO,prep.HI)
            q['values']=v.tolist()
        else:q['actions'].append(new_action(rng,end,i+layer))
        jobs.append(q)
    return jobs

def train():
    rng=np.random.default_rng(4160208)
    screen=read(HERE/'screen.json')
    distinct={}
    for r in screen:
        distinct.setdefault(r['config']['seed'],r)
    beam=list(distinct.values())[:5];best=beam[0];rows=[];stale=0
    with ProcessPoolExecutor(6) as pool:
        for layer in range(15):
            jobs=[]
            for i,b in enumerate(beam):jobs+=add_jobs(b,rng,21 if i==0 else 11,layer)
            new=list(pool.map(run,jobs,chunksize=2))
            previous=best
            ordered=sorted(beam+new,key=rank,reverse=True)
            best=ordered[0];stale=stale+1 if best['row']['last_both_m']<previous['row']['last_both_m']+.001 and best['row']['stable_finish_s']<=previous['row']['stable_finish_s'] else 0
            gates=dict(layer=layer,n=len(jobs),seed=best['config']['seed'],m=best['row']['last_both_m'],gate=best['row']['slope_1m'],hold=best['row']['stable_finish_s'],park=best['row']['success'])
            rows.append(gates);save('best.json',best);save('progress.json',rows);print(gates,flush=True)
            if best['row']['success'] or stale>=6:break
            ids=set();beam=[]
            for d in ordered:
                sig=(d['config']['seed'],round(d['row']['last_both_m'],3))
                if sig in ids: continue
                if sum(v['config']['seed']==sig[0] for v in beam)>=(2 if layer<4 else 4):continue
                beam.append(d);ids.add(sig)
                if len(beam)==5:break
    verified=run(best['config'],trace=HERE/'high-slope.npz')
    assert verified['row']==best['row']
    save('holdout-policy.json',best['config'])
    jobs=[dict(best['config'],seed=s) for s in range(17781000,17781128)]
    with ProcessPoolExecutor(5) as pool:held=list(pool.map(run,jobs,chunksize=4))
    save('holdout.json',dict(n=len(held),slope=sum(z['row']['slope_1m'] for z in held),park=sum(z['row']['success'] for z in held),max_m=max(z['row']['last_both_m'] for z in held),rows=[z['row'] for z in held]))
    print('independent',sum(z['row']['slope_1m'] for z in held),sum(z['row']['success'] for z in held),flush=True)

if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('stage',choices=['all','screen','train']);args=cli.parse_args()
    if args.stage in ('all','screen'):screen()
    if args.stage in ('all','train'):train()
