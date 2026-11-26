# 两颗 M8 螺帽分两趟穿房入篮

MicroDuck 在近站从地面叼起 A，绕开障碍、携 A 穿过六个路标，把 A 放进面包篮。它空嘴返回取 B，再沿通道送 B 入同一个篮，并后退站稳。MuJoCo 冻结盲验 **324/324**，Wilson 95% 区间为 **98.83%–100%**。三条路线 S0、S1、S2 各有两档延迟（0 和 20 ms），六组各 **54/54**。每个试次仅计一个从地面开始的完整回合。[正式验收](verdict.json) · [324 次逐例计分](episodes.csv)

[观看完整回合（4 倍速）](replay.mp4)。画面来自预登记的首例 17743000（S0、0 ms）。实际仿真时长 155.40 秒。可先看 A 入篮后的空载返程，再看 B 入同一篮，最后双件共同承托 5.0075 秒。视频上部保留仿真时钟，底部蓝条标出本归档的播放倍率。

## 控制和判定

每颗螺帽 0.993 g，使用独立自由关节。每件平放在各自的预设取件位，每轴独立扰动 ±1 mm，偏航 ±30°。三个现有 v7 身体策略负责地面拾取、步行和站稳。Python 调度下颌、路线和篮前投放，借助仿真状态预演候选动作。每次拾取要同时测到上下喙垫接触，整件离地至少 20 mm 且连续受夹 2 秒。两件依次投放后都须在篮内共同受托至少 2 秒。324 个成功回合合计 648 次合格拾取、648 次带载穿房，完成时间中位 140.82 秒。[冻结拾取参数](pickup-params.json) · [控制配置](settings.json)

较早快行版为 256/324，67 个回合携运中掉件。对准、步态和投放均经调整后才得到本批 324/324。另取相同的 24 个开发起点只改最终版步速，快慢两组均完成 24/24，因此主版本的增益无法单独归于减速。

## 跨引擎和视觉范围

| 测试条件 | 完整任务成绩 | 测了什么 |
|---|---:|---|
| 冻结控制器，24 对相同摆位 | MuJoCo 24/24，原生 CPU PhysX 0/24 | 对同一初态和控制器更换引擎。两种引擎的主结果分开统计。 |
| PhysX 单独调参、调整篮底接触模型后，另取 12 例 | 3/12 | 若同时要求抬升后的下垫侵入满足额外品质门槛，则为 0/12。 |
| MuJoCo 返程使用头部单目定位 B，另取 60 例 | 49/60 | 其余部分仍依赖已知地图和机身定位。六例返程对准超时，五例非足部触地。 |

主批使用扫描投影生成的碰撞通道和按公开尺寸重建的物体。该结果适用于已知地图下的 MuJoCo 状态反馈控制。真实三维扫描、原版 SimReady USD 完整碰撞层和真机交付仍待验证。[跨引擎 24 对逐例记录](engine-comparison.json) · [单目 B 组冻结成绩](vision-b-verdict.json)

## 在原实验工作区复演

此目录提供视频、筛选后的逐例记录、冻结配置和成绩。执行回合需原 MicroDuck 实验工作区、已安装的 MuJoCo/ONNX Runtime 环境、三个 v7 ONNX 与机器人几何包。从该工作区根目录进入实验目录，用已激活的实验 Python 环境运行。以下会创建新输出目录。

```bash
cd experiments/m8-nut-room-delivery
REG=validation/scan-paced-17743000
SRC="$REG/source/experiments/m8-nut-room-delivery"
OUT=$(mktemp -d)
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python "$SRC/course.py" --pick "$SRC/parameters.json" --settings "$SRC/settings.json" \
  --start 17743000 --case-layout S0 --case-delay-ms 0 --count 1 --trace --out "$OUT/first"
python "$SRC/audit_delivery.py" "$OUT/first/results.json"
```

同一目录下的 `双螺帽验收结果.md`、`validation/scan-paced-17743000/registration.json` 和 `transfer/scan-paced-native24/paired-results.json` 分别保存完整实验报告、冻结登记和双引擎配对记录。
