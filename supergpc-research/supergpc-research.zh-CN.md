---
document_id: "RSI-021"
title_zh: "SuperGPC 与 Robot RSI：CoLA、SuperMimic 和 Antigravity 中文调研"
title_en: "SuperGPC for Robot RSI: CoLA and Comparisons with SuperMimic and Antigravity"
language: "zh-CN"
kind: "research_report"
evidence_as_of: "2026-11-26"
indexed_on: "2026-11-26"
---

# SuperGPC 与 Robot RSI：CoLA、SuperMimic 和 Antigravity 中文调研

<!-- BEGIN GENERATED READING SUMMARY -->
## 阅读摘要 · Reading Summary

**核心问题：** SuperGPC 怎样结合 SuperMimic、离散运动先验与 CoLA，并与 Antigravity 分工支持 Robot RSI？

- [FACT] [AS_OF:2026-11-26] SuperGPC 将 SuperMimic 式训练接入 FSQ 跟踪器，再训练自回归运动先验与条件低秩任务适配；CoLA 部署切换使用已训练权重。
- [AUTHOR_REPORT] [AS_OF:2026-11-26] 作者报告单 RTX 5090 约 29.7 小时完成 tracker、prior 与 joystick CoLA；新旧数据、机器人及训练条件不同，且该总时长不含 get-down 训练。
- [DISCUSSION] SuperMimic 提供上游运动训练方法，SuperGPC 增加能力复用，Antigravity 组织场景、控制与实验；真实反馈回流、独立留出验收及三者集成仍需另建。

**适用边界：** 核查官方文章、固定版代码规范、模型卡及上游项目资料；结果按作者报告，当前动作评估无独立留出集，私有语料限制精确复现。本文没有运行训练、验证权重或实施 MicroDuck 迁移。

**相关文档：** [RSI-016 SuperMimic 中文调研](../supermimic-research/supermimic-research.zh-CN.md)；[RSI-002 Antigravity Robotics Plugin 与机器人仿真自我改进中文调研](../antigravity-robotics-plugin-research/antigravity-robotics-plugin-research.zh-CN.md)；[RSI-018 如何让一次实验的结果能成为下一次实验的输入](../%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5/%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5.zh-CN.md)

[返回总目录 · Research Index](../README.md)
<!-- END GENERATED READING SUMMARY -->

调研与归档日期：2026-11-26（新加坡时间）。对象来自用户提供的 Dollhouse Robotics SuperGPC 截图。本文合并项目分析、CoLA 解释，以及与 SuperMimic、Antigravity Robotics Plugin 的比较。

**结论：SuperGPC 将 SuperMimic 式运动跟踪训练接到 GPC 的离散运动先验与任务适配流程中，帮助降低候选运动策略的产生和复用成本。对 Robot RSI，它提供快速训练与模块化任务适配；真实失败回流、下一轮练习选择和独立真机验收仍需外层系统连接。**

本文依据官方文章、固定版代码与训练规范、官方模型卡，以及原 GPC 和 SuperMimic 项目资料。耗时和任务演示按作者报告保存；本次没有运行训练、下载验证权重或开展 MicroDuck 迁移实验。

**后续实测 · 2026-11-27**　MicroDuck 用本地动作先验和落脚反馈跟跳整段 Figure 4。冻结策略在 24 个配对条件下，MuJoCo 通过完整三拍 24 次，原生 PhysX 跳完 11 次、通过完整三拍 0 次。归档包含单个 ONNX、七段原速回放和逐回合数据。[MicroDuck 全身舞段训练记录](./microduck-dance-20261127/README.md)

## 1. 项目定位与资料

- SuperGPC 发布文章：[SuperGPC: training a humanoid autoregressive motion policy fast, on one GPU](https://www.dollhouserobots.com/posts/super-gpc)，Carlos Diaz-Padron，2026-11-25。[S1]
- 训练代码：[DollhouseRobotics/super-gpc](https://github.com/DollhouseRobotics/super-gpc)，本次检视版本 `22b9a9d80f1431c9b7e161bcfc8c65f8b5ea0e8b`，采用 Apache-2.0。[S2]
- 官方模型包：[dollhouserobotics/G1-25-DOF-GPC](https://huggingface.co/dollhouserobotics/G1-25-DOF-GPC)。[S6]
- 原 GPC：*GPC: Large-Scale Generative Pretraining for Transferable Motor Control*，SIGGRAPH 2026；GPC 指 Generative Pretrained Controllers。[S4]
- 上游训练方法：[SuperMimic](https://supermimic.github.io/)，用学习到的可微动力学模型加速全身运动跟踪训练。[S5]

研究问题有三层：怎样训练能覆盖多种运动的底座；怎样从底座适配具体任务；怎样把这些训练过程放入真实反馈驱动的持续改进循环。

## 2. 三阶段训练与执行接口

| 阶段 | 学习对象与监督 | 产物及复用方式 |
|---|---|---|
| Stage 1 跟踪器与技能编码 | 参考动作进入 encoder，经 FSQ 离散瓶颈，由 sensor-conditioned decoder 输出关节动作；采用学习动力学与想象回报梯度训练 | 跟踪器、离散编码空间和动作解码器 |
| Stage 2 自回归运动先验 | 冻结 Stage 1，从其 fresh expert rollouts 获取 token 标签，用交叉熵训练状态条件先验 | 可根据当前身体状态生成运动编码的 prior |
| 任务 CoLA | 冻结 prior 与 decoder，通过 PPO 训练任务适配器和 critic | joystick、get-down 等任务控制器 |

[FACT] 当前实现中，16 个七级 FSQ 标量分成 4 组，每组对应一个词表大小为 2,401 的 token。每 20 ms，根据当前传感状态依次生成这 4 个 tokens，再由冻结解码器产生动作。[S2–S3]

prior 的自回归依赖发生在当前控制步的四个 tokens 内，没有跨控制步的历史 token context window。prior 读取当前传感帧，decoder 另读取最近 10 帧。token 的作用由编码与当前机器人状态共同决定，不能把单个 token 直接解释为完整的“走路”或“起身”技能。[S3]

Stage 2 复用跟踪器产生的控制经验，任务适配再把速度、朝向等命令连接到运动分布。GPC 的原方法还允许在有指定动作示例时先做 SFT，再进行任务 RLFT；SuperGPC 当前发布的 joystick 和 get-down 配方需要按各自实现阅读。[S2, S4]

## 3. SuperMimic 加速了哪一部分

[FACT] 第一阶段交替执行：在 MJLab／MuJoCo 中收集状态转移，拟合动力学世界模型，在一次策略更新内固定世界模型，通过想象 rollout 的回报梯度优化跟踪策略，再返回仿真继续采样。梯度通过学习到的模型传播，不要求物理仿真器本身可微。[S2, S5]

原 SuperMimic 使用连续 latent；SuperGPC 保留其 model-based optimization，并引入离散 FSQ 瓶颈，使后续运动先验能够学习 token 分布。加速来源还包括接触奖励、采样、精度与执行方面的工程选择，不能把整条流程的速度变化只归因于一个算法。[S1–S3]

需要区分三个反馈范围：

- 动力学模型和 critic 可以使用训练期特权动力学 context，部署策略使用相应传感观察。
- 源码的 `RealEnv` 是 MJLab／MuJoCo 环境，名称相对于 learned-model imagination；它不是接入真实机器人数据的证据。
- 后续任务适配仍用 PPO；没有把全部阶段都改成世界模型梯度训练。[S2–S3]

## 4. CoLA 是什么

**CoLA 全称 Conditional Low-rank Adaptation，即条件低秩适配。**它在已有运动先验上加入较小的任务适配分支，用任务命令调节这个分支，复用底座已有的运动协调能力。[S4]

SuperGPC 的实现采用 DoRA 低秩残差，并通过 FiLM 按任务输入缩放、偏移中间特征。相较普通 LoRA 的低秩权重修正，CoLA 增加显式任务条件调制。同一个已训练 joystick 适配器可以接收不同速度与朝向命令，无须为每个命令值单独训练模型。[S2]

| 阶段 | 保持冻结 | 被更新或使用的部分 |
|---|---|---|
| 任务训练 | prior 与动作 decoder | 任务适配器、critic 及相应训练状态 |
| 部署执行 | 已训练权重 | 当前身体观察、任务命令、token 采样与动作输出 |
| 任务切换 | 共享底座 | 在已训练适配器之间切换或插值 |

[AUTHOR_REPORT] 作者展示了 G1 从 joystick 切到 get-down、再切回的实机演示，每次约一秒过渡。该结果覆盖展示的适配器组合；不能推广为任意任务组合的可靠切换。[S1]

[DISCUSSION] 运行时切换属于执行能力，参数更新发生在训练阶段。冻结底座提供版本边界，但仍需评价适配后的行为、任务过渡及旧能力回归；不能仅由冻结或平滑插值推定无遗忘或可靠部署。

## 5. 单卡约 30 小时的计算口径

[AUTHOR_REPORT] 官方文章公布以下工程训练记录。[S1]

| 阶段 | 旧配置 | SuperGPC 新配置 |
|---|---|---|
| Stage 1 tracker | 132 h，4 GPUs | 16.8 h，1×RTX 5090 |
| Stage 2 prior | 65 h，4×RTX 5090 | 12.2 h，1×RTX 5090 |
| Joystick CoLA | 6.1 h，1×RTX 5090 | 46 min，1×RTX 5090 |
| 合计 | 约 203 h，约 794 GPU-h | 约 29.7 h，约 30 GPU-h |

这组记录的墙钟时间约缩短到原来的七分之一，GPU-hours 约缩小 26 倍，但作者明确说明它**不是受控 benchmark**：旧语料约 225 h，新语料约 56 h，机器人模型、仿真器及旧 joystick 奖励也有差异。统计还排除了运行故障和作业间隙。[S1]

“约 30 小时”只相加 tracker、prior 与一个 joystick CoLA 的训练，不包含另行展示的 get-down 适配器训练时间，也不是从数据准备到真机部署的总工期。

[DISCUSSION] 这些数字支持整套工程训练流程加快；算法、数据缩减、配置与工程优化的独立贡献，还需要匹配条件的消融。已有合适底座后，新任务可以主要训练适配器，但所需时间取决于任务是否在底座能力范围内。

## 6. 评测与开源范围

### 6.1 训练集覆盖与留出泛化分开报告

[FACT] 固定版规范设置 `VAL_PERCENT=0`，全部动作 clips 用于训练，相关动作评估也来自训练 clips。因此报告的跟踪表现主要说明训练语料覆盖，不能直接标为留出动作泛化结果。[S2]

官方模型卡中的 tracking、接触质量、抗推及 get-down 等指标有各自仿真口径。真机视频可以支持被展示行为的存在；仿真百分比不能改写成真机统计成功率。[S1, S6]

### 6.2 训练代码公开与精确复现的条件

[FACT] 仓库公开各阶段训练、评估和 ONNX 导出代码；官方模型包提供相关 ONNX、原生检查点、配置、指标与 Miniverse 工件。该次模型卡记录约 55.8 h、24,467 clips（含镜像），原动作语料来自四个私有数据集，并未随权重公开。[S2, S6]

仓库默认的 50 小时语料配置与上述已发布运行应分开。模型卡还指出原生 `.pt` 来自较早的内部代码版本，推荐 ONNX 作为运行接口；公开代码、模型和配置并不消除数据访问与版本对应的复现条件。[S6]

当前代码面向定制 G1，包含 25 个身体关节与额外头部关节；博客或模型包名称中的 25DoF、某次运行固定头部的条件，与当前代码中的头部朝向扩展应分别阅读。不能把现成权重当作所有 G1 配置或 MicroDuck 的通用控制器。[S1–S3, S6]

## 7. SuperGPC 与 SuperMimic 比较

两者是上游训练方法与下游控制系统的关系：SuperGPC 使用 SuperMimic 式训练构建第一阶段，再增加离散运动先验与任务适配。

| 维度 | SuperMimic | SuperGPC |
|---|---|---|
| 主要目标 | 高效学习覆盖大量动作的跟踪器 | 训练可复用运动先验并适配具体任务 |
| 核心训练 | 世界模型、策略和 critic 交替更新，通过想象回报训练策略 | Stage 1 世界模型训练，Stage 2 token 监督，任务 CoLA PPO |
| 运动表示 | 原方法连续 latent | FSQ 离散编码供自回归先验使用 |
| 常见部署条件 | 身体状态与参考动作 | 身体状态，以及适配器提供的任务命令 |
| 任务复用 | 复用跟踪器，结合新参考或上层控制 | 复用 prior 与 decoder，训练任务适配器 |
| 对 RSI 的直接贡献 | 降低运动跟踪策略学习成本 | 支持基础运动与任务候选分开迭代 |

[AUTHOR_REPORT] SuperMimic 的“1 H100 约 3 h”表示其跟踪训练达到超过已发布 SONIC 基线回报的节点；SuperGPC 的“1 RTX 5090 约 29.7 h”涵盖三个阶段。GPU、数据、机器人配置及达标目标不同，不能用 3 对 30 直接判断快慢。SuperGPC 第一阶段的 16.8 h 也不是与该节点匹配的受控比较。[S1, S5]

[PROPOSAL] 对 MicroDuck，可先比较现有 PPO 与 SuperMimic 式跟踪训练，再根据动作库规模和多任务需求判断是否增加 FSQ prior 与 CoLA。这样能分别测量训练方法和后续任务复用的收益。

## 8. SuperGPC 与 Antigravity Robotics Plugin 比较

这里的 Antigravity 指此前研究的 Google Robotics Plugin。它帮助外部智能体制作场景与资产、编写控制器、审计物理、运行仿真、调用 RL 工作流和比较候选；SuperGPC 专注运动策略训练与任务适配。[S7]

| 维度 | SuperGPC | Antigravity Robotics Plugin |
|---|---|---|
| 核心问题 | 怎样高效学会、生成和适配身体运动 | 怎样组织机器人场景、控制、训练和验证工作 |
| 主要输入 | 动作参考、机器人状态、任务命令 | 用户目标、机器人与场景资料、代码和执行日志 |
| 主要产物 | 跟踪器、运动 prior、CoLA 和策略权重 | 场景、控制代码、实验配置、日志、评价及调用训练所得策略 |
| 主要改进对象 | 神经网络中的运动控制能力 | 场景、代码、奖励、配置、流程及被调用的策略 |
| RSI 角色 | 候选运动策略的训练与适配 | 外部智能体组织实验和改进证据 |

Antigravity 包含 RL 任务编写与训练工作流，不能把它的能力只概括为场景生成。它与 SuperGPC 也不是现成的无缝组合：后者基于 MJLab 和自己的训练实现，前者的相关 RL 工作流主要围绕 MuJoCo Playground／RSL-RL。共享 MuJoCo 仍需对接观察、动作、控制时序、训练命令、检查点与评价接口。[S2, S7]

[PROPOSAL] 可以探索由外部智能体诊断失败、修订场景或任务，再调用 SuperGPC 训练候选，最后交给独立评价器。此处是组合方案，公开资料没有证明插件已经提供该集成或自动完成全部闭环。

## 9. 对 Robot RSI 与 MicroDuck 的研究建议

[DISCUSSION] SuperGPC 的价值包括降低候选产生成本、分开管理底座与任务版本，以及保存可追溯的实验工件。规范记录解析后的配置、数据清单、机器人资产、teacher／prior 身份和指标，并检查原生推理与 ONNX 导出的一致性。这些工件便于下一轮研究读取；导出一致性本身不验证真实任务效果。[S2]

可以将职责放入以下外层循环：

**真实失败 → 修订数据、动力学或任务奖励 → 快速训练候选 → 独立仿真与真机复测 → 保留或回滚。**

当前链路的世界模型更新主要来自仿真，运行时适配器切换也没有展示现场权重学习。真实失败自动采集、训练内容选择、动力学校准和独立候选接纳，仍需额外建设。

[USER_CONTEXT] 用户希望后续研究 MicroDuck 的夹爪、嘴／喙与头部触觉交互，相关意向记录于 [MD-014 后续研究计划](https://github.com/ReadbytheBeach/my-microduck/blob/main/docs/research/触觉交互后续研究计划.md)。这些方向不能由 G1 运动权重或头部朝向控制直接推定已支持；接触观察、物体状态和任务评价需要另行建立。

[PROPOSAL] 一个范围清楚的起点是：固定小型参考动作集、机器人模型和评价器，比较现有 PPO 与 learned-dynamics 跟踪方法。分别记录物理仿真采样、模型训练、策略训练与评价成本；留出不同动作片段或动力学条件，测量跟踪误差、稳定性、滑移、动作质量、延迟和旧能力回归。

动作库与多任务需求明确后，再在相同底座、任务条件和预算下比较全量任务训练与 CoLA。一次候选完整周期还应计入数据采集、人工复位和真机复测，避免只用训练墙钟代表学习效率。

若匹配条件下快速训练不能稳定改善留出表现，或更复杂结构的计算与调试成本抵消收益，应保留较简单基线。本文只保存方案，不启动训练或部署。

## 10. 关联阅读

- [RSI-016 SuperMimic 中文调研](../supermimic-research/supermimic-research.zh-CN.md)：学习动力学与运动跟踪训练的上游方法。
- [RSI-002 Antigravity Robotics Plugin 中文调研](../antigravity-robotics-plugin-research/antigravity-robotics-plugin-research.zh-CN.md)：场景、控制器、审计和实验组织工作流。
- [RSI-018 如何让一次实验的结果成为下一次实验的输入](../如何让一次实验的结果能成为下一次实验的输入/如何让一次实验的结果能成为下一次实验的输入.zh-CN.md)：固定评价器、实验记忆及候选接纳流程。

这些关联说明模块如何衔接，不表示相关项目已完成集成或采用相同预算与成功判据。

## 11. 证据索引

- **S1 官方发布文章**：[SuperGPC](https://www.dollhouserobots.com/posts/super-gpc)，2026-11-25。支持阶段耗时、比较条件、真机适配器切换演示；数字按作者报告引用。
- **S2 固定版本仓库与规范**：[README](https://github.com/DollhouseRobotics/super-gpc/blob/22b9a9d80f1431c9b7e161bcfc8c65f8b5ea0e8b/README.md)、[docs/spec.md](https://github.com/DollhouseRobotics/super-gpc/blob/22b9a9d80f1431c9b7e161bcfc8c65f8b5ea0e8b/docs/spec.md)。支持训练阶段、CoLA、数据划分、工件与导出检查及代码许可。
- **S3 固定版本关键源码**：[prior.py](https://github.com/DollhouseRobotics/super-gpc/blob/22b9a9d80f1431c9b7e161bcfc8c65f8b5ea0e8b/src/super_gpc/rl/prior.py)、[real_env.py](https://github.com/DollhouseRobotics/super-gpc/blob/22b9a9d80f1431c9b7e161bcfc8c65f8b5ea0e8b/src/super_gpc/tasks/tracking/rl/real_env.py)。支持当前步 token 自回归与物理仿真环境的职责。
- **S4 原 GPC 官方资料**：[项目页](https://yi-shi94.github.io/gpc-page/)、[ProtoMotions GPC 指南](https://nvlabs.github.io/ProtoMotions/user_guide/gpc.html)。支持 FSQ、生成先验、CoLA 定义及 SFT／RLFT 的区别。
- **S5 SuperMimic 官方项目页**：[SuperMimic](https://supermimic.github.io/)。支持世界模型训练方法、计算口径及跟踪评测范围；计算数字按其作者报告引用。
- **S6 官方模型卡与模型包**：[G1-25-DOF-GPC](https://huggingface.co/dollhouserobotics/G1-25-DOF-GPC)。支持该次运行的数据清单、仿真指标、公开工件和原生检查点版本说明。
- **S7 Antigravity Robotics Plugin**：[README](https://github.com/google-deepmind/robotics-antigravity-plugin)、[RL 工作流](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/main/plugins/robotics/skills/mujoco-playground-rl/SKILL.md)、[控制器迭代工作流](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/main/plugins/robotics/skills/sim2real-iteration/SKILL.md)。用于本次职责比较；详细固定版核查与边界保留于 RSI-002。
