"""Render the median distance gain among positive two-second paired holdout changes."""
import csv
import hashlib
import subprocess
import sys
from unittest.mock import patch
import train_opening as t

sys.path.insert(0,str(t.SHORT/'media'))
import film


def main():
    rows=list(csv.DictReader((t.HERE/'validation.csv').open()))
    names=['medium','phase_08']
    by={n:{int(r['seed']):r for r in rows if r['material']=='high' and r['name']==n} for n in names}
    cases=[(float(by[names[1]][s]['m'])-float(r['m']),s) for s,r in by[names[0]].items()
           if r['both2']=='False' and by[names[1]][s]['both2']=='True']
    cases.sort()
    seed=cases[len(cases)//2][1]
    meta={}
    traces=t.HERE/'film-traces'
    traces.mkdir(exist_ok=True)
    for i,name in enumerate(names):
        trace=traces/f'{name}.npz'
        row=t.run_seed(seed,'high',name,trace)
        assert row['m']==float(by[name][seed]['m']) and row['t']==float(by[name][seed]['t'])
        label=['原有中档控制','按左右脚支撑相位调头、倾拍与步速'][i]
        with patch.object(film,'ROOT',t.HERE):
            film.encode(trace,t.HERE/f'video-{name}.mp4',f'{label} · μ=0.416 · 起点{seed}',rate=25.)
        meta[name]=row
    dest=t.HERE/'opening-paired.mp4'
    cmd=['ffmpeg','-y','-loglevel','error','-i',str(t.HERE/'video-medium.mp4'),'-i',str(t.HERE/'video-phase_08.mp4'),
         '-filter_complex','[0:v][1:v]hstack=inputs=2:shortest=0,scale=1440:-2','-c:v','libx264',
         '-preset','fast','-crf','19','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
    subprocess.run(cmd,check=True)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(dest),'-f','null','-'],check=True)
    t.write('opening-paired.json',dict(seed=seed,selection='median distance change among holdout high-mu pairs gaining simultaneous contact at 2 s',
            n_gain_cases=len(cases),runs=meta,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))


if __name__=='__main__':main()
