"""Teach measured residual actions from two development rollouts to a delayed-camera controller."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from unittest.mock import patch
import ast
import inspect
import json
import numpy as np
from scipy.spatial import cKDTree
from material import HERE,RECIPE,SHORT,actors,cp,save,short_track,study,surface

OUT=HERE/'imitation';OUT.mkdir(exist_ok=True)
FEATURE_SCALE=np.array([.027,.027,.12,.12,.045,.045,.12,.12,.02,.08,.14,.14,.010])


def features(a,b):
    za,zb=a.measurements[0],b.measurements[0]
    centre=(za+zb)*.5
    outer,inner=(za,zb) if za[:2]@za[:2]>=zb[:2]@zb[:2] else (zb,za)
    delta=outer-inner;distance=max(.006,np.linalg.norm(delta[:2]))
    radial=(delta[:2]@delta[2:])/distance
    lf=a.m.geom('left_foot_collision').id;rf=a.m.geom('right_foot_collision').id
    foot=a.d.geom_xpos[lf,2]-a.d.geom_xpos[rf,2]
    return np.clip(np.r_[centre,delta,distance,radial,a.d.site_xmat[a.site].reshape(3,3)[2,:2],foot]/FEATURE_SCALE,-5,5)


def teach():
    e=cp.transfer
    old=inspect.getsource(e.previous.simulate)
    token="        if np.any(bias):ch.plate_bias"
    assert old.count(token)==1
    src=old.replace(token,"        capture(ch,peer[0],bias,j,multiplier(t+1))\n"+token)
    tree=ast.parse(src)
    used=set()
    for block in ast.walk(tree):
        if not isinstance(block,ast.Try):continue
        for i,node in enumerate(block.body):
            if not isinstance(node,ast.Assign) or len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name):continue
            k=node.targets[0].id
            if k in ('r','result'):
                line="r=dispatch(SEED,spec['params'],savepath)" if k=='r' else 'result=score_row(r,state,active_schedule)'
                block.body[i]=ast.parse(line).body[0];used.add(k)
    assert used=={'r','result'}
    xs=[];ys=[];records=[]
    for mode in ('high','record'):
        meta=json.loads((HERE/'approach'/mode/'result.json').read_text())
        xx=[];yy=[]
        def capture(a,b,bias,j,pace):
            xx.append(features(a,b));yy.append(np.r_[bias,j,pace-1])
        env={**e.NS,'capture':capture,'SEED':12600381}
        exec(compile(ast.fix_missing_locations(tree),'measured_demonstration','exec'),env)
        with surface(mode),patch.object(e,'SIMULATE',env['simulate']):
            result=e.run('fixed',12600381,actions=meta['selected_actions'])
        assert abs(result['last_both_m']-meta['result']['last_both_m'])<1e-8
        keep=len(xx)-15  # The last 0.30 s already lead into the known loss.
        xs.extend(xx[:keep]);ys.extend(yy[:keep])
        records.append(dict(mode=mode,seed=12600381,frames=len(xx),usable=keep,m=result['last_both_m']))
    np.savez_compressed(OUT/'examples.npz',x=np.asarray(xs),y=np.asarray(ys))
    save(OUT/'teachers.json',records)


@lru_cache(maxsize=1)
def examples():
    with np.load(OUT/'examples.npz') as z:x,y=z['x'].copy(),z['y'].copy()
    return cKDTree(x),y


def run(job):
    seed,mat,spec=job
    tree,yy=examples()
    k,bandwidth,gain=spec
    params=actors.configured(study.BASE['params'],RECIPE)
    state={'tick':None,'value':np.zeros(11),'queue':None,'both2':False,'peak':0.}
    base=short_track.Meter.observe
    def meter(m,t,x,fail,on,audit,bc):
        base(m,t,x,fail,on,audit,bc)
        if m.valid and on:
            state['peak']=max(x,state['peak'])
            if abs(t-2.)<1e-8:state['both2']=True
    def update(bc):
        if state['tick']==bc.tick:return
        state['tick']=bc.tick
        dist,idx=tree.query(features(*bc.channels),k=k)
        weights=np.exp(-.5*((dist-dist.min())/bandwidth)**2)
        value=np.average(yy[idx],axis=0,weights=weights)
        state['value']=.55*state['value']+.45*gain*value*np.exp(-.5*(dist.min()/bandwidth)**2)
    with surface(mat),actors.controller(RECIPE,study.BASE['settings']) as mon:
        old_drive=actors.locomotion.Locomotion.control;old_head=cp.ball.BallChannel.control
        def drive(w,d,speed):
            bc=mon['live']
            if bc is not None and bc.d is d:
                update(bc);speed*=np.clip(1+state['value'][-1],.5,1.5)
            return old_drive(w,d,speed)
        def head(ch,estimate=None):
            bc=mon['live']
            if bc is None or ch is not bc.channels[0]:return old_head(ch,estimate)
            update(bc);v=state['value'];bias=getattr(ch,'plate_bias',np.zeros(2))
            ch.plate_bias=np.clip(bias+v[:2],-.28,.28)
            if state['queue'] is None:
                state['queue']=deque([np.zeros(8)]*(1+ch.act_lag),maxlen=1+ch.act_lag)
                ids=np.array([ch.m.actuator(n).id for n in cp.transfer.previous.JOINTS])
                state['ids']=ids;state['bounds']=ch.m.jnt_range[ch.m.actuator_trnid[ids,0]]
            state['queue'].append(v[2:10].copy())
            ids=state['ids'];bounds=state['bounds']
            ch.d.ctrl[ids]=np.clip(ch.d.ctrl[ids]+state['queue'][0],bounds[:,0],bounds[:,1])
            try:return old_head(ch,estimate)
            finally:ch.plate_bias=bias
        with patch.object(short_track.Meter,'observe',meter),patch.object(actors.locomotion.Locomotion,'control',drive),patch.object(cp.ball.BallChannel,'control',head):
            r=short_track.run('combined',seed,params,timeout=45)
    return dict(seed=seed,mode=mat,m=r['last_both_m'],peak=state['peak'],both2=state['both2'],flat=r['flat_1m'],
                slope=r['slope_1m'],finish=r['finish_2p5'],torque=max(r['motor']['peak_nm']))


def score(rows):
    return dict(n=len(rows),finish=sum(q['finish'] for q in rows),slope=sum(q['slope'] for q in rows),flat=sum(q['flat'] for q in rows),
                half=sum(q['peak']>=.5 for q in rows),quarter=sum(q['peak']>=.25 for q in rows),both2=sum(q['both2'] for q in rows),
                mean=float(np.mean([q['m'] for q in rows])),max_m=max(q['m'] for q in rows))


def main():
    controls=[(4,1.,0.),(4,1.,.5),(4,1.8,1.),(12,1.5,1.),(24,2.5,1.5),(12,2.5,.5)]
    save(OUT/'protocol.json',dict(controls=controls,develop=[17360000,17360035],fresh=[17361000,17361127],
            rank=['finish','slope','flat','half','quarter','both2','mean'],materials=['high','wide']))
    teach()
    with ProcessPoolExecutor(4) as pool:
        dev=[]
        for spec in controls:
            rr=list(pool.map(run,[(s,m,spec) for s in range(17360000,17360036) for m in ['high','wide']],chunksize=4))
            dev.append(score(rr))
        winner=max(range(1,len(dev)),key=lambda i:tuple(dev[i][k] for k in ('finish','slope','flat','half','quarter','both2','mean')))
        save(OUT/'choice.json',dict(index=winner,spec=controls[winner],scores=dev))
        out={}
        for i in (0,winner):
            for m in ('high','wide'):
                rr=list(pool.map(run,[(s,m,controls[i]) for s in range(17361000,17361128)],chunksize=4))
                out[f'{i}/{m}']=dict(summary=score(rr),rows=rr)
        save(OUT/'transfer.json',out)


if __name__=='__main__':main()
