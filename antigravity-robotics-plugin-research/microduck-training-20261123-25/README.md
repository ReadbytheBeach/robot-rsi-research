---
document_id: "RSI-020"
title_zh: "MicroDuck 六次仿真训练：从单脚承重到双螺帽归拢投篮"
title_en: "Six MicroDuck Simulation Experiments: From Single-Leg Support to Gathering and Delivering Two Nuts"
language: "zh-CN"
kind: "experiment_report"
evidence_as_of: "2026-11-25"
indexed_on: "2026-11-26"
---

# MicroDuck 六次仿真训练：从单脚承重到双螺帽归拢投篮

<!-- BEGIN GENERATED READING SUMMARY -->
## 阅读摘要 · Reading Summary

**核心问题：** MicroDuck 如何从舞步换重与单件搬运，发展到先用脚归拢两颗相距 200 mm 的螺帽，再用喙一次拾取并完成投篮？

- [LOCAL_RESULT] [AS_OF:2026-11-25] 地面短瓜段三障碍投筐在 MuJoCo 的留出测试为 309/320；同起点的原生 PhysX 为 0/320，已建立的双侧接触未产生所需净抬升。
- [LOCAL_RESULT] [AS_OF:2026-11-25] 两颗 M8 初始相距 200 mm 的一次双夹单趟搬运在 MuJoCo 完成 239/240。成功回合都用足缘归拢；唯一失败例最终同篮，但运输时碰撞体穿入超限。

**适用边界：** 六次本地仿真按任务分别计分。舞段的单拍与全身判据分列；200 mm 整屋任务使用已知地图、仿真状态和物性代理，结果仅覆盖 MuJoCo。

**相关文档：** [RSI-002 Antigravity Robotics Plugin 与机器人仿真自我改进中文调研](../antigravity-robotics-plugin-research.zh-CN.md)；[RSI-010 MicroDuck 在电子维修店交错通道中的训练与双引擎盲测](../../ropedia-xperience-2/MicroDuck%E5%95%86%E9%93%BA%E4%BA%A4%E9%94%99%E9%80%9A%E9%81%93%E8%AE%AD%E7%BB%83%E4%B8%8E%E5%8F%8C%E5%BC%95%E6%93%8E%E7%9B%B2%E6%B5%8B%E6%80%BB%E7%BB%93_20261119_093806.md)；[RSI-012 NVIDIA SimReady Central 与机器人 RSI 仿真资产中文调研](../../simready-central-research/simready-central-research.zh-CN.md)；[RSI-013 NVIDIA SOMA Retargeter：人体动作到 MicroDuck 策略的技术调研](../../soma-retargeter-research/soma-retargeter-research.zh-CN.md)

[返回总目录 · Research Index](../../README.md)
<!-- END GENERATED READING SUMMARY -->

实验时间为 2026 年 11 月 23–25 日。六组材料按当时提出的训练目标排列。每章给出训练条件、验收口径、机器可读证据和代表回放，便于从一次失败追到下一版动作。舞步、单件投筐、双件分趟和双件单趟分别计分。

| 训练目标 | 怎样判断改进 | 回放 |
|---|---|---|
| [1 · 舞段幅度粗调和反馈精调](01-soma-amplitude/README.md) | 在附加延迟下，候选从 0/6 提升到 6/6 完整跳完两遍。左脚独立承重 200 ms 的严格要求仍未达成。 | [原速，两周期](01-soma-amplitude/replay.mp4) |
| [2 · 右拍换重与落地恢复](02-soma-catch/README.md) | g2r0 在 MuJoCo 通过 12/12 个留出右拍，在 PhysX 通过 9/12。把双侧动作和全身条件一起考仍是 0/6。 | [原速，四工况](02-soma-catch/replay.mp4) |
| [3 · 从地面拾取短瓜段、绕障投筐](03-cucumber-delivery/README.md) | 同样的 320 个起点，MuJoCo 完成 309 个，原生 PhysX 完成 0 个。PhysX 能建立双侧接触，但瓜段没有达到净抬升要求。 | [原速，全程](03-cucumber-delivery/replay.mp4) |
| [4 · 两颗 M8 分两趟送入同一篮](04-m8-shuttle/README.md) | 扫描通道、近站 ±1 mm 摆位的冻结批为 324/324。另取 24 个相同起点做引擎对照，MuJoCo 24/24，原生 PhysX 0/24。 | [4 倍速，全程](04-m8-shuttle/replay.mp4) |
| [5 · 喙宽内两颗 M8 一次双夹、单趟投篮](05-m8-near-pair/README.md) | 第一版 237/240，其中一组为 37/40。第二版用全新起点得到 235/240，六组均达 38/40。 | [2 倍速，全程](05-m8-near-pair/replay.mp4) |
| [6 · 两颗起距 200 mm，先归拢再一次双夹](06-m8-200mm/README.md) | 三条路线、两档延迟共 239/240，六组均达标。所有成功回合都用足缘在地面归拢。 | [原速，全程](06-m8-200mm/replay.mp4) |

## 从最后一项看失败回放的作用

鸭子已有同时夹持近距两件的能力，但原喙覆盖不到相距 200 mm 的两颗螺帽。早期足推动作一度把两颗推到可夹范围，收脚时却让其中一颗弹起。训练随后加入“撤脚后两颗仍静稳”这一步，并从相同姿态比较带载转向。完整测试里，239 个成功回合均只闭喙一次，先把两件共同夹稳，再越过起点出口。唯一未通过的回合完成了同篮投放，但运输中的两件碰撞体穿入超过预先规定的上限。[全身质心与零件高度](06-m8-200mm/center-of-mass.png) · [失败的接触深度曲线](06-m8-200mm/failed-contact.png)

舞段阶段优化了动作幅度与反馈，运输阶段沿用原有步态、地面拾取和站稳网络，再针对任务搜索参数与动作分支。螺帽试验借鉴了 Antigravity 的同起点配对、失败分支和独立评价方法。相应成功率依赖各章记录的地图、物性和可观测状态；200 mm 任务还依赖模型预演，近站规划中位数为 76.3 CPU 秒。六次训练均为仿真实验。

本归档可直接阅读结果、下载视频和复算逐例表。复跑动力学所需的机器人模型、上游 ONNX 和仿真环境列于各章。所有视频保留仿真时钟，播放倍率见表。
