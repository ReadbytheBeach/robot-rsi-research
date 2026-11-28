"""Write the reproducible development-only physical training record in Chinese."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import subprocess
import numpy as np
import mujoco
import develop as d
import extend as e

def metrics(stem):
    meta=e.read(d.HERE/(stem+'.json'));model=d.e.short_track.render_model('combined',meta['track_origin_x_m'])
    data=mujoco.MjData(model);ids=[model.geom(n).id for n in ('ball_geom','ball_geom_b')]
    site=model.site('paddle_center').id
    with np.load(d.HERE/(stem+'.npz')) as z:
        rows=[]
        for offset in (1.2,.6,0.):
            idx=int(np.argmin(abs(z['t']-(meta['seconds']-offset))))
            data.qpos[:]=z['qpos'][idx];mujoco.mj_kinematics(model,data)
            xy=((data.geom_xpos[ids]-data.site_xpos[site])@data.site_xmat[site].reshape(3,3))[:,:2]
            rows.append([float(z['t'][idx]),1000*float(np.linalg.norm(xy[1]-xy[0])),np.round(1000*np.linalg.norm(xy,axis=1),2).tolist()])
    return rows

def main():
    a=e.read(d.HERE/'result.json');p=e.read(d.HERE/'prep-result.json');ext=e.read(d.HERE/'extension-result.json')
    other=e.read(d.HERE/'other-natural.json');transfer=e.read(d.HERE/'opened-transfer.json')
    standard=e.read(d.HERE/'standard-materials.json');prepared=e.read(d.HERE/'prep-materials.json')
    def line(label,row):
        t=row['gates']['flat_1m']['t']
        return f"|{label}|{row['seed']}|{t:.2f} s|{row['last_both_m']:.4f} m|{max(0,row['last_both_m']-1):.4f} m|{row['seconds']:.2f} s|{row['reason']}|"
    rows=[line(k,v) for k,v in [('标准静立，候选二',other['verified']),('标准静立，冻结',a['selected']),('静立 1.18 秒，冻结',p['verified']),('原生状态分支延伸',ext['verified'])]]
    slopes=e.read(d.HERE/'extension-history.json')
    first=e.read(d.HERE/'extension-source.json')['candidates']
    probes=['标准静立','静立 1.18 秒'];materials=[]
    for name,rr in zip(probes,(standard,prepared)):
        for mode in (False,True):
            vals=[next(v['last_both_m'] for v in rr if v['named_material']==mu and v['low_trained_pulses']==mode) for mu in ('low','nominal','high')]
            materials.append('|'+name+'|'+('冻结的反馈脉冲' if mode else '无新增脉冲')+'|'+ '|'.join(f'{x:.4f}' for x in vals)+'|')
    stats=[(sum(t['flat'] for t in transfer if t['no_added_actions']==mode),
            np.mean([t['meters'] for t in transfer if t['no_added_actions']==mode]),
            max(t['meters'] for t in transfer if t['no_added_actions']==mode)) for mode in (True,False)]
    gaps=metrics('extension-low');angles=', '.join(f"{t:.2f} 秒 {mm:.1f} 毫米" for t,mm,_ in gaps)
    extm=e.read(d.HERE/'extension-low.json')
    desc=f"""# 双球低摩擦在连续主赛道的实测训练

固定两颗球与拍面的滑动摩擦系数 μ = 0.224，保留原有扭转与滚动摩擦、球间接触和地面接触。两颗独立 16 毫米球各重 0.432 克，平拍半径 55 毫米、重量 40 克，电机扭矩限幅 0.20 N·m。赛道从实际释放点起依次为平地 1 m、1° 上坡 1 m、平台 0.5 m。主赛道从零连续仿真。规则使用 500 Hz 接触与失效审计，在通过门槛的 50 Hz 样本要求两球同时触拍，终点另需停车保持一秒。

## 开发结果

|配置|已开发起点|两球过 1 m|最后有效双触拍里程|进入坡段距离|终止时刻|终止原因|
|---|---:|---:|---:|---:|---:|---|
{chr(10).join(rows)}

这四行包含两个不同的自然起点，均来自预先筛选的 358 个已开发种子。所有里程使用实际有效双触拍位置。进入坡段后的里程按水平投影计。两个种子均达到平地 1 m，坡段 1 m 与全程 2.5 m 的成功数均为零。正式成功率应读取另行冻结的独立盲验。

## 如何找到动作

1. 对 358 个归档自然起点各运行三个控制配置，共 {a['initial_sims']:,} 次。包含归档脉冲、原步速无新增脉冲和 1.17 倍步速无新增脉冲。所有配置初筛最远 {a['best_initial']['m']:.4f} 米。保留多个真实开局，逐步尝试有限时间的步速改变、颈部角度、偏航、相机观测反馈与倾拍调整。标准释放共 {a['branches']:,} 次分支，由同样释放状态重放。最终冻结种子 {a['selected']['seed']} 的匹配基线只有 {a['same_start_base']['last_both_m']:.4f} 米，处理前后的位置状态逐字节一致至第 {a['identical_prefix_last_tick']} 个控制节拍。
2. 基于归档物理结果取其中 18 个种子，枚举 5 个空拍预备静立时长和 2 个步速，每次在预备后正常释放双球。共 {p['initial']} 次初始化、{p['branches']} 次分支。1.18 秒静立在最终选中的起点上，无新增动作时达到 {p['initial_same_start']['last_both_m']:.4f} 米。冻结策略的预备时长比原默认 1.00 秒增加 0.18 秒。原有球初始位置扰动、速度和后续扰动取样保留。
3. 取两个已越米的开局，复制失效前完整进程与物理状态，逐步前移或后移干预时刻，并试验双球分离方向、相对速度、支撑脚步相触发的脖颈与拍面调整。{len(slopes)} 轮共产生 {ext['branches']:,} 个后继，含原动作对照。每组 25 个后继的 qpos、qvel、ctrl 和加速度热启动哈希一致，组内原动作复现上级结果。每个分支继承该时点的所有延迟观测和扰动状态。最后选出的动作序列从自然释放完整复跑，确认里程一致。反馈使用原传感器和控制时钟，分支选择使用已打开回合的结果，所以动作时间有起点依赖。
4. 最远轨迹失效前 1.2 秒内，两球拍面投影间距依次为 {angles}。停机原因是 {extm['reason']}，此时最后一次刻录的两球距拍心分别为 {extm['terminal_radii_mm'][0]:.1f}、{extm['terminal_radii_mm'][1]:.1f} 毫米。全程没有机身触地，500 Hz 审计中最大单球连续脱拍间隔为 {1000*extm['contact_audit_500hz']['longest_no_face_contact_s']:.1f} 毫秒。

## 同一起点改变摩擦

各行从自然种子 15387848 同样释放并完整重放，单位为米。训练脉冲均在 μ = 0.224 下选出。横向比较反映这组策略对材料的敏感性。

|空拍预备|动作|μ = 0.224|μ = 0.320|μ = 0.416|
|---|---|---:|---:|---:|
{chr(10).join(materials)}

另用 96 个来自同一预筛档案、未进入 18 个预备训练起点的自然种子复跑。原控制到一米 {stats[0][0]}/96，平均 {stats[0][1]:.4f} m，最远 {stats[0][2]:.4f} m。冻结 1.18 秒预备策略到一米 {stats[1][0]}/96，平均 {stats[1][1]:.4f} m，最远 {stats[1][2]:.4f} m。当前可复用的是已打开起点的物理前缀、诊断和搜索方法，本轮行走目标为跨起点 90% 成功，目前仍未达到。

## 回放和复做

- [原始静立时间的 1.2349 m 原速回放](standard-primary.mp4)
- [静立 1.18 秒后的 1.2035 m 原速回放](prepared-primary.mp4)
- [原生物理分支延伸回放](extension-primary.mp4)
- [358 个起点与冻结实验规则](protocol.json)，[标准释放全程验证](result.json)，[第二个自然起点的越米核验](other-natural.json)，[预备动作验证](prep-result.json)，[原生分支的起点、时刻与哈希](extension-history.json)，[延伸结果](extension-result.json)，[96 个开局的逐条迁移记录](opened-transfer.json)。

在本目录以实验已有的 Python 环境依次执行以下命令。

```sh
../../pingpong-turn-pit-20261128/run-local develop.py
../../pingpong-turn-pit-20261128/run-local preparation.py
../../pingpong-turn-pit-20261128/run-local extend.py --frozen-sources
../../pingpong-turn-pit-20261128/run-local transfer_cells.py best.json prep-result.json --out material-comparison.json
../../pingpong-turn-pit-20261128/run-local opened_transfer.py
LP_NUM_THREADS=1 ../../pingpong-turn-pit-20261128/run-local render_proof.py extension-low.npz extension-primary.mp4
```

本次原生分支的起始快照保存于 `extension-source.json`。使用冻结来源精确复现当时两个起点的动作。分支结束后主流程又改善了标准释放的候选，因此不能简单拿最后的 `best.json` 替代原生分支的原始起点。底层轨迹的 `material: original` 是沿用的非滑动材料配置标签。两组实际球–拍显式接触的滑动数值和继承的其他摩擦分量可查 `standard-materials.json` 与 `prep-materials.json` 中的 `pairs` 字段。
"""
    f=d.HERE/('低摩擦连续主赛道实训_'+datetime.now(ZoneInfo('Asia/Singapore')).strftime('%Y%m%d_%H%M%S')+'.md')
    f.write_text(desc)
    print(f)
if __name__=='__main__':main()
