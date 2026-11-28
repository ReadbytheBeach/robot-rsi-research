"""Recount gates and describe paired changes across natural outward release speeds."""
import csv
import json
import math
import numpy as np
import train_opening as t
import release_groups


def main():
    with (t.HERE/'validation.csv').open() as f:
        rows=list(csv.DictReader(f))
    summary=json.loads((t.HERE/'validation.json').read_text())
    output={}
    group_rows={}
    rng=np.random.default_rng(2284)
    rates={}
    for seed in sorted(set(int(r['seed']) for r in rows)):
        pos,vel,us=release_groups.release(seed)
        rates[seed]=release_groups.features(pos,vel,us)['separation_rate_mm_s']
    old=json.loads((t.PILOT/'release_groups.json').read_text())['groups']['separation_rate_mm_s']
    breaks=[(a['max']+b['min'])/2 for a,b in zip(old,old[1:])]
    for mat in ('high','wide','nominal'):
        groups=[sorted((r for r in rows if r['name']==n and r['material']==mat),key=lambda r:r['seed'])
                for n in ('medium','phase_08')]
        for rr in groups:
            s=summary[rr[0]['name']][mat]
            assert len(rr)==len(set(r['seed'] for r in rr))==s['n']
            for key in ('flat','slope','finish','qtr','half','both2'):
                assert sum(r[key]=='True' for r in rr)==s[key]
        a,b=groups
        assert [r['seed'] for r in a]==[r['seed'] for r in b]
        x=sum(r['both2']=='False' and s['both2']=='True' for r,s in zip(a,b))
        y=sum(r['both2']=='True' and s['both2']=='False' for r,s in zip(a,b))
        m=np.array([float(s['m'])-float(r['m']) for r,s in zip(a,b)])
        p=min(1,2*sum(math.comb(x+y,i) for i in range(min(x,y)+1))*2**-(x+y))
        q=np.quantile(m[rng.integers(0,len(m),(8000,len(m)))].mean(axis=1),[.025,.975])
        output[mat]=dict(gain=x,loss=y,mcnemar_exact=p,delta_mean_mm=m.mean()*1000,bootstrap95_mm=(q*1000).tolist())
        bins=np.digitize([rates[int(r['seed'])] for r in a],breaks)
        group_rows[mat]=[]
        for i in range(4):
            aa=[r for j,r in enumerate(a) if bins[j]==i]
            bb=[r for j,r in enumerate(b) if bins[j]==i]
            group_rows[mat].append(dict(group=i,n=len(aa),
              base_both2=sum(r['both2']=='True' for r in aa),trained_both2=sum(r['both2']=='True' for r in bb),
              base_mean=float(np.mean([float(r['m']) for r in aa])),trained_mean=float(np.mean([float(r['m']) for r in bb]))))
    t.write('paired.json',output)
    t.write('release-subgroups.json',dict(historical_cutoffs_mm_s=breaks,rows=group_rows,
        definition='fixed previous 768-start radial speed quartile cutoffs; true release used only for retrospective subgroup audit'))
    print(group_rows['high'],flush=True)


if __name__=='__main__':main()
