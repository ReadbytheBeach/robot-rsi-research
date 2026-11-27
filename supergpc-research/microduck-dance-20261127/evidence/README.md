# 逐回合数据与判读方法

[trials.csv](trials.csv) 收录 472 个已执行的仿真回合。每行对应一个模型、一种引擎和一个随机种子。相同种子在不同引擎、不同策略间配对。每行的模型 SHA-256 可以辨认不同阶段中重复使用的同一组参数，轨迹 SHA-256 在打包时与原始 NPZ 文件逐一核对。逐子步 NPZ 留在原始实验中。

| 数据批次 | 种子 | 回合数 | 目的 |
|---|---|---:|---|
| first | 892700–892711 | 120 | 五个冻结策略，各用两种引擎和 12 个条件验收 |
| landing | 892800–892811 | 48 | 落脚反馈策略 land075 与三拍父策略配对 |
| old_paired | 892800–892811 | 12 | 另用相同的 MuJoCo 条件重跑 11 月 26 日的 dance-full，比较实际抖动、漂移与姿态 |
| headref | 892820–892831 | 48 | 官方头壳投影纠偏与三拍父策略配对 |
| coordinated | 892850–892861 | 48 | 40% 头颈纠偏叠加在 land075 上，与 land075 配对 |
| head_amplitude | 892900–892903 | 16 | 四个头颈目标偏移统一缩放至 65%，与三拍父策略配对 |
| consistency | 893200–893259 | 180 | 已冻结的三个策略在 60 个新条件下另做 MuJoCo 复验 |

## 如何计算成功率

先按策略和引擎筛选。要复算 land075 的 **24 个双引擎配对条件**，选中 `landing` 和 `coordinated` 两个批次中 `policy=land075` 的行。这个 ONNX 在前一批是新策略，在后一批是对照策略。再分别对两种引擎计算 `completion`、`feasible`、`three_feasible` 的和。

| land075 | 回合 | 跳完整段 | 整段物理可行 | 物理可行且三拍有效 | 第 155 帧右脚受控 |
|---|---:|---:|---:|---:|---:|
| 两批独立 MuJoCo | 24 | 24 | 24 | 24 | 24 |
| 相同条件的原生 PhysX | 24 | 11 | 3 | 0 | 24 |
| 追加独立 MuJoCo | 60 | 60 | 60 | 60 | 60 |

在规定扰动分布下，将这另外 60 次看作独立抽样，60/60 的成功率单侧 95% 精确下界为 95.13%。种子改变摩擦、驱动增益和起始偏航；每一回合模仿的都是相同的 281 帧人体舞段。头壳投影误差分别保留全批次和父子共同完赛子集的口径。[分组汇总与视觉、头幅消融](results.json)

以下命令只需要 Python 标准库，可在本目录执行。

```python
import csv

with open("trials.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

for engine in ("mujoco", "physx"):
    trials = [r for r in rows if r["suite"] in {"landing", "coordinated"}
              and r["policy"] == "land075" and r["engine"] == engine]
    print(engine, len(trials), {
        key: sum(int(r[key]) for r in trials)
        for key in ("completion", "feasible", "three_feasible", "right155")
    })
```

## 怎样读时间和物理量

- `completion` 表示跑到原片最后一帧。`feasible` 要求跳完整段并满足关节行程、速度、全身倾角、漂移、接触和质心等约束。`three_feasible` 还要求在人体三个相应时间窗完成左、右、左有效换重。
- `right155` 单独检查官方右拍的一个时刻。原片第 155 帧在 5.167 秒，本地有两帧缓冲，最近的 50 Hz 控制采样为 5.24 秒。`beat1_controlled_s` 至 `beat3_controlled_s` 是各拍内对侧脚触地、摆动足达到高度且质心符合支撑要求时的最长连续时长。每拍至少需 0.06 秒，且人体峰时前后 0.25 秒内须观察到有效换重。两种更严的同段计算所得完整三拍通过数见汇总。
- `drift_cm` 是相对起点的最大水平偏移。`tilt_max_deg` 是机身最大倾角。`com_outside_p95_mm` 是有接触时，质心投影越出当时支撑多边形的距离第 95 百分位。`contact_outside_25mm_fraction` 是有接触时该距离超过 25 mm 的样本比例。
- `speed_200hz` 是物理子步最高实测关节角速度，单位 rad/s。`command_slew` 是 50 Hz 指令变化速率峰值。`angle_margin_deg` 和 `command_margin_deg` 是相对关节额定行程的最小实测、指令余量。`jitter_rms_deg` 是相对低通曲线的位置高频波动，`acceleration_rms_rad_s2` 是关节角加速度均方根。提前终止的回合只在已观测样本上计算这些连续运动统计量。
- `pose_curve_score` 比较双膝与头身相对转向。`amplitude`、`smooth_score`、`consistency` 和 `utility` 是原实验的分项/综合评分，单位为分。成功率按回合的二元物理与三拍门槛统计。

[protocol.json](protocol.json) 保存运动来源指纹、种子区间、物理门槛、11 个落脚参数、5,934 个主搜索回合的分支计数、同状态重播和反馈消融结果。2.24 和 3.28 秒均为本地仿真时间。训练时的失败分支与消融使用单独的种子，独立验收分母只包含上表标出的回合。

[landing.py](landing.py) 是训练时使用的落脚窗口、反馈计算及 ONNX 导出源码。它依赖实验工作区的 `adapter`、`run`、相位表、三拍与稳姿两个专家模型，以及 NumPy 和 ONNX。阅读或核验该局部控制律可直接使用此文件；单独运行训练需要原实验依赖。归档中的[冻结 ONNX](../models/landing.onnx)已将两条专家路径与落脚控制合入一张图。
