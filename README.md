# 机器人递归自我改进研究 Robot RSI Research

围绕 MicroDuck，研究机器人如何利用示范、仿真、真实交互和失败反馈持续改进。仓库保存技术调研、训练闭环设计、实验记录及硬件资料，正文以中文为主。

A research archive on robot recursive self-improvement, with MicroDuck as an application platform. It connects demonstrations, simulation, real-world interaction, failure feedback, evaluation, and hardware. Most full documents are in Chinese; titles, navigation, and retrieval topics are bilingual.

## 从哪里开始 Start here

- **先看研究主线：**真实反馈提出问题，仿真扩大相关练习，训练产生候选，独立评价决定是否保留改进。任务内纠错、策略学习和改进学习过程本身，需要分别提供证据。
- **按问题找文档：**使用下面的阅读路径和分类目录，再阅读目标文档开头的核心问题、带证据标签的摘要与适用边界。
- **引用具体结论：**继续读取正文的相关章节、来源版本和证据索引。阅读摘要帮助定位，不替代实验条件或原始证据。

Start with the question-oriented routes below. Each indexed document has a stable ID, an English retrieval title, a short tagged summary, and a scope statement. Follow the full document and its sources before citing a result.

<!-- BEGIN GENERATED RESEARCH INDEX -->
## 推荐阅读路径 · Suggested Reading Routes

### 理解机器人学习闭环 · Understand the robot learning loop

1. [RSI-018 如何让一次实验的结果能成为下一次实验的输入](%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5/%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5.zh-CN.md)
2. [RSI-009 PEAR 与 Robot RSI 中文技术调研](pear-research/pear-research.zh-CN.md)
3. [RSI-004 CaPtain 与 Physical Critic：中文技术调研](captain-research/captain-research.zh-CN.md)
4. [RSI-006 HG-DAgger 中文调研与人工接管证据链方案](hg-dagger-research/hg-dagger-research.zh-CN.md)
5. [RSI-017 TAMPAgent 中文调研与机器人 RSI 研究方案](tampagent-research/tampagent-research.zh-CN.md)
6. [RSI-003 ATLAS 与 SOMA 对 Robot RSI 的价值：中文技术调研](atlas-research/atlas-research.zh-CN.md)

### 构建 MicroDuck 场景与嘴部操作实验 · Build MicroDuck scene and mouth-manipulation experiments

1. [RSI-002 Antigravity Robotics Plugin 与机器人仿真自我改进中文调研](antigravity-robotics-plugin-research/antigravity-robotics-plugin-research.zh-CN.md)
2. [RSI-012 NVIDIA SimReady Central 与机器人 RSI 仿真资产中文调研](simready-central-research/simready-central-research.zh-CN.md)
3. [RSI-011 Ropedia Xperience 2 × MicroDuck 训练方案：从真实场景到跨引擎验收](ropedia-xperience-2/ropedia-xperience-2.zh-CN.md)
4. [RSI-010 MicroDuck 在电子维修店交错通道中的训练与双引擎盲测](ropedia-xperience-2/MicroDuck%E5%95%86%E9%93%BA%E4%BA%A4%E9%94%99%E9%80%9A%E9%81%93%E8%AE%AD%E7%BB%83%E4%B8%8E%E5%8F%8C%E5%BC%95%E6%93%8E%E7%9B%B2%E6%B5%8B%E6%80%BB%E7%BB%93_20261119_093806.md)

### 检查动作参考与跟踪控制 · Inspect motion references and tracking control

1. [RSI-013 NVIDIA SOMA Retargeter：人体动作到 MicroDuck 策略的技术调研](soma-retargeter-research/soma-retargeter-research.zh-CN.md)
2. [RSI-005 GMR 人体动作重定向与 MicroDuck 参考轨迹验收：中文技术调研](gmr-research/gmr-research.zh-CN.md)
3. [RSI-016 SuperMimic 中文调研](supermimic-research/supermimic-research.zh-CN.md)

### 连接示范数据与口头纠正 · Connect demonstration data and verbal corrections

1. [RSI-015 Specialist Gripper 中文调研：硬件、双手同步与世界坐标轨迹重建](specialist-research/specialist-research.zh-CN.md)
2. [RSI-014 Specialist 数据重建 README 导读：管线、数据层与训练样本](specialist-research/specialist-data-pipeline.zh-CN.md)
3. [RSI-007 Moshi 全双工语音与 Robot RSI 人工纠偏：中文技术调研](moshi-research/moshi-research.zh-CN.md)
4. [RSI-006 HG-DAgger 中文调研与人工接管证据链方案](hg-dagger-research/hg-dagger-research.zh-CN.md)

### 进入机械与电子工程资料 · Explore mechanical and electronic engineering

1. [RSI-001 AI Mechanical Design：MicroDuck STEP 试运行](ai-mechanical-design-research/ai-mechanical-design-research.zh-CN.md)
2. [RSI-008 CH340C Type-C 转 3.3V TTL 转接板](pcb-design/README.md)

## 研究索引 · Research Index

### 学习闭环与反馈 · Learning Loops and Feedback

| ID | 中文文档 | English Title | 类型 · Type | 证据日期 · As Of |
|---|---|---|---|---|
| RSI-003 | [ATLAS 与 SOMA 对 Robot RSI 的价值：中文技术调研](atlas-research/atlas-research.zh-CN.md) | ATLAS and SOMA for Robot RSI: Video Demonstrations and Online Execution Correction | 技术调研 · Research review | 2026-11-19 |
| RSI-004 | [CaPtain 与 Physical Critic：中文技术调研](captain-research/captain-research.zh-CN.md) | CaPtain and Physical Critic: Post-Training Code-as-Policy Robot Agents | 技术调研 · Research review | 2026-11-05 |
| RSI-006 | [HG-DAgger 中文调研与人工接管证据链方案](hg-dagger-research/hg-dagger-research.zh-CN.md) | HG-DAgger and a Traceable Human Intervention Evidence Pipeline | 设计方案 · Design proposal | 2026-11-11 |
| RSI-009 | [PEAR 与 Robot RSI 中文技术调研](pear-research/pear-research.zh-CN.md) | PEAR and Robot RSI: Simulation Reinforcement Learning and Real-World Feedback Loops | 技术调研 · Research review | 2026-11-16 |
| RSI-017 | [TAMPAgent 中文调研与机器人 RSI 研究方案](tampagent-research/tampagent-research.zh-CN.md) | TAMPAgent: A Research Review and Robot RSI Study Proposal | 技术调研 · Research review | 2026-11-05 |
| RSI-018 | [如何让一次实验的结果能成为下一次实验的输入](%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5/%E5%A6%82%E4%BD%95%E8%AE%A9%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E7%BB%93%E6%9E%9C%E8%83%BD%E6%88%90%E4%B8%BA%E4%B8%8B%E4%B8%80%E6%AC%A1%E5%AE%9E%E9%AA%8C%E7%9A%84%E8%BE%93%E5%85%A5.zh-CN.md) | Turning One Experiment's Results into the Next Experiment's Inputs | 设计方案 · Design proposal | 2026-11-08 |

### 仿真资产 场景与实验 · Simulation Assets, Scenes, and Experiments

| ID | 中文文档 | English Title | 类型 · Type | 证据日期 · As Of |
|---|---|---|---|---|
| RSI-002 | [Antigravity Robotics Plugin 与机器人仿真自我改进中文调研](antigravity-robotics-plugin-research/antigravity-robotics-plugin-research.zh-CN.md) | Antigravity Robotics Plugin and Robot Simulation Self-Improvement | 技术调研 · Research review | 2026-11-22 |
| RSI-010 | [MicroDuck 在电子维修店交错通道中的训练与双引擎盲测](ropedia-xperience-2/MicroDuck%E5%95%86%E9%93%BA%E4%BA%A4%E9%94%99%E9%80%9A%E9%81%93%E8%AE%AD%E7%BB%83%E4%B8%8E%E5%8F%8C%E5%BC%95%E6%93%8E%E7%9B%B2%E6%B5%8B%E6%80%BB%E7%BB%93_20261119_093806.md) | MicroDuck Slalom Control Tuning and Dual-Engine Blind Testing in an Electronics Repair Shop | 实验记录 · Experiment report | 未注明 · Not specified |
| RSI-011 | [Ropedia Xperience 2 × MicroDuck 训练方案：从真实场景到跨引擎验收](ropedia-xperience-2/ropedia-xperience-2.zh-CN.md) | Ropedia Xperience 2 and MicroDuck: A Training Plan from Real Scenes to Cross-Engine Evaluation | 设计方案 · Design proposal | 2026-11-18 |
| RSI-012 | [NVIDIA SimReady Central 与机器人 RSI 仿真资产中文调研](simready-central-research/simready-central-research.zh-CN.md) | NVIDIA SimReady Central and Simulation Assets for Robot RSI | 技术调研 · Research review | 2026-11-22 |

### 动作参考与控制 · Motion References and Control

| ID | 中文文档 | English Title | 类型 · Type | 证据日期 · As Of |
|---|---|---|---|---|
| RSI-005 | [GMR 人体动作重定向与 MicroDuck 参考轨迹验收：中文技术调研](gmr-research/gmr-research.zh-CN.md) | GMR Human Motion Retargeting and MicroDuck Reference Trajectory Validation | 技术调研 · Research review | 2026-11-20 |
| RSI-013 | [NVIDIA SOMA Retargeter：人体动作到 MicroDuck 策略的技术调研](soma-retargeter-research/soma-retargeter-research.zh-CN.md) | NVIDIA SOMA Retargeter: From Human Motion References to MicroDuck Policies | 技术调研 · Research review | 2026-11-19 |
| RSI-016 | [SuperMimic 中文调研](supermimic-research/supermimic-research.zh-CN.md) | SuperMimic: Differentiable World Models and BPTT for Humanoid Motion Tracking | 技术调研 · Research review | 2026-11-09 |

### 示范数据与语言交互 · Demonstration Data and Language Interaction

| ID | 中文文档 | English Title | 类型 · Type | 证据日期 · As Of |
|---|---|---|---|---|
| RSI-007 | [Moshi 全双工语音与 Robot RSI 人工纠偏：中文技术调研](moshi-research/moshi-research.zh-CN.md) | Moshi Full-Duplex Speech and Human Verbal Corrections for Robot RSI | 技术调研 · Research review | 2026-11-21 |
| RSI-014 | [Specialist 数据重建 README 导读：管线、数据层与训练样本](specialist-research/specialist-data-pipeline.zh-CN.md) | A Guide to Specialist Data Reconstruction: Pipeline, Data Layers, and Training Samples | 技术导读 · Technical guide | 2026-11-10 |
| RSI-015 | [Specialist Gripper 中文调研：硬件、双手同步与世界坐标轨迹重建](specialist-research/specialist-research.zh-CN.md) | Specialist Gripper: Hardware, Bimanual Synchronization, and World-Frame Trajectory Reconstruction | 技术调研 · Research review | 2026-11-10 |

### 机械与电子工程 · Mechanical and Electronic Engineering

| ID | 中文文档 | English Title | 类型 · Type | 证据日期 · As Of |
|---|---|---|---|---|
| RSI-001 | [AI Mechanical Design：MicroDuck STEP 试运行](ai-mechanical-design-research/ai-mechanical-design-research.zh-CN.md) | AI Mechanical Design: MicroDuck STEP CAD Trial Plan | 设计方案 · Design proposal | 2026-11-09 |
| RSI-008 | [CH340C Type-C 转 3.3V TTL 转接板](pcb-design/README.md) | CH340C USB Type-C to 3.3V TTL Adapter Board | 硬件入口 · Hardware project | 未注明 · Not specified |

<!-- END GENERATED RESEARCH INDEX -->

## 人和模型共用的阅读格式 Shared reading format

| 层次 | 用途 Purpose |
|---|---|
| 本页 README | 人类浏览、双语主题索引和阅读顺序 / Human navigation and reading routes |
| [research-index.json](research-index.json) | 文档身份、类型、主题、日期、摘要和关联的权威注册表 / Canonical machine-readable registry |
| 每篇文档顶部 | YAML 身份信息与从注册表生成的阅读摘要 / Generated identity metadata and retrieval summary |
| 原有正文与证据索引 | 完整机制、条件、来源和实验范围 / Full argument, conditions, sources, and evidence |
| [AGENTS.md](AGENTS.md) | 模型按需阅读与维护索引的约定 / Agent reading and maintenance instructions |

这个组织方式借鉴 [thousand-brains](https://github.com/ReadbytheBeach/thousand-brains) 的双语索引、稳定编号、证据分层和机器注册表。这里把注册表单独保存为 JSON，便于程序直接解析，并用同一个文件生成 README 目录与文档入口，减少多份索引不一致。

The structure adapts the bilingual index, stable identifiers, evidence distinctions, and machine registry from `thousand-brains`. A separate JSON registry generates the human index and document entry blocks without extra Python dependencies.

### 稳定编号与日期 Identifiers and dates

- `document_id` 采用 `RSI-NNN`，用于永久引用；编号不表示时间顺序、质量排名或实验完成状态。新增文档追加编号，不因目录排序重新编号。
- 原路径和中文正文保留。英文标题是检索译名，除非正文另有说明，不作为论文官方英文标题的声明。
- `evidence_as_of` 保留原文明确的调研或证据日期；未明确时为 `null`。索引整理不代表重新核查了动态事实。
- `indexed_on` 表示首次纳入此阅读格式的日期。注册表的 `updated_on` 表示索引更新时间。两者都不能替代证据日期。
- 研究报告、设计方案、实验记录、技术导读和硬件入口分别标明 `kind`。有一份实验记录，不代表同主题下的全部方案已经执行。

Stable IDs and paths support durable citations. Evidence dates remain separate from indexing dates; `null` means the original document does not establish an evidence cutoff. Document types describe the material, not a blanket validation status.

### 证据标签 Evidence tags

标签作用于具体摘要命题或明确范围的段落，不能给混合内容的整篇文章统一加上“已验证”。

| 标签 Tag | 含义 Meaning |
|---|---|
| `[FACT]` | 可核查的项目、文档或源码事实；源码存在某个接口不等于接口已在本项目运行通过 / Verifiable source or code fact, not implied runtime validation |
| `[AUTHOR_REPORT]` | 项目作者或外部评测方报告的结果；保留归属和条件 / Externally reported result with attribution |
| `[AUTHOR_HYPOTHESIS]` | 原作者提出的假说 / Hypothesis attributed to the original author |
| `[LOCAL_RESULT]` | 仓库记录的本地实验、工具检查或合成数据结果；保留仿真、教学或硬件范围 / Locally recorded result with its actual scope |
| `[DISCUSSION]` | 调研中的分析、推断或类比 / Research interpretation or inference |
| `[PROPOSAL]` | 尚待实施或验证的设计与实验建议 / Proposed design or experiment |
| `[USER_CONTEXT]` | 用户提供的应用前提；不推定未知硬件规格 / User-provided application context |
| `[AS_OF:YYYY-MM-DD]` | 相应命题使用的证据日期 / Evidence cutoff attached to a claim |

模型总结时应保留文档 ID、结果归属、证据日期和适用边界。不能把作者自报、仿真结果、合成数据验证或设计建议改写成真实机器人独立复现。

When summarizing, retain document IDs, attribution, dates, and scope. Do not promote author reports, simulations, synthetic demonstrations, or proposals into independently verified real-robot results.

## 新增与维护 Adding and maintaining documents

1. 使用 [中文研究笔记模板](templates/research-note.zh-CN.md) 或保留已有、适合该材料的正文结构。
2. 在 `research-index.json` 中追加永久 ID、真实路径、双语标题和主题、原证据日期、短摘要、边界及关联 ID。按具体命题选择证据标签。
3. 运行 `python3 scripts/build_reading_index.py`，生成 README 索引、每篇元数据和阅读摘要。
4. 运行 `python3 scripts/build_reading_index.py --check`，检查编号、路径、日期、关联、主要文档覆盖和生成内容是否一致。
5. 同一个提交保存正文、注册表与生成内容。若更新了研究结论，先核查来源，再相应修改摘要和证据日期。

The registry is the source of truth for navigation metadata. Keep it and generated files in the same commit. The generator preserves the full document body; the consistency check does not rerun the research or certify an experiment.

覆盖检查以各主题目录第一层的自有 Markdown 为主文档；根目录说明，以及 `scripts/`、`templates/` 和工作目录不属于主题条目。第三方许可证、CREDITS、模型、数据、PCB 工程与分析产物保持各自格式，通过相应主题文档进入。注册表不将每个辅助资产当作研究报告，也不对原许可证追加阅读元数据。
