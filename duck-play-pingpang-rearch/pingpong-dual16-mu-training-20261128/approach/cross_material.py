"""Run each frozen opened trajectory under controlled ball–paddle friction swaps."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch
import argparse
from search import HERE,BASES,SEED,cp,read,save


def job(args):
    name,mu,actions=args
    with patch.object(cp,'HISTORIC',mu),cp.surface('historic_fixed') as info:
        row=cp.transfer.run('fixed',SEED,1.,actions=actions)
    assert info['ball_geom'][1]==mu and info['ball_geom_b'][1]==mu
    return {k:row[k] for k in ('seed','gates','last_both_m','seconds','max_tilt_deg','reason')} | dict(name=name,mu=mu)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--high', default='high-catch')
    mode=ap.parse_args().high
    recipes={'old_teacher':read(BASES['record'])['actions'],'record_trained':read(HERE/'record/result.json')['selected_actions'],
             'high_trained':read(HERE/mode/'result.json')['selected_actions']}
    mus=[.224,.272,.320,cp.HISTORIC,.392,.416]
    with ProcessPoolExecutor(3) as pool:rows=list(pool.map(job,[(n,mu,a) for n,a in recipes.items() for mu in mus]))
    save(HERE/'material-transfer.json',dict(mu_grid=mus,seed=SEED,high_source=mode,rows=rows))
    for n in recipes:print(n,[(round(r['mu'],4),round(r['last_both_m'],3)) for r in rows if r['name']==n])
if __name__=='__main__':main()
