"""Verify and optionally render the paired holdout replay; write the fixed-start report."""
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch
import json
import subprocess
import sys
import numpy as np
from train import HERE,hs
sys.path.insert(0,str(hs.OLD/'media'))
import film

def read(name):return json.loads((HERE/name).read_text())

def encode(job):
    stem,title=job
    with patch.object(film,'ROOT',HERE):film.encode(HERE/(stem+'.npz'),HERE/(stem+'-original-speed.mp4'),title,rate=25.)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(HERE/(stem+'-original-speed.mp4')),'-f','null','-'],check=True)

def report():
    r=read('result.json');e=read('example.json');held=read('unseen-material-paired.json');w=read('frozen.json')
    for label in ('baseline','trained'):
        saved=read('paired-'+label+'.json')
        with np.load(HERE/('paired-'+label+'.npz')) as z:
            assert np.allclose(z['t'][-1],saved['seconds']) and saved['last_both_m']==e[label]['m']
            if e[label]['gate']:
                gate=saved['gates']['slope_1m'];j=np.flatnonzero(np.isclose(z['t'],gate['t']))
                assert len(j)==1 and z['ball_contacts'][j[0]].all()
            if e[label]['park']:
                assert saved['success'] and saved['stable_finish_s']>=1.0
    ds=np.array([b['m']-a['m'] for a,b in zip(held[0]['rows'],held[1]['rows'])])
    p=r['counts'];n=r['n_materials']
    lines=['# 独立坡道的窄摩擦区间与停车迁移','',
        f'同一个已打开的释放起点 {r["release_seed"]}、同一条 1° 坡、两颗 16 毫米球和 40 克平拍。将两组球–拍面的滑动摩擦共同固定在每回合指定的 μ，保留原始滚动与扭转摩擦、释放状态、执行延时和 0.20 N·m 扭矩上限。成功要求双球实际触拍越过一米并按原始规则停车满一秒。','',
        f'以 μ=0.416 的停车动作和同起点的另一停车动作初始化。在五个均匀分布的固定训练材料上微调步速、减速点和时间、停车等待及既有动作幅度与时刻，另尝试在此前最差摩擦的失球前小幅纠偏。训练共 {p["candidates"]} 套候选、{p["train_rollouts"]} 次回合。再用四个额外开发材料比较入围方案，总计 {p["selection_rollouts"]} 次。训练和选型先按停车个数、过线个数，然后按最差里程、低分位里程排序。','',
        '冻结所选参数后，对区间 [0.414, 0.416] 内事先独立均匀抽出的 48 个新摩擦值做配对复验，共 96 次。每次都从同一已知开发起点重新释放，两种策略受相同外界扰动。表中分母是材料抽样个数。','',
        '| 条件 | 材料数 | 双球过坡一米 | 过坡且停车 | 最差末次双球接触 m | 平均有效距离 m（截至 1 m） |',
        '|---|---:|---:|---:|---:|---:|']
    for label,q,k in [('原动作开发材料',r['baseline_development'],9),('训练后开发材料',r['developed'],9),('原动作新摩擦',r['baseline'],48),('训练后新摩擦',r['trained'],48)]:
        lines.append(f"| {label} | {k} | {q['gate']}/{k} | {q['park']}/{k} | {q['min_m']:.4f} | {q['mean_safe']:.4f} |")
    lines.extend(['',f'逐对观察，新策略单独停车 {len(r["paired_gain"])} 次、原策略单独停车 {len(r["paired_loss"])} 次。末次双球有效里程的配对变化中位数为 {np.median(ds)*1000:+.2f} 毫米，有 {sum(ds>1e-9)} 组进步、{sum(ds< -1e-9)} 组退步。该结果描述固定起点的材料迁移。随机新起点的停车率须使用另一个实验的随机释放数据。','',
       f'保留的一对从释放重跑采用 μ={e["material"]:.9f}。原动作最后双球触拍 {e["baseline"]["m"]:.4f} 米，微调后 {e["trained"]["m"]:.4f} 米。该样本优先选择新增停车的材料；若没有，则选训练策略能停车的材料；若两者都没有，则选里程改善最大的一组。','',
       '[原策略](../slope/sprint-best.json) · [训练代码](train.py) · [冻结参数](frozen.json) · [独立摩擦逐对结果](unseen-material-paired.json) · [回放选择与实测门槛](example.json)'])
    aa=w['baseline']['actions'];bb=w['config']['actions']
    changed=[(i,a,b) for i,(a,b) in enumerate(zip(aa,bb)) if a!=b]
    if len(changed)==1 and len(aa)==len(bb):
        _,a,b=changed[0]
        if set(k for k in a if a[k]!=b[k])=={'duration'}:
            lines.extend(['',f'最终保留下来的改变只有一处：松球后 {a["tick"]*.02:.2f} 秒那次步速和颈部修正从 {a["duration"]:.2f} 秒缩短为 {b["duration"]:.2f} 秒。'])
    worst_idx=int(np.argmin(ds));worst_a=held[0]['rows'][worst_idx];worst_b=held[1]['rows'][worst_idx]
    lines.extend(['',f'退步最大的一组 μ={worst_a["mu"]:.9f}，有效里程从 {worst_a["m"]:.4f} 米降到 {worst_b["m"]:.4f} 米。'])
    if (HERE/'paired-comparison.mp4').exists():lines+=['','[同一材料的原速对照视频](paired-comparison.mp4)']
    path=next(iter(HERE.glob('固定起点窄摩擦停车迁移_*.md')),HERE/f"固定起点窄摩擦停车迁移_{datetime.now(ZoneInfo('Asia/Singapore')).strftime('%Y%m%d_%H%M%S')}.md")
    path.write_text('\n'.join(lines)+'\n')
    print(path,flush=True)
    return e
if __name__=='__main__':
    e=report()
    if len(sys.argv)>1 and sys.argv[1]=='--film':
        with ProcessPoolExecutor(2) as pool:
            list(pool.map(encode,[('paired-baseline','原策略 · 固定起点 · μ '+f'{e["material"]:.7f}'),('paired-trained','窄区间训练 · 固定起点 · μ '+f'{e["material"]:.7f}')]))
        max_sec=max(e['baseline']['t'],e['trained']['t'])+.04
        f=';'.join(f'[{i}:v]scale=768:444,tpad=stop_mode=clone:stop_duration={max_sec},trim=duration={max_sec},setpts=PTS-STARTPTS[v{i}]' for i in (0,1))+';[v0][v1]hstack[out]'
        cmd=['ffmpeg','-v','error','-nostdin','-y','-i',str(HERE/'paired-baseline-original-speed.mp4'),'-i',str(HERE/'paired-trained-original-speed.mp4'),'-filter_complex',f,'-map','[out]','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(HERE/'paired-comparison.mp4')]
        subprocess.run(cmd,check=True);subprocess.run(['ffmpeg','-v','error','-nostdin','-xerror','-i',str(HERE/'paired-comparison.mp4'),'-f','null','-'],check=True)
        report()
