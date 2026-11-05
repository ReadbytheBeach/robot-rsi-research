# CaPtain 与 Physical Critic：中文技术调研

调研日期：2026-11-05（新加坡时间）。对象来自用户提供的“港中文 MMLab / CaPtain / Physical Critic”截图。

**结论：CaPtain 的研究价值在于把小型视觉语言模型训练成能编写机器人控制代码的智能体，并用训练期可见的仿真物理状态改善请求级信用分配。它提供了实际的参数学习流程，但现有证据不能直接等同于递归自我改进（RSI）。**

本报告阅读了官方仓库说明、SFT/RL 文档、critic 源码、训练配置、Harness 的评测协议与完成判定代码。没有运行训练、机器人评测或下载模型权重；没有读取论文 PDF 全文。下文结果是作者披露，并非独立复现。

## 1. 项目定位与资料

- 标题：**CaPtain: A Pipeline for Post-Training Code-as-Policy Robot Agents**。
- 作者：Yijia Fan、Xilin He、Yilei Jiang、Dongming Wu、Jiaxu Wang、Xiangyu Yue。[S1]
- 主仓库：[waltstephen/CaPtain](https://github.com/waltstephen/CaPtain)。
- 环境仓库：[waltstephen/CaPtain-Harness](https://github.com/waltstephen/CaPtain-Harness)。
- 官方仓库给出的论文入口：[arXiv:2610.40799](https://arxiv.org/abs/2610.40799)、[PDF](https://waltstephen.github.io/captain/assets/paper/CaPtain.pdf)。本次未读取这两个入口的正文。
- 主仓库检视版本：`a6b799b49349db6e97a375ca0d6d8a1cc99747a8`。
- 该版本绑定的 Harness：`de38d6d63b710caf356320a3c046b72b6d299514`。以下 Harness 证据均对应此固定版本。
- 仓库声明代码采用 MIT，基础模型权重沿用 Qwen3.5-4B 的许可证，SAM 3 权重需单独接受许可。[S1, S8]

与之前调研的 TAMPAgent 不同，CaPtain 当前确实公开了训练与环境代码。本次核查了这些源文件，未验证所有权重、数据和资产能否完整下载，也没有据此宣称已经实现端到端复现。

## 2. 先纠正截图中容易误解的说法

| 说法 | 核查结果 |
|---|---|
| “无需预训练” | 若理解成从零训练，则不成立。它以已预训练的 **Qwen3.5-4B** 为基础，再做 SFT 和 RL。[S1–S3] |
| “只有 4B 参数” | **策略模型**为 4B；完整系统还调用 SAM 3、Molmo2-8B 等感知服务。不能把整个机器人系统视为仅有一个 4B 模型。[S1, S8] |
| “自主编写 Python 控制机器人” | 有代码与接口支持，但代码调用的是已经实现的低层感知、测量、IK 和带保护的运动接口，不是模型直接生成电机控制电流。[S5] |
| “不需要 VLA” | 作者的部署路径不依赖额外的 benchmark-trained VLA；但依赖训练好的 VLM、感知模型、运动实现和机器人标定。[S1, S5] |
| “Physical Critic 懂物理规律” | 源码体现为基于物理状态特征预测成功概率的价值函数，不是显式物理定律求解器，也不是预测未来视频的世界模型。[S3, S4] |

“不需要从头预训练一个新模型”可以成立；“没有预训练与训练依赖”不能成立。

## 3. 推理时系统如何运行

策略通过一个 `python` 工具使用持久 Python 会话，反复执行：

**读图与指令 → 写 Python 调用工具 → 获得测量和执行回执 → 调整下一段代码 → 调用 finish() 结束。**

Harness 提供 22 项低层能力及 `finish()`，包括观察、分割、目标选择、几何测量、坐标变换、运动预览、IK 相关运动、夹爪动作与接触检查。[S5]

作者强调没有暴露完整的“抓取物体”“放置物体”高层宏技能。这个描述针对策略接口；后端仍包含相当多工程能力。例如迁移文档披露 RoboTwin/RoboDojo 后端包含自动选臂、倾斜重试、抓取反馈或交接等行为。因此“低层接口”不等于“底层实现没有任何任务相关启发式”。[S6]

必须区分三个组件：

1. **策略模型**决定调用什么工具、写什么代码。
2. **Harness 和机器人后端**负责执行、测量、预算、回执及运动保护。
3. **训练期 critic**根据隐藏状态提供训练信号。

critic 不承担部署时逐动作发放形式化执行证书的职责；这与 TAMPAgent 的约束检查入口不同。

## 4. Physical Critic 到底做什么

### 4.1 解决信用分配问题

机器人可能经历许多轮模型请求和工具调用，最后才得到“成功/失败”。只给整条轨迹同一个奖励，难以区分哪次请求改善了局面、哪次浪费预算。

CaPtain 在训练时记录每次模型请求前的仿真状态，并训练价值函数估计当前状态最终成功的概率，再用请求前后的价值变化分配信用。[S3, S4]

一个模型请求可以触发多个工具调用，因此这里的粒度是**模型请求级**，不能直接称为每次电机动作或每个代码 token 都有独立物理评分。

### 4.2 输入和网络

训练文档列出：36 个物理特征、请求索引，以及 40 类任务的 one-hot 编码；包括从物体、末端执行器、抓取和目标进展等信息构造的特征。[S3, S4]

critic 从离线收集的 SFT 策略轨迹预热，再与策略训练共同更新。参考配置 `critic_hidden: "none"`，表示最终配方不读取策略模型隐藏向量；源码虽支持隐藏向量分支，不能把可选分支误写为最终训练配置。[S3, S4]

文档描述使用 5 个三层、宽度 256 的 MLP 成员。在线 CoCritic 对成员 logits 求均值，再经 sigmoid 得到概率。[S3, S4]

**信息隔离：**critic 可以读取训练期的特权仿真状态；策略只能读取允许的图像、代码输出、测量和工具回执，不能直接读取对象真值位姿、成功谓词或目标进展。这属于特权信息辅助训练。[S3–S6]

### 4.3 请求级优势估计

参考文档的非终止请求增量为：

```text
δ_t = c_t + V(s_(t+1), t) − V(s_t, t)
δ_T = c_T + R_i − V(s_T, T)
A_GAE(t) = Σ_k λ^k δ_(t+k),  λ = 0.9
```

其中 `c_t ≤ 0` 为即时成本。两次价值评估使用同一个时间索引 t，即 **same-t**，避免仅因“时间过去了一轮”而产生价值变化信用。[S3, S4]

实际优势还结合相同初始状态的四条 rollout：

```text
G_i = R_i + Σ_t c_t
A(i,t) = (G_i − mean_group(G))
       + (A_GAE(i,t) − mean_time(A_GAE(i,·)))
```

随后用历史优势标准差的 EMA 缩放。它不是简单地把“物体离目标更近”直接当作唯一奖励。[S3, S4]

还要避免另一种误解：**价值预测增加不是严格的因果证明**。它受 critic 误差、状态特征、策略变化和奖励设计影响。

## 5. 训练流程与人工设计部分

### 阶段 A：SFT

Qwen3.5-4B 经机器人智能体轨迹监督微调，得到 CaPtain-4B-SFT。

公开配方包含 24,440 行、约 797.1M token 的混合数据，其中有通用智能体轨迹、困难任务教师演示、学生自生成成功轨迹和视觉问答。**训练行不等同于独立机器人 episode**。大部分智能体轨迹来自闭源前沿教师模型。[S2]

因此，部署时不调用前沿模型，不代表数据生产阶段没有使用前沿模型。

### 阶段 B：RL

从 SFT 检查点开始，进行 300 rounds、75 次优化器更新，总计 76,800 个训练 episode；每轮 64 个初始状态，每个状态四条 rollout。[S3]

终局返回包括成功并自主结束 +1、成功但未自主结束 +0.25、错误结束 −0.3、预算耗尽 −0.1；还包含动作成本、失败动作成本、代码执行成本、成功后继续运行的成本等。[S3]

此外有两个不能省略的人工设计：

- 8 个困难任务使用分阶段子目标奖励。
- critic 对持续低成功概率的部分 episode 提前停止；设置 5% 不截断控制样本，困难任务豁免。[S3]

所以不能仅根据 SFT→RL 提升，把全部收益归因于“Physical Critic”，也不能称最终配方只有纯终局奖励、完全无需任务特定设计。应通过匹配奖励、早停和总交互预算的消融实验分离贡献。

## 6. 实验结果：哪些数字可以比较

以下为作者报告，成功率单位为百分比。[S1]

| 基准 | 评测 episode | SFT host / strict | RL 后 host / strict |
|---|---:|---:|---:|
| LIBERO，保留初始状态 11–16 | 240 | 55.4 / 52.1 | 73.8 / 67.5 |
| LIBERO-PRO Pos+Task，6-cell | 600 | 59.5 / 56.7 | 78.5 / 71.5 |
| LIBERO-PRO Pos+Task，8-cell | 800 | 49.2 / 45.1 | 68.6 / 58.9 |
| LIBERO-Plus，7 类扰动 | 700 | 48.6 / 44.6 | 66.1 / 59.0 |
| LIBERO-MAX Dynamic | 80 | 40.0 / 40.0 | 61.2 / 50.0 |

- **host：**episode 最终状态满足目标谓词。
- **strict：**host 成功，并且智能体自主调用 `finish()`。
- LIBERO host 提升 18.4 个百分点；strict 提升 15.4 个百分点。
- 这些保留初始状态实验不等于所有测试目标语义均未在训练中出现；训练覆盖 LIBERO 的 40 个任务，初始状态划分与任务语义划分必须区别。[S3, S5]

### 6.1 RoboTwin：曾成功、最终成功、自主结束不同

作者披露 50 任务 × 100 episode：[S6]

| 指标 | 全部 50 任务 |
|---|---:|
| ever，过程中曾满足成功条件 | 22.6% |
| host，最终状态成功 | 19.5% |
| strict，最终成功且自主结束 | 8.4% |

22.6% 的作者报告 95% CI 为 21.5–23.8%。33 个单臂子集的 ever 为 30.0%，不能代替全部任务表现。

后端使用双 Franka Panda，官方参考设置使用 aloha-agilex；Franka 基座各向桌面移动 0.10 m。还增加深度、接触信号等输入。因此，与其他方法的排行榜数字并列时，需要核对机器人本体、传感和执行条件。[S6]

### 6.2 SimplerEnv：83.3% 不是官方步数预算下的结果

作者报告 WidowX visual-matching 四任务、共 96 episode，最终成功率 **83.3%**；同文档披露，在官方 **60/120 步 horizon** 下仅 **4.2%**。[S6]

该运行使用更长的任务运行范围、增加的腕部 RGB-D 相机、渲染深度和接触信号，且绕过官方 delta 末端控制器，改用关节目标控制。[S6]

这并不抹去其代码策略执行能力，但说明不能据此直接宣称“同协议击败某 VLA”。正式对比应匹配输入、动作接口、仿真步数、模型请求数与墙钟预算。

### 6.3 CaP-Bench 与 RoboDojo

- CaP-Bench 的 75.0% 是 Lift 与 Stack 两项在原步数 horizon 下的均值，不是五项任务总体成功率。文档另列 Re-stack 最终 7/20、Nut 0/20、Wipe 0/20；Wipe 需要持续压桌，而现有带保护运动原语不提供这种能力。[S6]
- RoboDojo 的 1.7 是 leaderboard **Score**，不能直接写为 1.7% 成功率。[S1, S6]

### 6.4 自主完成判断的边界

Harness 的 completion gate 检查智能体自己的公开测量，不读取隐藏成功真值；但源码设置 `MAX_REJECTIONS = 2`，达到次数后放行结束声明，部分关节状态场景在一次拒绝后也可放行。[S7]

这表示它是带反馈的结束检查机制，并非不可绕过的完备成功证明。**放行结束声明不会自动把失败计为 host 成功**；最终成功谓词仍然是独立评分依据。

## 7. 真实机器人与复现条件

Harness 文档写明真实实验使用 XR1 机械臂、头部 RGB-D 和腕部相机，以及在粗略本体孪生仿真中适配过的检查点；该机器人驱动与适配检查点**不在本次开源发布中**。[S5]

因此：公开通用硬件接口是有价值的，但不能据此宣称下载 CaPtain-4B 后就能不经适配复现论文的真实机器人效果。

作者披露的资源：[S1–S3, S8]

| 工作 | 参考资源 |
|---|---|
| 单次推理评测 | 策略 GPU + 感知/渲染 GPU；LIBERO 每 episode 中位约 6 分钟 |
| SFT | 16 × H100-80GB，约 7.6 小时 / 120 GPU-hours |
| RL | 16 × H100-80GB，约 1,290 GPU-hours；另有 8-GPU 配置，训练卡显存接近 80GB |
| 依赖 | Linux、Python 3.10/3.11、多套仿真环境、bubblewrap、EGL；部分后端需要 Vulkan |
| 模型 | Qwen3.5-4B 派生策略、SAM 3、Molmo2-8B；部分无深度硬件可选 MoGe-2 |

4B 策略并不意味着训练和完整评测成本很低。建议先复现一个 LIBERO episode，再复现固定子集上的 SFT/RL 差异，最后才考虑重跑训练。不要先安装所有迁移仿真器。

## 8. 与 TAMPAgent 的关系

| 维度 | TAMPAgent | CaPtain |
|---|---|---|
| 主问题 | 如何让智能体计划满足可检查执行条件 | 如何把小 VLM 训练成有效的代码机器人策略 |
| 主要机制 | 任务/运动约束、工具证据、执行许可、状态更新 | SFT + 物理状态 critic 辅助 RL |
| 反馈作用 | 执行前后检查与重新规划 | 训练时分配请求级信用、改善参数 |
| 不确定性 | 公开描述显式语言假设和 belief 表示变化 | critic 可读特权状态，但不自动等于具备显式 belief 规划 |
| 改进证据 | 特定任务跨尝试记忆案例 | 参数更新后多项基准成绩提升 |
| 主要待解问题 | 技能积累、持续改进、延迟与感知误判 | 奖励归因、评测可比性、结束判断、真实迁移 |

二者可以互补：在保持相同的动作检查接口下，让小型策略学习更高效地提出计划和调用工具。但二者原始任务、机器人、工具与模型不同，不能直接拿现有成功率作优劣比较。

## 9. 对机器人 RSI 研究的意义

这里暂将 RSI 理解为 Recursive Self-Improvement（递归自我改进）。

CaPtain 比“只保存重试笔记”更进一步：它确实有自主采样轨迹与参数优化。但 critic 与策略共同训练，本身仍是研究者设计的学习算法；不能仅因二者同时更新就证明“系统改进了自身的改进方法”。

可以分成三个可检验层次：

1. **自反馈学习：**利用自身交互和环境反馈提升策略；CaPtain 为此提供代码和实验结果。
2. **持续泛化改进：**多轮学习后在未见任务、布局或机器人上稳定提升，并控制遗忘和成本；需要专门的持续学习评测。
3. **递归改进：**允许系统更新课程、技能搜索或学习策略，证明相同总预算下优于固定改进器；当前所读材料不足以证明这一层。

## 10. 推荐研究方向与最小实验

**建议题目：物理进展与约束失败反馈联合驱动的代码机器人自我改进。**

核心问题：与纯终局奖励相比，物理状态 critic、执行约束反馈及其结合，能否让小模型用更少交互学会可迁移的工具组合，同时改善自主结束判断？

### 第一阶段：分离 critic 与奖励工程的贡献

| 实验组 | 学习信号 | 要回答的问题 |
|---|---|---|
| A SFT 固定策略 | 不继续 RL | 起点表现 |
| B outcome RL | 终局奖励 + 匹配成本 | 普通 RL 带来多少提升 |
| C 固定物理 critic | B + 离线 critic | 密集信用分配是否有效 |
| D 在线物理 critic | B + 共训练 critic | 在线校准是否优于固定 critic |
| E 约束反馈 | B + 结构化执行失败/检查信息 | 无特权真值反馈是否有效 |
| F 联合反馈 | D + 与 E 相同的约束信息 | 二者是否互补 |

所有组匹配基础模型、工具、奖励成本、感知输入、总交互和评测预算。将困难任务分阶段奖励、critic 早停分别设为独立消融，不能只在某一组使用。

### 第二阶段：观察受限 critic

用部署期可见的测量、回执和图像训练 observation critic，与仿真特权 critic 比较；若做蒸馏，单列教师特权信息的作用。

特别关注：**真实物理状态变化很小，但感知行为增加了信息时，critic 是否低估其价值？** 纯物理状态 critic 未必表示智能体的知识状态，可能无法充分奖励消除遮挡与确认目标等信息获取行为。这是待实验检验的假设，不是已确认缺陷。

### 第三阶段：更严格 RSI 检验

允许系统更新经验提炼、任务采样或技能搜索策略，与固定更新策略比较；保持成功判据和封存测试集固定，不让学习器修改评分方式。

若只增加了训练量，不能称其为改进机制提升。应匹配总 GPU 时间、模型 token、交互次数和候选评估成本。

### 指标与实验划分

- 分开报告 ever、host、strict，以及错误结束、成功后继续动作、成功状态丢失。
- 同时报原生仿真步数预算与扩展预算成绩，避免把多运行时间当成算法优势。
- 成本使用每成功任务的模型 token、工具调用、墙钟时间、训练交互量。
- critic 评估 AUC、Brier、校准及分布偏移误差；重点检查低概率早停是否误杀困难但可解的任务。
- 分离未见初始状态、未见布局、未见任务语义与跨本体测试。
- 先做每类约 20 个独立种子的探索实验，再根据方差和效应大小规划正式样本量；正式学习曲线还应考虑多个训练随机种子。
- 不同后端包含的自动重试、选臂、交接和控制保护必须记录并保持一致。

### 可证伪条件

- C/D 在匹配预算下不优于 B：不能声称物理 critic 有额外收益。
- F 不优于 D/E：不能声称两种反馈互补。
- 收益只在训练见过的任务或扩展时间预算内出现：不能声称一般任务泛化或原生预算优势。
- 自适应改进器不优于固定改进器：不能提出更强的 RSI 成果主张。

## 11. 证据索引

以下均为本次实际阅读的固定版本源文件：

- **S1 项目说明与结果**：[CaPtain README](https://github.com/waltstephen/CaPtain/blob/a6b799b49349db6e97a375ca0d6d8a1cc99747a8/README.md)
- **S2 SFT 数据与训练**：[sft/README.md](https://github.com/waltstephen/CaPtain/blob/a6b799b49349db6e97a375ca0d6d8a1cc99747a8/sft/README.md)
- **S3 RL 方法与资源**：[rl/README.md](https://github.com/waltstephen/CaPtain/blob/a6b799b49349db6e97a375ca0d6d8a1cc99747a8/rl/README.md)、[参考配置](https://github.com/waltstephen/CaPtain/blob/a6b799b49349db6e97a375ca0d6d8a1cc99747a8/rl/configs/captain-4b.json)
- **S4 critic 实现**：[physics_critic.py](https://github.com/waltstephen/CaPtain/blob/a6b799b49349db6e97a375ca0d6d8a1cc99747a8/rl/physics_critic.py)、[critic_cotrain.py](https://github.com/waltstephen/CaPtain/blob/a6b799b49349db6e97a375ca0d6d8a1cc99747a8/rl/critic_cotrain.py)、[critic_features.py](https://github.com/waltstephen/CaPtain/blob/a6b799b49349db6e97a375ca0d6d8a1cc99747a8/rl/critic_features.py)
- **S5 Harness 设计、评分与真实机器人发布边界**：[docs/harness.md](https://github.com/waltstephen/CaPtain-Harness/blob/de38d6d63b710caf356320a3c046b72b6d299514/docs/harness.md)
- **S6 迁移评测协议及观察/控制差异**：[eval/transfer/README.md](https://github.com/waltstephen/CaPtain-Harness/blob/de38d6d63b710caf356320a3c046b72b6d299514/eval/transfer/README.md)
- **S7 完成判定代码**：[completion_gate.py](https://github.com/waltstephen/CaPtain-Harness/blob/de38d6d63b710caf356320a3c046b72b6d299514/src/captain_harness/adapters/capx/completion_gate.py)
- **S8 安装与依赖**：[INSTALL.md](https://github.com/waltstephen/CaPtain-Harness/blob/de38d6d63b710caf356320a3c046b72b6d299514/INSTALL.md)、[RELEASE_NOTES.md](https://github.com/waltstephen/CaPtain-Harness/blob/de38d6d63b710caf356320a3c046b72b6d299514/RELEASE_NOTES.md)

TAMPAgent 的证据与详细讨论见同仓库 [TAMPAgent 中文调研](../tampagent-research/tampagent-research.zh-CN.md)。
