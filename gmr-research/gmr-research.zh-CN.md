---
document_id: "RSI-005"
title_zh: "GMR 人体动作重定向与 MicroDuck 参考轨迹验收：中文技术调研"
title_en: "GMR Human Motion Retargeting and MicroDuck Reference Trajectory Validation"
language: "zh-CN"
kind: "research_report"
evidence_as_of: "2026-11-20"
indexed_on: "2026-11-23"
---

# GMR 人体动作重定向与 MicroDuck 参考轨迹验收：中文技术调研

<!-- BEGIN GENERATED READING SUMMARY -->
## 阅读摘要 · Reading Summary

**核心问题：** 如何判断动作重定向生成的参考轨迹是否导致下游跟踪失败或动作失真？

- [AUTHOR_REPORT] [AS_OF:2026-11-20] 论文在相同 BeyondMimic 训练流程下比较 G1 的多种重定向参考，报告完成率随动作与参考方法显著变化；GMR 也存在参考异常和起始帧敏感的案例。
- [DISCUSSION] 完成整段动作、跟踪精度和参考对人体原动作的忠实度应分别判断；G1 仿真子集结果不足以推出 GMR 在 MicroDuck、真机或物体交互任务上的优劣。
- [PROPOSAL] 建议对齐人体原动作、机器人参考和实际轨迹，先检查滑移、穿地、关节尖峰与首帧过渡，再固定其他条件比较 GMR 与 SOMA。

**适用边界：** 以论文原文、项目页与官方实现为资料的调研；定量证据来自作者的 G1 仿真，本文未运行训练、仿真或实机实验。

**相关文档：** [RSI-013 NVIDIA SOMA Retargeter：人体动作到 MicroDuck 策略的技术调研](../soma-retargeter-research/soma-retargeter-research.zh-CN.md)；[RSI-003 ATLAS 与 SOMA 对 Robot RSI 的价值：中文技术调研](../atlas-research/atlas-research.zh-CN.md)

[返回总目录 · Research Index](../README.md)
<!-- END GENERATED READING SUMMARY -->

调研日期为 2026 年 11 月 20 日（新加坡时间）。研究对象为斯坦福大学论文 *Retargeting Matters: General Motion Retargeting for Humanoid Motion Tracking*（arXiv:2510.02252v1）。

**在相同的策略训练流程下，换一种人体动作重定向方法，可以让 Unitree G1 在同一段舞蹈上的跨引擎完成率从 0% 变为 100%。GMR 在另一段舞蹈上也会降到 51%。对 Robot RSI，最值得借鉴的是在调整奖励或重新训练之前，先检查交给策略模仿的参考动作。** [S1，表 I、图 3]

下文区分论文作者公布的 G1 仿真结果和面向 MicroDuck 的实验建议。本次工作限于资料调研，未运行训练、仿真或实机实验。

## 1. 项目定位与资料

João Pedro Araújo、Yanjie Ze、Pei Xu、Jiajun Wu 和 C. Karen Liu 研究了一个具体问题：同样的人体动作，如果先用不同方法转换为机器人动作，再用同一套强化学习流程训练，哪些差异会保留到最终执行？作者同时检查机器人能否完成动作、实际轨迹离参考多远，以及参考动作在视觉上是否忠实于人体原动作。[S1–S3]

论文比较了 GMR、PHC、ProtoMotions 三种公开方法，以及 Unitree 发布、由闭源方法生成的参考动作数据。GMR 项目提供重定向代码，论文中的跟踪策略由独立的 BeyondMimic 流程训练。[S1，第三节；S3]

## 2. GMR 怎样把人体动作变成机器人动作

以迈步为例：人体和机器人的腿长、躯干比例和关节活动范围不同。把整个人按身高等比缩小，摆动腿的姿态可能看起来相似，支撑脚却会在应该踩稳时滑动。GMR 用以下步骤生成可供跟踪的参考轨迹。[S1，第四节、图 2]

1. **建立对应关系。** 将人体与机器人的躯干、脚等关键部位配对，并对齐静止姿态下的坐标方向。
2. **分别处理整体位移与局部比例。** 对根部的整体位移使用统一缩放，对各关键部位相对根部的位置使用各自的缩放系数。这样可以分别适配腿与躯干的比例。
3. **分两次求解逆运动学。** 第一阶段优先匹配关键部位朝向和手脚等末端位置。第二阶段进一步匹配各关键部位的位置与朝向，两阶段都考虑关节限位。
4. **输出时间序列。** 用上一帧的解初始化下一帧，输出每帧的机器人根部位姿和关节角。下游控制器还需在重力、接触和执行器约束下跟踪这些目标。

## 3. 实验怎样区分参考质量与策略训练的影响

作者从 LAFAN1 选取 21 段动作，目标机器人固定为 Unitree G1。对每种方法生成的每段参考动作，分别在 Isaac Sim 中用同一套 BeyondMimic 流程训练一个跟踪策略。评测包括关闭域随机化的 Isaac Sim（每策略 100 次）、开启域随机化的 Isaac Sim（每策略 4,096 次），以及 MuJoCo + ROS 跨引擎测试（每策略 100 次）。[S1，第三节 C–D]

一次成功要求机器人跟踪到参考动作结束，期间躯干参考部位的高度和朝向偏差保持在终止阈值内。完成率回答“能否做完全程”，论文表 II 另报身体部位与关节跟踪误差。20 人盲评进一步比较参考动画与人体原动作的相似度。三项评测可区分动作能否完成、控制器能否跟准，以及给控制器的参考是否忠实。[S1，表 I–II、图 4]

## 4. 表 I 和表 III 的关键结果

### 4.1 同一训练流程，难点随动作改变

下表摘自表 I 的 **sim2sim** 栏。每格都是该策略在 MuJoCo + ROS 的 100 次测试中，完成整段动作的比例。[S1，表 I]

| 动作 | PHC | GMR | ProtoMotions | Unitree 闭源参考数据 |
|---|---:|---:|---:|---:|
| 普通步行 Walk 1，33 秒 | 100% | 100% | 100% | 100% |
| 舞蹈 Dance 1，118 秒 | 0% | 100% | 100% | 100% |
| 跑动与急停 Run (stop & go)，37 秒 | 74% | 100% | 26% | 100% |
| 舞蹈 Dance 5，68.4 秒 | 100% | **51%** | 100% | 100% |

Walk 1 无法区分这四组策略。对差异大的动作，作者回看参考轨迹，发现 PHC 的部分舞蹈发生严重穿地，ProtoMotions 的跑动与急停出现双腿相交，GMR 的 Dance 5 出现腰部侧倾角突然跳变。对开发者而言，记录异常发生的部位和帧号，比只记录“训练失败”更有诊断价值。[S1，第五节 B、图 3；S2]

### 4.2 同一策略，只改起始帧

表 I 中 Walk 2 的跨引擎结果带有星号。表 III 说明，同一个 GMR 步行策略从参考序列第 0 帧开始时，完成率为 **64%**；改从第 7 帧开始，完成率为 **100%**。这项比较没有重新训练策略。它提示应当单独验证默认站姿到首帧的过渡，并把实际采用的起始帧连同成绩一起记录。[S1，表 I 注释、表 III]

## 5. 与 SOMA、ATLAS 的关系及证据边界

GMR 与 NVIDIA SOMA Retargeter 都可以把人体运动转换为机器人参考轨迹，适合在同一段输入动作上比较。ATLAS 的技术说明则在重定向步骤引用 GMR；它另外用现场感知、全身跟踪器、执行修正和失败重试来完成任务。GMR 可以是这类系统中的一个上游组件。[S1，第四节；S4；S5]

论文中的定量测试只覆盖 G1 仿真和 LAFAN1 动作子集，比较对象中没有 SOMA。论文数据因而不足以判断 GMR 和 SOMA 在 MicroDuck 或实机上的优劣，也无法直接推广到抓取等物体交互任务。[S1，第六节]

仓库相关研究：[SOMA Retargeter 与 MicroDuck](../soma-retargeter-research/soma-retargeter-research.zh-CN.md) · [ATLAS 与 SOMA 对 Robot RSI 的价值](../atlas-research/atlas-research.zh-CN.md)

## 6. 对 Robot RSI 的意义与 MicroDuck 最小验收建议

建议从已有的一段 MicroDuck 舞步开始，保留**人体原动作、机器人参考轨迹、策略实际轨迹**，用同一时间轴、单位和坐标约定对照。优先检查最早出现偏差的位置。

| 验收问题 | 要看的记录 | 如何决定下一步 |
|---|---|---|
| 参考动作本身可行吗？ | 支撑脚滑移、足底穿地、身体自碰、关节速度尖峰、默认站姿到首帧的过渡，以及异常帧号 | 若参考阶段已经丢失抬脚幅度，先检查骨架映射、缩放和逆运动学权重 |
| 策略既做完也做准了吗？ | 完成率与动作质量分开计分；在相同舞步上同时记录抬脚高度、身体摆幅、足端轨迹误差 | 若两组都能完成，以幅度和跟踪误差辨别哪一组保留了原动作 |
| 偏差在哪个执行环节出现？ | 对齐 MuJoCo 与 Isaac/PhysX 中的同一段参考、下发指令与实际关节响应 | 若 MuJoCo 跟得上、切换环境后才出现幅度缩水，分别复查物理引擎与 BAM 电压型执行器、PD 执行器的差异，每次只改变一个因素 |

如比较 GMR 与 SOMA，建议固定人体片段、机器人模型、训练预算、奖励、起始帧和评测种子，只替换参考动作生成方法。该方案等待批准后执行。

## 7. 证据索引

- **S1 论文原文** [arXiv:2510.02252v1（PDF）](https://arxiv.org/pdf/2510.02252v1)。图 2 为方法流程，表 I 为完成率，表 II 为跟踪误差，图 3 为典型轨迹异常，表 III 为起始帧对照。
- **S2 作者项目页** [Retargeting Matters：动作与失败案例对照视频](https://jaraujo98.github.io/retargeting_matters/)。
- **S3 官方实现** [YanjieZe/GMR](https://github.com/YanjieZe/GMR)。
- **S4 SOMA 方法与 MicroDuck 演示** [NVIDIA 技术说明](https://developer.nvidia.com/blog/adapt-human-motion-for-robots-with-nvidia-soma-retargeter/)。
- **S5 ATLAS 架构与重定向引用** [ATLAS 作者技术说明](https://atlas-humanoid.github.io/blog/)。
