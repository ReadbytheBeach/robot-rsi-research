"""Learn a causal trigger for the four successful uphill action pulses."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
from unittest.mock import patch

import numpy as np

from high_slope import HERE, cp, read, run


DEST = HERE/'observed'
DEST.mkdir(exist_ok=True)
TEACHER = read(HERE/'sprint-best.json')
TIMED = dict(name='timed',distance=1.,lookahead=0.,risk=None,orient=0.)
TRAIN = range(17841000,17841036)
SELECT = range(17842000,17842064)
TEST = range(17843000,17843192)


def save(name, value):
    p = DEST/name
    tmp = p.with_suffix('.part')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(p)


def get_reference():
    ref = np.load(HERE/'sprint.npz')['progress_m']
    ticks = [a['tick'] for a in TEACHER['config']['actions']]
    assert all(ref[:t].max() < ref[t] for t in ticks)
    return [(ref[t]+ref[:t].max())*.5 for t in ticks]


LANDMARKS = get_reference()


class Trigger:
    def __init__(self, recipe, actions):
        self.recipe = recipe
        self.actions = actions
        self.original_ticks = [a['tick'] for a in actions]
        self.order = sorted(range(len(actions)),key=lambda i:self.original_ticks[i])
        self.landmarks = np.array(LANDMARKS)*recipe['distance']
        self.events = []
        self.last_tick = -999
        if recipe['name']!='timed':
            for a in self.actions:
                a['tick'] = 2**24

    def update(self, progress, tick, measurements):
        if not self.order:
            return
        idx = self.order[0]
        p = self.recipe
        z = np.asarray(measurements)
        predicted = z[:,:2] + p['lookahead']*z[:,2:]
        radii = np.linalg.norm(predicted,axis=1)
        danger = int(np.argmax(radii))
        why = None
        if p['name']=='timed':
            if tick==self.original_ticks[idx]:
                why='time'
        elif progress>=self.landmarks[idx]:
            why='distance'
        elif p['risk'] is not None and tick>=p['launch_ticks'] and tick-self.last_tick>=p['refractory_ticks']:
            if radii[danger]>=p['risk']:
                why='projected_edge'
        if why is None:
            return
        self.order.pop(0)
        a = self.actions[idx]
        a['tick'] = tick
        if why=='projected_edge' and p['orient'] and np.hypot(a['pitch'],a['roll'])>0:
            direction = predicted[danger]/max(.001,radii[danger])
            a['pitch'],a['roll'] = np.hypot(a['pitch'],a['roll'])*p['orient']*direction
        self.last_tick = tick
        self.events.append(dict(pulse=idx,source_tick=self.original_ticks[idx],tick=tick,
                                trigger=why,progress_m=float(progress),predicted_edge_m=float(radii[danger])))


def episode(job, trace=None):
    recipe,seed=job
    cfg = deepcopy(TEACHER['config'])
    cfg['seed'] = seed
    trigger = Trigger(recipe,cfg['actions'])
    gates = dict(quarter=False,both_at_2s=False)
    base = cp.st.Meter.observe
    def observe(meter,t,dist,fail,on,audit,control):
        base(meter,t,dist,fail,on,audit,control)
        # Score only. Neither true contacts, failure, nor the meter's valid flag reach the trigger.
        if meter.valid and on and dist>=.25:
            gates['quarter']=True
        if abs(t-2.)<1e-8 and meter.valid and on:
            gates['both_at_2s']=True
        a,b=control.channels
        assert a.tick==b.tick
        trigger.update(dist,a.tick,[a.measurements[0],b.measurements[0]])
    with patch.object(cp.st.Meter,'observe',observe):
        raw=run(cfg,trace=trace)
    assert raw['mu']==[.416,.416]
    return dict(recipe=recipe['name'],events=trigger.events,mu=raw['mu'],**gates,**raw['row'])


def bank():
    out=[TIMED]
    for scale in (1.,.82,.60,.38,.20):
        out.append(dict(TIMED,name=f'odom-{scale}',distance=scale))
    for i,radius in enumerate((.026,.036,.046,.056)):
        for j,(look,orient,gap) in enumerate(((.14,0.,11),(.27,-1.,14),(.38,1.,18),(.22,-1.,26),(.38,-1.,8))):
            out.append(dict(name=f'predict-{i}-{j}',distance=(1.,.55,1.,.75,.35)[j],
                            risk=radius,lookahead=look,orient=orient,launch_ticks=(4,12,7,4,2)[j],
                            refractory_ticks=gap))
    return out


def evaluate(pool,recipes,seeds):
    return list(pool.map(episode,[(r,s) for s in seeds for r in recipes],chunksize=3))


def summary(rows,recipes):
    out={}
    for p in recipes:
        group=[r for r in rows if r['recipe']==p['name']]
        d=np.array([r['last_both_m'] for r in group])
        out[p['name']]=dict(n=len(group),park=sum(r['success'] for r in group),slope=sum(r['slope_1m'] for r in group),
                            quarter=sum(r['quarter'] for r in group),both_2s=sum(r['both_at_2s'] for r in group),
                            mean_m=np.mean(d),median_m=np.median(d),max_m=max(d),max_seed=group[np.argmax(d)]['seed'],
                            any_trigger=sum(bool(r['events']) for r in group))
    return out


def order(report,group):
    def score(r):
        a=report[r['name']]
        return (a['park'],a['slope'],a['quarter'],a['both_2s'],a['mean_m'])
    return sorted(group,key=score,reverse=True)


def main():
    candidates=bank()
    save('protocol.json',dict(mu=.416,teacher_seed=TEACHER['config']['seed'],landmarks_ordinal=LANDMARKS,
         training=[TRAIN.start,TRAIN.stop-1],selection=[SELECT.start,SELECT.stop-1],blind=[TEST.start,TEST.stop-1],
         training_candidates=candidates,priority=['park','1m','0.25m','both touching at 2s','mean distance'],
         sensors='release-aligned forward odometry and own delay buffers of both ball camera channels only; projected radius uses position+tau*velocity'))
    for p in candidates[:2]:
        r=episode((p,TEACHER['config']['seed']))
        assert r['success'] and r['last_both_m']==TEACHER['row']['last_both_m'] and len(r['events'])==4
        assert all(e['source_tick']==e['tick'] for e in r['events'])
    with ProcessPoolExecutor(5) as pool:
        rows=evaluate(pool,candidates,TRAIN)
        stats=summary(rows,candidates);save('train-summary.json',stats);save('train-rows.json',rows)
        top=order(stats,candidates[1:])
        final=[candidates[0],candidates[1],*top[:5]]
        final=list({r['name']:r for r in final}.values())
        select=evaluate(pool,final,SELECT)
        val=summary(select,final);save('select-summary.json',val);save('select-rows.json',select)
        scene=order(val,[p for p in final if p['name']!='timed'])[0]
        save('seal.json',dict(selected=scene,linked_primary='paired primary against original timed; pure odometry also included as fixed reference',range=[TEST.start,TEST.stop-1]))
        variants=list({p['name']:p for p in [TIMED,candidates[1],scene]}.values())
        held=evaluate(pool,variants,TEST);res=summary(held,variants)
    assert all(len({r['seed'] for r in held if r['recipe']==p['name']})==len(TEST) for p in variants)
    save('blind-rows.json',held);save('blind-summary.json',res)
    by=lambda p:{r['seed']:r for r in held if r['recipe']==p['name']}
    base=by(TIMED);new=by(scene);rng=np.random.default_rng(45121)
    boot=rng.integers(0,len(TEST),(12000,len(TEST)));delta=np.array([new[k]['last_both_m']-base[k]['last_both_m'] for k in TEST])
    paired=dict(mean_delta_m=delta.mean(),interval=np.quantile(delta[boot].mean(axis=1),[.025,.975]).tolist())
    for metric in ['success','slope_1m','quarter','both_at_2s']:
        paired[metric]=dict(gained=sum(new[k][metric] and not base[k][metric] for k in TEST),
                            lost=sum(base[k][metric] and not new[k][metric] for k in TEST))
    save('paired.json',paired)
    opened={p['name']:episode((p,TEACHER['config']['seed']),trace=DEST/(p['name']+'.npz')) for p in variants}
    save('opened.json',opened)
    print(json.dumps(dict(selected=scene,held=res,paired=paired),indent=2),flush=True)


if __name__=='__main__':
    main()
