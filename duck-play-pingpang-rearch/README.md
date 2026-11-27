---
document_id: "RSI-022"
title_zh: "MicroDuck 嘴持球拍稳球仿真实验"
title_en: "MicroDuck Ping-Pong Ball Balancing with a Beak-Mounted Paddle"
language: "zh-CN"
kind: "experiment_report"
evidence_as_of: "2026-11-27"
indexed_on: "2026-11-27"
---

# MicroDuck 嘴持球拍稳球仿真实验

<!-- BEGIN GENERATED READING SUMMARY -->
## 阅读摘要 · Reading Summary

**核心问题：** MicroDuck 能否通过头部俯仰与横滚控制鸭嘴上的球拍，在扰动下稳住乒乓球？PPO 对双轴 PD 有多少帮助？

- [FACT] [AS_OF:2026-11-27] NVIDIA SimReady Central 索引包含乒乓球和球拍道具，Pollen Robotics 的 MicroDuck MJCF 提供 mouth_tip 安装点。
- [LOCAL_RESULT] [AS_OF:2026-11-27] 同一组 100 个固定躯干仿真回合中，固定拍面、PD、PD + PPO 的 10 秒稳球结果分别为 0/100、99/100、100/100。PPO 将 PD 的球心径向误差 P95 从 20.05 mm 降至 12.22 mm。

**适用边界：** 固定躯干、刚性鸭嘴安装、参数化道具与带合成噪声和延迟的仿真状态。真机夹持、相机闭环及无支架站立仍需验证。

**相关文档：** [RSI-012 NVIDIA SimReady Central 与机器人 RSI 仿真资产中文调研](../simready-central-research/simready-central-research.zh-CN.md)；[RSI-018 如何让一次实验的结果能成为下一次实验的输入](../%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5/%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5.zh-CN.md)；[RSI-020 MicroDuck 六次仿真训练：从单脚承重到双螺帽归拢投篮](../antigravity-robotics-plugin-research/microduck-training-20261123-25/README.md)

[返回总目录 · Research Index](../README.md)
<!-- END GENERATED READING SUMMARY -->

MicroDuck 用鸭嘴固定轻型球拍，通过头部俯仰和侧倾，把滚动的乒乓球拉回拍心。这个 MuJoCo 原型使用 Pollen Robotics 的 MicroDuck 模型，可在 CPU 上运行固定躯干的稳球实验、训练 PPO 并导出演示视频。

- [10 秒 PD + PPO 仿真回放](media/microduck-pingpong-ppo.mp4)
- [PPO 权重](models/microduck_ppo.zip)
- [MuJoCo 环境与道具](microduck_env.py) · [训练脚本](train.py) · [回放脚本](demo.py)

## 资产和训练设计

工作区的 RSI‑012 调研介绍了如何用 SimReady Central 发现资产并复核物理参数。沿其索引找到 NVIDIA 数据集的四个相关资产，球为 `misc_toy_pongPaddle_ball_a01`、`a02`，拍为 `misc_toy_pongPaddle_bat_a01`、`a02`，数据修订为 `653d91e182011f357cf1644013cc94ddf194d349`。后续做 Isaac Sim 视觉训练时可参考这些资产的外观，导入后仍需核对尺寸、质量、惯量和碰撞形状。 [RSI‑012 调研](../simready-central-research/simready-central-research.zh-CN.md) [NVIDIA 资产索引](https://github.com/NVIDIA-Omniverse/simready-central/blob/main/submissions/nvidia/simready-assets)

本原型采用程序生成的道具，便于复现实验和独立校准碰撞。橙色球直径 40 mm、质量 2.7 g，惯量按薄球壳计算。训练拍为直径 110 mm、厚 4 mm 的圆面，拍柄与拍面共用 18 g 的刚体。拍柄接到头部刚体 `jaw_soft` 的鸭嘴尖端附近，站立时拍面水平。球拍参数和接触摩擦是原型设定，实物数值需测量。 [ITTF 规则](https://db.ittf.com/sites/default/files/public/2026-02/2026_Statutes_v1_consolidated_clean.pdf)

[AUTHOR_REPORT] SO‑101 项目公开了 MuJoCo、PPO 和相机检测代码。作者报告随机化仿真中 97.5% 的回合稳球 10 秒，加入完整相机链路后的仿真为 113/120。MicroDuck 使用自己的结构、载荷配置、评估种子和扰动。 [SO‑101 稳球项目](https://github.com/zecice/so101-pingpong-balance)

- 物理仿真 500 Hz，控制 50 Hz。PD 根据球在拍面坐标里的二维位置和速度生成倾角。PPO 学习 `head_pitch` 与 `head_roll` 的两个角度修正量。
- 每回合随机化球的起始偏移和速度、推球扰动、拍面摩擦、舵机参数、控制和观测延迟以及测量噪声。`--difficulty` 从 0 到 1 调节扰动强度。
- 球持续 10 秒、未越过允许边界或长时间离拍，即算成功。训练脚本在同一组评估种子上对比 PD 与 PD + PPO，并报告成功率、球心径向误差和稳球时长。

## 仿真结果

[LOCAL_RESULT] 使用 MuJoCo 3.17.0、Stable‑Baselines3 2.9.2 和 CPU，PPO 训练 120,832 步。三种控制使用相同的 100 个留出回合（种子 30021–30120，难度 1）。每回合有球初始位置和速度扰动、两次推球，以及舵机增益、摩擦、观测噪声和 0–40 ms 的观测及控制延迟随机化。

| 控制 | 稳球 10 秒 | 球心偏移中位数 | 球心偏移 P95 | 稳球时长中位数 |
| --- | ---: | ---: | ---: | ---: |
| 固定拍面 | 0/100 | 31.64 mm | 54.68 mm | 1.12 s |
| PD | 99/100 | 1.68 mm | 20.05 mm | 10.00 s |
| PD + PPO | 100/100 | 0.81 mm | 12.22 mm | 10.00 s |

球心偏移为球心投影到拍面后距拍心的距离，按实际运行的控制步汇总。PD + PPO 把这一组评估的 P95 球心偏移缩小约 39%。仿真将球拍刚接在头部，躯干固定，观测取自物理状态并叠加合成噪声与延迟。真机夹持、站立、舵机和视觉闭环需要单独验证。

## 安装与运行

在本项目目录里运行。需准备 Git 和 Python 3.12（本次验证版本）。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

git init upstream
git -C upstream fetch --depth=1 https://github.com/pollen-robotics/microduck_rl.git \
  0daab160d3fb1c2cbaba16a4a19052f36709dd9e
git -C upstream checkout --detach FETCH_HEAD
```

用同一个种子复现三种控制。

```bash
python demo.py --upstream upstream --difficulty 1 --seed 30021 --controller flat
python demo.py --upstream upstream --difficulty 1 --seed 30021 --controller pd
python demo.py --upstream upstream --difficulty 1 --seed 30021 \
  --controller ppo --model models/microduck_ppo.zip
```

重新训练并评估 100 个留出回合。

```bash
python train.py --upstream upstream --steps 120000 --envs 4 \
  --difficulty 1 --seed 17 --eval-episodes 100 --eval-seed 30021 \
  --model .venv/microduck_ppo_retrained.zip
```

在支持 EGL 的 Linux 环境生成 MP4。去掉 `--video` 可仅运行仿真和打印结果。

```bash
MUJOCO_GL=egl python demo.py --upstream upstream --difficulty 1 --seed 30021 \
  --controller pd --video demo-pd.mp4

MUJOCO_GL=egl python demo.py --upstream upstream --difficulty 1 --seed 30021 \
  --controller ppo --model models/microduck_ppo.zip --video demo.mp4
```

## 从仿真到真机

[PROPOSAL] 依次测试夹具、视觉闭环和无支架站立，每次保留上一步的对照。

1. **先测头部与夹具。** 用轻质短柄和防滑夹持面，测量夹持稳定性、拍面静态偏差、载荷对头部响应的影响。仿真用刚性安装和固定躯干，真机需分别验证夹持和双脚站立。
2. **加入真实视觉。** 先用斜上方相机同时拍到橙球与拍面上的定位标记，用相机内参和拍面位姿求球心射线与拍面上方一个球半径的平面交点，滤波估计拍面坐标中的滚动速度。观测丢失时让头部平缓回到中位。上机前把实测延迟、检测抖动和头部响应加入仿真。原始 MJCF 相机有方向偏差，官方仿真运行时已修正。 [官方相机修正](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/src/mjlab_microduck/sim/camera.py#L74-L95)
3. **沿用站立控制。** 外部稳球控制器通过 `robot.head` 发送相对站姿的俯仰和侧倾目标，原厂站立策略维持全身姿态。`robot.mouth` 负责夹持。原型的 SB3 检查点使用独立的稳球观测和动作接口，接入原厂 61 输入、14 输出的策略加载器需要适配。 [MicroDuck 控制协议](https://github.com/pollen-robotics/microduck/blob/main/duck-ipc-proto/src/lib.rs) [官方训练与导出接口](https://github.com/pollen-robotics/microduck_rl)

## 模型来源与许可

演示渲染使用 © Pollen Robotics 的 MicroDuck STL 网格，源自上游固定版本。仿真脚本加载官方 MJCF 后固定躯干，调整碰撞与关节控制，加入球和球拍。上游 MJCF 采用 Apache‑2.0，原始 STL 网格和改编演示按 CC BY‑NC‑SA 4.0 共享。 [上游代码许可](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/LICENSE) [上游网格许可](https://github.com/pollen-robotics/microduck_rl/blob/0daab160d3fb1c2cbaba16a4a19052f36709dd9e/LICENSE-MODELS.md) [CC BY‑NC‑SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
