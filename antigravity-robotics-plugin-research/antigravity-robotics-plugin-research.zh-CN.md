# Antigravity Robotics Plugin 与机器人仿真自我改进中文调研

调研日期：2026-11-22（新加坡时间）。对象来自用户提供的医院走廊、Stretch 3 为 PPE 抽屉补货的三视角截图，并结合 MicroDuck 嘴部可作为拾取末端的应用设想。

**结论：Antigravity Robotics Plugin 把场景与资产制作、物理审计、控制代码、仿真评测和 RL 训练连接成可由外部智能体组织的工作流，适合作为 Robot RSI 的实验基础设施。截图展示的医院任务与作者公开提示词高度匹配，但画面不能证明该任务已经训练成功、完成真机迁移或具备持续自我改进能力。对 MicroDuck，应分别研究鸭子的任务能力学习，以及外部智能体组织实验和改进工作流的能力。**

本次阅读了 Google 官方公告、发布者提示词、插件说明和相关审计、训练、迭代及评分源文件。未取得截图对应的医院任务代码，未运行插件、RL 训练或真机实验。下文区分公开能力、源码边界与拟议实验。

## 1. 截图身份与项目资料

截图包含标题“Hospital Ward Corridor — Restock Isolation PPE Drawer from Supply Shelf”，右上标注 Stretch 3 与 Shelf-Level View；主视图、第三人称和腕部视图展示金属货架、蓝白包装及抽屉推车。

2026-11-19，Zhutian (Skye) Yang 发布的示例提示词与这些要素高度吻合：使用 Antigravity Robotics Plugin 构建 MuJoCo 医院补给场景，让 Stretch 3 将手套盒和隔离衣包从货架转移到 PPE 推车抽屉，并要求 Blender 高质量背景及多视角输出。[S1]

这种文字与构图匹配支持识别其来源；本次没有取得对应任务工件，不能逐帧验证视频、动力学执行和成功判据。该画面应作为仿真制作演示理解，不能写成真实医院部署效果。

- 官方发布：Google Developers Blog，2026-11-17。[S2]
- 代码仓库：[google-deepmind/robotics-antigravity-plugin](https://github.com/google-deepmind/robotics-antigravity-plugin)。
- 本次检视版本：`3dde33820355c70fe8d8e33e42707cdcb742ceb4`。
- 插件代码采用 Apache-2.0；运行时调用的模型服务、下载的软件与机器人资产遵循各自条款。[S3]

## 2. 它提供哪些可核查能力

| 环节 | 公开实现或工作流 | 对 RSI 的作用与边界 |
|---|---|---|
| 场景和资产制作 | MuJoCo 场景编辑、Blender 资产制作、Studio 预览 | 降低构造实验的成本；生成结果仍需审计 |
| 物理资产审计 | 静态结构检查与十种动态测试 | 排除部分建模缺陷；不代替实测参数校准 |
| 控制与迁移 | DeviceLayer、感知、IK、运动规划、视觉伺服 | 支持代码控制器在仿真和指定硬件间迭代 |
| 控制器评测 | Gauntlet、目标判据检查、扰动、日志、失败分叉 | 将失败转为可比较的候选实验 |
| 策略训练 | MuJoCo Playground、Warp、RSL-RL 工作流 | 支持构造任务并训练策略；没有截图任务的训练证据 |
| 更强意义的 RSI | 可以由外部智能体串联这些组件 | 仍需证明多轮改进优于同预算的固定流程 |

这些能力不宜压缩为“生成一段视频”。但也不能仅由仓库提供训练技能，就声称任意生成场景已经成为可靠训练环境。[S3–S7]

## 3. 场景生成后必须检查什么

### 3.1 几何与物理是不同问题

医院提示词要求抽屉关节、凹形碰撞几何、质量和摩擦，并要求合成平滑轨迹及渲染。这些是作者提出的目标，不是对应场景已通过验证的证明。漂亮画面可能遮蔽碰撞体封住容器、抽屉轴向错误、惯量失真或物体由脚本移动等问题。

训练任务需要确认物体运动由允许的机器人动作和接触产生。直接改物体状态可用于初始化或评价器测试，但不能替代被评测的拾取、搬运行为。必须检查截图任务自身的代码和执行日志，才能判定它采用哪条路径。

### 3.2 审计有实际工具，也有适用范围

`mujoco-audit` 检查静态结构、尺度、碰撞与视觉几何、质量惯量、摩擦和关节；动态场景包括稳定落地、容器空腔、关节范围及高速穿透等。文档明确，默认阈值是可配置启发式，不是普遍物理定律。[S5]

资产标准要求参考真实物体校准尺寸、质量和接触行为，避免用看似相近的商品规格覆盖可信扫描。[S6] 因此审计通过说明满足相应检查，不能保证某个现实抽屉的阻尼或某种包装的摩擦已经准确。

## 4. 确实包含 RL 训练工作流

`mujoco-playground-rl` 给出了通过 MuJoCo Playground、PyTorch/Warp `reaf-sim` 与 RSL-RL 编写任务、训练和部署 checkpoint 的流程。它涉及机器人 DeviceLayer、动作与观察、奖励、终止条件、重置、GPU 批量运行及回放，并非仅有自然语言宣传。[S7]

但必须区分三项产物：

1. **场景工件：**可以加载、交互和复位的模型与资产。
2. **控制器或策略：**手写或生成的控制代码，或者经过 RL 更新的策略参数。
3. **学习证据：**预算、训练曲线、留出任务结果、回归与真实迁移记录。

一个成功轨迹视频不足以确认第二项采用了参数学习，也不足以建立第三项。截图医院任务目前应保留在“来源高度匹配、训练过程未核实”的范围内。

## 5. 控制器迭代与成功判定

### 5.1 失败分叉与配对比较

`sim2real-iteration` 和 `sim2real-gauntlet` 提供确定性 episode 分叉、同种子配对比较、扰动与 MCAP 日志。可以先定位失败时刻，再让不同候选从可比条件继续执行；比较协议还要求场景与种子匹配，并允许结果为无效、更差、不可区分或更好。[S8, S9]

这有利于检验“修改为什么有效”。单次成功不应自动接纳为新基线，额外运行时间与候选筛选成本也要计入。

### 5.2 真值隔离与评价器自检

非 RL 控制工作流要求经 follower DeviceLayer 操作，禁止控制器直接读取特权物体 `mj_data.xpos`。评审规则要求目标从实时相机或接触反馈定位，避免记住固定 MJCF 坐标。[S4, S10]

`preflight.py` 包含目标判据的正负控制：初态、悬空、放错位置或错误物体进入目标等状态应失败，构造的正确终态应成功。[S11] 其中直接设置状态用于测试评价器，并不代表正常任务可用相同方式完成。

这些规则可以帮助防止投机，但截图任务是否遵守规则仍需单独验证。生成者同时编写场景、策略和成功判据时，尤其需要独立固定评价器。

### 5.3 真机 success=None 的具体范围

该版本 `sim2real-gauntlet` 的 `grade.py` 明确说明：此评分路径的真实日志仅携带关节位置，因此真机 episode 的 `success` 为 `None`；仿真包含相应物体位姿和力信息时，才结合任务谓词、静止与释放条件计算成功。[S12]

**这不表示整个插件无法观察真机。**其他技能提供相机、定位与闭环控制。它说明这个评分器尚未自动解决任意真实任务的完成判定；真机奖励或验收仍需接入适当的视觉、传感或人工评价。

## 6. 对 Robot RSI 的意义

插件可以服务于两条彼此关联但不同的改进方向。

| 方向 | 学习或修改对象 | 核心证据 |
|---|---|---|
| 机器人任务能力 | 控制器、动作策略或其参数 | 新任务成功率、恢复能力、真实迁移与旧能力保持 |
| 外部智能体的实验组织能力 | 场景构造、失败诊断、任务采样、代码、工具和实验记忆 | 同预算下更快产生有效候选、减少无效训练并提高后续学习效率 |

第二条方向不必每轮更新外部大模型权重，也可以通过持久实验记忆和可复用工作流积累改进。但工具调用次数增加、代码修改成功或仿真分数提高，都不自动等于严格 RSI。需要比较自适应改进流程和固定改进流程的多轮效果。

值得保留的组合是：**真实反馈决定问题，场景与资产工具扩大练习量，训练产生候选，独立验证决定保留哪些改进。**Antigravity 提供其中多段工具；完整闭环仍需版本、预算、反馈、评价与部署管理。

## 7. MicroDuck 应用 嘴部拾取与移动操作

用户说明 MicroDuck 嘴部可作为拾取末端，因此可以规划从原地夹取到运送的任务序列。嘴部开口、扭矩、传感、控制接口及可承载范围尚未明确，下面不假定具体规格。

官方公开工作流涉及 SO-101、YAM 和 FR3 Duo 等平台；没有据此确认 MicroDuck 可直接接入。[S2–S4] 需要先实现本体、嘴部动作、观察与控制的适配，并校准延迟、接触和执行限制。

### 7.1 鸭子的任务能力分阶段学习

| 阶段 | 任务 | 独立验收重点 |
|---|---|---|
| A 原地夹取 | 稳定站立，嘴部接近、闭合并抬起物体 | 物体确实离开支撑并保持，身体不失稳 |
| B 原地放置 | 将物体放入目标区并张嘴释放 | 释放后物体留在目标区，不能只靠嘴托住 |
| C 携物移动 | 夹持后沿短路径行走 | 完成路径且物体未掉落，步态与姿态可接受 |
| D 避障运送 | 从起点拾取，绕过障碍后放置 | 全流程完成、接触与碰撞符合预定约束 |

各阶段先从易测量的刚性物体和简单场景开始，再扩展尺寸、质量、摩擦与布局。参数范围应来自测量或明确的待检验假设。携物可能改变重心、头部惯量和步态需求，需要评测运动与夹持的耦合，不能把“原地能咬住”直接视为“行走时能携带”。

### 7.2 外部智能体组织实验

外部智能体负责把“途中掉落”等现象转成候选解释，选择低成本诊断，组织场景变体或训练，并保存结果。它可以借鉴审计、episode 分叉和配对比较；但应把这些机制适配到 MicroDuck 的执行后端，而不是假设现有手臂任务接口可直接复用。

若改变嘴部控制、物体质量或移动策略，应明确每个候选的修改、父版本、假设和资源消耗。先定位是观察误差、执行接口、接触模型还是行为策略问题，再决定是否需要重新训练。

## 8. 最小实验与评价设计

### 8.1 先验证任务和评价器

首个实验只做原地夹取并放置，采用固定基线与少量可复查场景。确认嘴部动作实际生效、物体受接触驱动、复位可重复。独立评价器在释放并等待稳定后判定完成，同时用悬空、错误目标、未释放、物体掉落等负例测试，避免“输出成功”或“命令已发送”被当作任务完成。

仿真物体真值可以供评价器使用；策略只接收计划在部署时可获得的观察。真实评价需要事先确定可测量手段，不能默认该插件的 `grade.py` 已提供通用成功信号。

### 8.2 匹配预算 比较改进机制

比较三种流程：固定任务采样、等量随机补充变体、失败驱动的自适应变体与诊断。保持机器人基线、动作接口、留出场景和评价器一致，匹配真机时间、仿真交互、训练计算及候选评测预算。为检验外部智能体的作用，也要记录其模型调用、代码修复和失败作业成本。

先验证原地任务，再依次进入携物和避障阶段。每次候选都复测旧任务；只改善当前场景却损害站立或原有运动能力的更新，不应视为能力净增益。

### 8.3 同时衡量学习效率与运行效率

| 维度 | 应回答的问题 | 建议记录 |
|---|---|---|
| 学习效率 | 每轮资源投入带来多少可迁移能力净提升 | 留出任务学习曲线、真机小时、人工分钟、仿真量、GPU 时间、智能体调用和验证成本 |
| 运行效率 | 更新后机器人能更可靠、更经济地完成多少任务 | 每小时可靠完成量、端到端时间、掉落率、复位时间、接管与恢复次数 |

不同资源应分别报告，或明确价格假设后计算总成本，不能直接把机器人小时、人工分钟与 GPU 小时相加。外循环的更强检验是：系统积累经验后，能否在相同预算下更有效地决定下一轮学什么，而不仅是继续增加训练量。

## 9. 与其他研究的连接

- [SimReady Central 中文调研](../simready-central-research/simready-central-research.zh-CN.md)：关注可复用资产、物理元数据与资产版本；与任务和工作流制作互补。OpenUSD 资产导入 MuJoCo 后仍需验证碰撞、关节和动力学行为，不能假定跨引擎物理效果相同。
- [PEAR 与 Robot RSI 中文调研](../pear-research/pear-research.zh-CN.md)：提供仿真后训练内循环与真实反馈外循环的分层，以及学习效率、运行效率两个评价维度。
- [如何让一次实验的结果能成为下一次实验的输入](../如何让一次实验的结果能成为下一次实验的输入/如何让一次实验的结果能成为下一次实验的输入.zh-CN.md)：提供固定评价器、预算、实验记忆和候选接纳的训练 Harness 设计，可用于组织上述 MicroDuck 实验。

## 10. 证据索引

下列插件文件固定到检视版本 `3dde33820355c70fe8d8e33e42707cdcb742ceb4`。MicroDuck 任务与实验方案属于基于用户本体说明提出的研究设计。

- **S1 截图来源线索**：[作者主帖](https://x.com/ZhutianYang_/status/2123233209295249766)、[医院任务提示词](https://x.com/ZhutianYang_/status/2123233300357812582)、[可读取镜像](https://nitter.gq/ZhutianYang_/status/2123233300357812582)。发布于 2026-11-19。
- **S2 Google 官方公告**：[Gemini 4 Hydrogen: a faster model for general purpose robotics](https://developers.googleblog.com/gemini-hydrogen-for-robotics/)。发布于 2026-11-17，支持插件定位、场景工作流与官方硬件示例；应用耗时为官方演示披露。
- **S3 仓库说明与许可**：[README.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/README.md)。
- **S4 仿真与真实控制接口**：[mujoco-playground/SKILL.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/mujoco-playground/SKILL.md)。
- **S5 资产审计**：[mujoco-audit/SKILL.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/mujoco-audit/SKILL.md)。
- **S6 资产结构与物理要求**：[mujoco_asset_standards.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/rules/mujoco_asset_standards.md)。
- **S7 RL 训练工作流**：[mujoco-playground-rl/SKILL.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/mujoco-playground-rl/SKILL.md)。
- **S8 仿真到真实的控制器迭代**：[sim2real-iteration/SKILL.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/sim2real-iteration/SKILL.md)。
- **S9 评测与日志接口**：[sim2real-gauntlet/SKILL.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/sim2real-gauntlet/SKILL.md)。
- **S10 控制器评审规则**：[critic_rubric.md](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/sim2real-iteration/references/critic_rubric.md)。
- **S11 评价器正负控制实现**：[preflight.py](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/sim2real-gauntlet/src/robosim_gauntlet/preflight.py)。
- **S12 成功判定与真机评分范围**：[grade.py](https://github.com/google-deepmind/robotics-antigravity-plugin/blob/3dde33820355c70fe8d8e33e42707cdcb742ceb4/plugins/robotics/skills/sim2real-gauntlet/src/robosim_gauntlet/grade.py)。
