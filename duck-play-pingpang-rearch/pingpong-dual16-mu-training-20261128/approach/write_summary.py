"""Create the branch report after both entry searches have finished."""
from datetime import datetime
from zoneinfo import ZoneInfo
from summarize import main as verify_all
from search import HERE,read

def main():
    verify_all()
    data=read(HERE/'audit.json')
    s=data['slope-entry']; raw=data['slope-entry-tilt'];r=data['record'];h=data['high-catch']
    fresh=read(HERE/'high-catch/fresh.json')
    worldtoe=1.02
    init=read(HERE/'record/trajectory.json')['initial_x_m']
    first=read(HERE/'first-high-metre/frozen.json')['result']
    gate=first['gates']['flat_1m']
    group=['record','record-continuation','orientation','high','high-continuation','high-catch','slope-entry','slope-entry-tilt','primary']
    label={'record':'纪录材料，分阶段搜索','record-continuation':'纪录材料，步速与相位','orientation':'纪录材料，两球调换前后顺序','high':'最高摩擦，分阶段搜索','high-continuation':'最高摩擦，步速与相位','high-catch':'最高摩擦，越缘前二维纠偏','slope-entry':'最高摩擦，支撑相位与入坡','slope-entry-tilt':'最高摩擦，保留较大机身倾角的入坡分支','primary':'最高摩擦，主赛道开发起点'}
    table=[]
    for name in group:
        a=data[name]; d=a['last_dual']
        table.append(f'| {label[name]} | {a["trials"]} | {d["m"]:.4f} | {d["slope_m"]:.4f} | {a["both_centered"]["m"]:.4f} | {a["tilt_peak_deg"]:.2f}° |')
    rows='\n'.join(table)
    allrows=read(HERE/'material-transfer.json')['rows']
    material='\n'.join('| '+str(name)+' | '+' | '.join(f'{row["last_both_m"]:.3f}' for row in allrows if row['name']==key)+' |' for name,key in [('原纪录动作','old_teacher'),('纪录材料优化后','record_trained'),('最高摩擦优化后','high_trained')])
    text=f"""# 双球入坡的动作分支与滑动摩擦复验

全部回合使用 40 克平拍、两颗 16 毫米球、0.20 N·m 原扭矩限幅和既有扰动、时延、计分规则。固定网格开发起点为 12600381。坡脚固定在世界 x={worldtoe:.3f} 米，从该次释放点到坡脚为 {worldtoe-init:.5f} 米。另在坡脚严格距实际释放点 1 米的主赛道上，从 114 个历史开发起点筛选后另行训练。

## 从释放重跑的结果

最高摩擦 μ=0.416 时，原纪录控制只能走 0.22006 米。先在时间更早、物理状态完全相同的分支训练，再增加短时加速、颈部与二维倾拍纠偏。首次确认在 {gate["t"]:.2f} 秒双球同时触拍并越过一米，球心到拍心为 {gate["radii_mm"][0]:.2f} 和 {gate["radii_mm"][1]:.2f} 毫米。队列中的不同前缀在 0.70、0.76、0.82、0.87 米附近尝试根据左右脚支撑差交替调整步速、颈部与倾拍，同时保留预计拍缘余量较大、径向分离较慢和末次触拍里程较远的不同轨迹。控制使用已经送达的读数。状态分支共享实际接触状态、暖启动、执行队列及随机序列，选中后均从首次释放重新运行。

| 开发分支 | 候选物理分支数 | 最后同时触拍里程 m | 其中实际坡上 m | 两球心均在拍面内时的最后里程 m | 峰值机身倾角 |
|---|---:|---:|---:|---:|---:|
{rows}

常规开发搜索优先保留峰值倾角小于 29° 的分支。另从通过原始判据且机身倾角较大的候选中，复现之前最长的动作，再独立进行支撑相位入坡搜索。两种筛选均保留原始姿态、扭矩和接触判负器。高摩擦的最好动作在末次双球接触时距真实坡脚还有 2.74 毫米，下一帧已触发 B 球出缘。纪录材料实际进入 1° 坡 0.427 米，坡顶位于坡脚之后一米。上表最后四列来自完整轨迹的 50 Hz 实际接触与有效里程，终止帧本身不计为最后有效双球里程。[状态和逐门槛审计](audit.json) · [首次最高摩擦过米原速录像](first-high-metre/original-speed.mp4) · [8.94 秒过线帧](first-high-metre/gate-8p94.png) · [纪录材料入坡录像](record/original-speed.mp4)

## 动作与材料互换

固定同一开发起点和这两套已训练控制，逐一替换球与拍面的滑动摩擦，读取最后双球同时触拍的里程。滚动、扭转以及球与球的原参数都保持原值。此处最高摩擦优化后指已完成平地一米的二维补偿动作。

| 控制 | 0.224 | 0.272 | 0.320 | 0.364467 | 0.392 | 0.416 |
|---|---:|---:|---:|---:|---:|---:|
{material}

[六种摩擦逐次物理结果](material-transfer.json)

## 新起点与失败回放

固定最高摩擦越缘前二维纠偏动作，在主赛道 128 个新起点上，一米为 {fresh["combined"]["trained"]["flat"]}/128，全程为 {fresh["combined"]["trained"]["finished"]}/128，平均有效推进 {100*fresh["combined"]["trained"]["mean_m"]:.2f} 厘米；固定网格上相应通过数为 {fresh["fixed"]["trained"]["flat"]}/128 和 {fresh["fixed"]["trained"]["finished"]}/128。后续两套入坡动作与此控制首次出现差异分别在 8.76 秒和 7.56 秒，以上全部 256 次对应释放最晚在 5.28 秒已结束，逐步动作序列在所有终止前完全相同，因而过线计数相同。纪录材料训练方案在这批起点的主赛道和固定网格同样均未过一米。[动作前缀比对](slope-entry-fresh-prefix-proof.json)[最高摩擦逐回合](high-catch/fresh.csv) · [纪录材料逐回合](record/fresh.csv) · [主赛道开发控制复验](primary/fresh.json)

纪录材料最远轨迹在 11.6 秒时双球间距约 35.8 毫米；11.7 秒时增至 41.0 毫米，12.0 秒达到 62.8 毫米。进一步选择物理上确曾在 8 秒前后调换两球前后次序的分支训练，末次双球里程 0.970 米，仍在下一次大幅分离之前失球。不同轨迹对相同动作的反应表明，单一已公开起点的持续提升无法代表整组新起点的结果。[不同前缀与未达到坡脚的分支](orientation/history.json)

## 本地复跑

在本目录使用原有环境。以下命令重现开发搜索、独立验证与材料互换。

```bash
../../pingpong-turn-pit-20261128/run-local search.py high
../../pingpong-turn-pit-20261128/run-local search.py record
../../pingpong-turn-pit-20261128/run-local primary.py
../../pingpong-turn-pit-20261128/run-local extend.py high
../../pingpong-turn-pit-20261128/run-local extend.py record
../../pingpong-turn-pit-20261128/run-local catch.py
../../pingpong-turn-pit-20261128/run-local slope_entry.py
../../pingpong-turn-pit-20261128/run-local tilt_companion.py
../../pingpong-turn-pit-20261128/run-local orientation.py
../../pingpong-turn-pit-20261128/run-local verify.py high-catch
../../pingpong-turn-pit-20261128/run-local cross_material.py
```
"""
    primary=HERE/'primary-final/result.json'
    pace=HERE/'primary-final/fine-pace/result.json'
    if primary.exists() and pace.exists():
        final=read(primary);g=read(pace)
        body=['', '## 正式赛道上补做的最高摩擦对照', '',
            f'使用前面已打开的三个起点，在正式赛道上试了 {final["pilots"]} 种起步组合、{final["branches"]} 个同状态动作分支，并在步速倍率 0.96–1.04 之间隔 0.001 比较 {g["n"]} 次步速微调。以下均为开发成绩。', '',
            '| 起点 | 动作分支最远 m | 步速微调最远 m |', '|---|---:|---:|']
        for a,b in zip(final['best_by_seed'],g['top']):
            assert a['seed']==b['seed']
            body.append(f'| {a["seed"]} | {a["m"]:.5f} | {b["m"]:.5f} |')
        winners=[(final,primary.parent),(g,pace.parent)]
        chosen,path=max(winners,key=lambda q:q[0]['result']['last_both_m'])
        frac=chosen['result']['last_both_m']; verified=chosen['result']
        body.extend(['',f'最高摩擦最终能在这个正式地面上确认的最远双球触拍为 {frac:.5f} 米。坡上有效距离 {max(0.,min(frac-1.,1.)):.5f} 米。回合以 {verified["reason"]} 结束。'])
        evidence=path/'fresh.json'
        if evidence.exists():
            v=read(evidence);body.append(f'冻结后复验 {v["n"]} 个新起点，平地一米 {v["flat"]}/{v["n"]}，坡上一米 {v["slope"]}/{v["n"]}，2.5 米停车 {v["finish"]}/{v["n"]}。')
        body.extend(['','[动作与逐起点结果](primary-final/result.json) · [步速细扫结果](primary-final/fine-pace/result.json) · [分支状态校验](primary-final/history.json)'])
        text+='\n'.join(body)+'\n'
    stamp=datetime.now(ZoneInfo('Asia/Singapore')).strftime('%Y%m%d_%H%M%S')
    existing=sorted(HERE.glob('双球入坡动作分支与摩擦复验_*.md'))
    target=existing[0] if existing else HERE/f'双球入坡动作分支与摩擦复验_{stamp}.md'
    target.write_text(text)
    print(target)
if __name__=='__main__':main()
