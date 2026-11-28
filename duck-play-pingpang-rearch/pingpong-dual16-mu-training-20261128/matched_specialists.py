"""Give the lowest and highest allowable friction identical search budgets and paired tests."""
from concurrent.futures import ProcessPoolExecutor
import csv
import numpy as np
from decision_policy import HERE,op,save

OUT=HERE/'specialists';OUT.mkdir(exist_ok=True)
MATS=(.224,.416)


def episode(args):
    mu,name,seed=args
    return op.run_seed(seed,mu,name=name)


def stats(rows):
    return dict(n=len(rows),flat=sum(r['flat'] for r in rows),slope=sum(r['slope'] for r in rows),finish=sum(r['finish'] for r in rows),
                half=sum(r['half'] for r in rows),qtr=sum(r['qtr'] for r in rows),both2=sum(r['both2'] for r in rows),
                mean=float(np.mean([r['m'] for r in rows])),best=max(r['m'] for r in rows),best_seed=max(rows,key=lambda r:r['m'])['seed'])


def rank(v):
    return (v['finish'],v['slope'],v['flat'],v['half'],v['mean']+.12*v['both2']/v['n']+.2*v['qtr']/v['n'])


def batch(pool,bank,start,n,name):
    jobs=[(mu,arm,s) for s in range(start,start+n) for mu,arms in bank.items() for arm in arms]
    results=list(pool.map(episode,jobs,chunksize=6))
    with (OUT/(name+'.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    out={mu:{a:stats([r for r in results if r['material']==mu and r['name']==a]) for a in arms} for mu,arms in bank.items()}
    assert all(t['n']==n for by in out.values() for t in by.values())
    save(OUT/(name+'.json'),out)
    return out


def main():
    save(OUT/'protocol.json',dict(materials=MATS,screen=[17550000,24],select=[17551000,64],test=[17552000,300],
         criterion='Rank finish, slope, flat, half counts, then mean last double-contact distance + 0.12 * P(both contact at 2s) + 0.20 * P(quarter metre)',
         comparison='All 41 identical action recipes in both materials, on identical starts. Cross-test both winners, the historical medium baseline and the phase_08 opening.'))
    with ProcessPoolExecutor(6) as pool:
        bank={mat:list(op.bank()) for mat in MATS}
        scr=batch(pool,bank,17550000,24,'screen')
        bank={mu:list(dict.fromkeys(['medium',*sorted(arms,key=lambda a:rank(scr[mu][a]),reverse=True)[:7]])) for mu,arms in bank.items()}
        sel=batch(pool,bank,17551000,64,'selection')
        chosen={mu:max(arms,key=lambda a:rank(sel[mu][a])) for mu,arms in bank.items()}
        held=list(dict.fromkeys(['medium','phase_08',*chosen.values()]))
        save(OUT/'frozen.json',dict(chosen=chosen,arms=held,independent_n=300))
        final=batch(pool,{mu:held for mu in (*MATS,.32)},17552000,300,'independent')
        print(chosen,[(m,n,round(v['mean'],4),v['half'],v['flat']) for m,d in final.items() for n,v in d.items()],flush=True)


if __name__=='__main__':main()
