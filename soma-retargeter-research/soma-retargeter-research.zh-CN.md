---
document_id: "RSI-013"
title_zh: "NVIDIA SOMA Retargeter：人体动作到 MicroDuck 策略的技术调研"
title_en: "NVIDIA SOMA Retargeter: From Human Motion References to MicroDuck Policies"
language: "zh-CN"
kind: "research_report"
evidence_as_of: "2026-11-19"
indexed_on: "2026-11-23"
---

# NVIDIA SOMA Retargeter：人体动作到 MicroDuck 策略的技术调研

<!-- BEGIN GENERATED READING SUMMARY -->
## 阅读摘要 · Reading Summary

**核心问题：** SOMA如何为MicroDuck生成动作参考，参考动作又如何经独立训练成为可执行策略？

- [FACT] [AS_OF:2026-11-19] SOMA Retargeter把兼容人体骨架的BVH动作通过机器人映射、IK和后处理转为根部位姿与关节角CSV；它输出运动学参考，不直接输出低层电机命令或已验证控制策略。
- [FACT] [AS_OF:2026-11-19] 项目支持通过Robot Configurator导入URDF或MJCF建立自定义机器人配置；正文核对时列出的五种内置机器人不含MicroDuck，MicroDuck示例的策略训练是下游物理仿真阶段。
- [PROPOSAL] 建议先映射MicroDuck躯干和腿部、检查足部接触及限位，再接入动作跟踪训练并保留执行器建模、域随机化与独立验收；本报告未安装工具、生成轨迹或训练策略。

**适用边界：** 仅完成官方资料与接口调研及最小实验设计，没有MicroDuck端到端重定向、仿真跟踪或实机复现。

**相关文档：** [RSI-005 GMR 人体动作重定向与 MicroDuck 参考轨迹验收：中文技术调研](../gmr-research/gmr-research.zh-CN.md)；[RSI-016 SuperMimic 中文调研](../supermimic-research/supermimic-research.zh-CN.md)

[返回总目录 · Research Index](../README.md)
<!-- END GENERATED READING SUMMARY -->

调研日期：2026-11-19（新加坡时间）。对象为用户提供的 SOMA Retargeter 截图，以及 NVIDIA 官方技术博客、SOMA Retargeter 代码与配置文档、MicroDuck Isaac Lab 训练资料。

**结论：SOMA Retargeter 的作用是把人体动作转换成特定机器人可用的运动学参考轨迹；它本身不产生可直接部署的机器人控制策略。** 截图中的三栏依次表示人体动作、映射后的 MicroDuck 参考动作、以及在物理仿真中训练出的动作跟踪策略。对 MicroDuck 而言，SOMA 可以作为动作参考生成和模仿学习的前端，与 Isaac Lab / Newton 的物理训练互补。真正的平衡、接触稳定性、执行器适配和真机部署仍需要单独训练和验收。[S1, S2]

本报告为技术调研与实验建议。没有安装 SOMA Retargeter、没有生成 MicroDuck 轨迹、没有运行仿真或训练策略。

## 1. 项目定位与资料

- 项目：**NVIDIA SOMA Retargeter**。
- 官方介绍：[Adapt Human Motion for Robots with NVIDIA SOMA Retargeter](https://developer.nvidia.com/blog/adapt-human-motion-for-robots-with-nvidia-soma-retargeter)，2026-11-13。[S1]
- 代码仓库：[NVIDIA/soma-retargeter](https://github.com/nvidia/soma-retargeter)。代码许可为 Apache-2.0。[S2]
- 官方 MicroDuck 仿真训练背景：[Using AI Agents to Teach Robots Like Microduck to Walk in Simulation](https://developer.nvidia.com/blog/using-ai-agents-to-teach-robots-like-microduck-to-walk-in-simulation)。[S3]
- MicroDuck Isaac Lab 训练与部署教程：[Train in Simulation, Deploy on a Real Robot: Microduck with Isaac Lab 3.0](https://huggingface.co/blog/nvidia/microduck-isaac-lab-sim-to-real)。[S4]
- SOMA 参考人体动作：[BONES-SEED](https://bones.studio/)；其数据许可和使用条件需单独核查。[S1, S2]

SOMA 是一个人体到人形机器人的动作重定向工具链，围绕 SOMA 人体骨架表示，将兼容的 BVH 动作映射到机器人身体结构。项目目前处于 beta 阶段，API 和功能可能变化。仓库列出的五种内置机器人是 Unitree G1、Unitree H2、Booster T1、AgiBot X2 Ultra 和 AgiBot A3T3，MicroDuck 不在这一内置清单中。[S1, S2]

## 2. 截图中的三栏代表什么

| 截图栏位 | 技术含义 | 产物 |
|---|---|---|
| Human motion | 原始人体动作，例如 BONES-SEED 的动作捕捉数据 | SOMA 骨架 BVH |
| Retargeted motion | 按 MicroDuck 身体比例和关节结构解算出的参考动作 | 根位置、根朝向和逐帧关节角 CSV |
| Trained policy | 在物理仿真中训练出的控制策略跟踪参考动作 | 策略模型和仿真回放 |

NVIDIA 说明其 MicroDuck 示例先将 Bones 人体动作适配到机器人，再对每段动作训练控制器。图中间栏是运动学重定向输出，右栏是下游策略在 Isaac Lab / Newton 仿真中的执行结果。两者不是同一个模块。[S1]

## 3. SOMA 的动作重定向流程

### 3.1 输入与标准化

动作来源可包括动作捕捉、视频重建、在线数据集或动作生成模型。输入需要转换成符合 SOMA 基础骨架的 BVH。不同骨架和文件格式之间的转换，是进入重定向前的独立数据处理步骤。[S1, S2]

### 3.2 机器人比例与骨架映射

Robot Configurator 支持导入 URDF 或 MJCF XML，并建立 SOMA 人体部位到机器人连杆的映射。工具根据机器人目标配置调整尺度、参考姿态和关节对应关系。导入单位要求为米、弧度和千克，坐标方向假设为 +Z 向上、+X 向前、+Y 向左。[S5]

### 3.3 逆运动学与后处理

Newton 上的 IK 求解器逐帧寻找机器人关节姿态，以满足选定的人体目标点和姿态目标。无法同时匹配所有目标时，IK 权重决定身体部位优先级。后处理可以进行关节限制、平滑以及足部着地修正，降低参考轨迹中的脚底滑动。[S1, S2, S6]

### 3.4 输出

输出 CSV 含机器人根位置、根姿态和目标机器人关节值。后续需要将 CSV 转换成训练框架使用的动作库或参考轨迹格式。CSV 是期望运动，不是低层电机命令或已验证的控制策略。[S1, S2]

## 4. SOMA 与 MicroDuck 训练体系的关系

NVIDIA 的 MicroDuck Isaac Lab 教程已提供基本行走训练环境。教程描述策略使用 61 个观测值并输出 14 个关节位置目标，同时使用 Newton 物理和 Better Actuator Models（BAM）模拟舵机响应，并随机化质量、质心、摩擦、关节惯量、编码器偏移、电池压降、命令延迟和关节间隙。[S4]

SOMA 轨迹可以补充该体系的**动作参考**：

1. 人体动作经过 SOMA 转换为 MicroDuck 运动学目标。
2. 将目标轨迹作为参考输入训练任务。
3. 策略读取参考动作和当前机器人状态，输出控制动作。
4. 仿真根据物理接触和执行器动力学反馈结果。
5. 用跟踪误差、平衡、接触、能耗和动作安全指标评估策略。

这与按速度命令训练的普通行走策略目标不同。普通行走策略学习响应方向或速度指令，动作跟踪策略则尝试复现特定的参考步态或动作。两类策略应分别评价。

## 5. 对 MicroDuck 的可行性判断

### 5.1 可以尝试自定义机器人配置

SOMA 的 Robot Configurator 支持 URDF 和 MJCF，因此若 MicroDuck 的模型可用且拓扑受支持，技术上可以建立自定义配置。工作项包括：

- 检查 MicroDuck 的 URDF/MJCF、网格、关节命名、关节轴和限位。
- 建立 SOMA 骨架与 MicroDuck 连杆/关节的对应关系。
- 设定参考姿态和尺寸比例。
- 为双脚设计接触修正与 IK 目标。
- 验证前进、转向、抬脚、落脚、动作首尾帧和限位行为。
- 将导出的 CSV 接入 Isaac Lab 动作跟踪任务。

上述是依据 SOMA 对自定义机器人导入方式和 NVIDIA MicroDuck 训练接口作出的**工程可行性判断**，不是已完成的 MicroDuck 端到端复现。[S4, S5]

### 5.2 微型双足机器人的适配风险

SOMA 的示例主要是人形机器人。MicroDuck 的尺度、自由度、躯干比例和动作范围不同，配置中的 IK 目标与权重必须适配。若人体轨迹要求 MicroDuck 无法达到的摆腿高度、步幅或躯干姿态，IK 可能生成形式上有效但物理上不稳定的参考动作。

SOMA 配置器文档还提示，高自由度灵巧手目前不是其目标用例。对 MicroDuck 的基础步态实验，优先只映射躯干和腿部，不需纳入手部骨架目标。[S5]

## 6. 技术限制与证据边界

1. **运动学不等于动力学可行。** 关节轨迹视觉上合理，不证明机器人能在重力、惯性和地面接触作用下稳定跟踪。仓库要求在仿真中验证安全性、可行性和控制器兼容性后再上硬件。[S2]
2. **参考动作不等于策略。** SOMA 导出 CSV，动作跟踪策略仍需通过 Isaac Lab 或其他控制训练流程获得。[S1, S4]
3. **映射参数影响结果。** 比例、参考姿态、IK 权重和足部着地修正可能改变运动结果，应固定版本并逐项调优。[S1, S5, S6]
4. **域差异仍存在。** 即使参考动作在仿真可跟踪，真实舵机延迟、间隙、电池压降、传感和接触仍需通过 BAM 参数标定、域随机化和真机测试处理。[S3, S4]
5. **Beta 软件和依赖风险。** SOMA 仓库声明处于 beta，当前安装要求 Linux 或 Windows x86-64、Python 3.12、兼容 NVIDIA GPU 和驱动，模型资产通过 Git LFS 下载。[S2]
6. **数据许可分开管理。** 代码采用 Apache-2.0；仓库内示例 BVH、优化器输入和 CSV 使用单独的 NVIDIA Sample Data Evaluation License。其他 BONES-SEED 动作应按数据集自身许可使用。[S2]

## 7. 推荐的 MicroDuck 最小实验

### 研究问题

**使用 SOMA 生成的参考动作训练，能否让 MicroDuck 更稳定地完成指定的步态变化或转向动作，同时保持平衡与可接受的能耗？**

### 实验阶段

#### 阶段 A：模型和动作输入核查

- 确认 MicroDuck 当前 URDF/MJCF 与关节定义。
- 选择一段简单、可重复的人体动作，例如原地踏步、缓慢前进或小角度转向。
- 检查输入动作是否为 SOMA 兼容 BVH，以及数据许可是否适用于计划用途。
- 确认 SOMA 输出的关节列与 MicroDuck 训练环境关节顺序一致。

#### 阶段 B：建立 SOMA MicroDuck 配置

- 导入机器人模型并核对单位、坐标轴、关节限位和参考姿态。
- 先映射躯干与腿部目标。
- 对动作全过程进行可视化检查，关注脚底穿透/悬空、落脚漂移、关节触限和身体左右镜像。
- 固定初版配置与动作文件版本，生成参考 CSV。

#### 阶段 C：仿真跟踪训练

- 在 Isaac Lab 中建立动作跟踪训练任务，使策略同时读取动作参考和 MicroDuck 当前状态。
- 用 Isaac Lab / Newton 训练控制策略，保留 BAM 与有界域随机化。
- 先使用单条简单动作验证接口，再扩展到多条动作和不同速度/初始姿态。
- 将 SOMA 参考跟踪策略与现有速度行走策略分开保存，避免混淆策略用途。

#### 阶段 D：独立验收

评估集应包含未参与 IK 权重调优的动作片段或不同初始状态。记录：

- 动作跟踪误差及其峰值
- 跌倒、重置、碰撞和足底滑移
- 关节位置、速度、力矩和控制饱和
- 任务完成率与完成时间
- 每次成功动作的能耗或稳定代理指标
- 策略推理频率、观测延迟和动作输出连续性

先在 Isaac/PhysX 中冻结策略并运行留出测试，再按项目现有安全流程评估真机。验收阈值应由 MicroDuck 项目既有基准确定，不在本报告中臆定。

### 对照组

| 实验组 | 参考输入 | 目的 |
|---|---|---|
| A：现有基线 | 速度/方向命令 | 了解现有行走策略性能 |
| B：SOMA 跟踪 | 单一 SOMA 重定向动作 | 验证动作映射和跟踪训练能否跑通 |
| C：多动作跟踪 | 多个重定向动作与变化速度 | 检验策略对动作变化的泛化 |

### 可证伪条件

- 若 B 组在仿真中无法稳定跟踪，则先修正机器人配置、参考动作或 IK 权重，不进入真机。
- 若跟踪误差改善但跌倒、滑移或执行器饱和变差，则不能判定策略整体提升。
- 若仅在参与 IK 调优的动作上有效，则证据不足以支持泛化。
- 若 C 组不优于 B 组的留出动作表现，则不能声称多动作训练提升了泛化。

## 8. 对 Robot RSI 闭环的价值

SOMA 可作为 Robot RSI 中“人类演示转为机器人参考行为”的模块，为策略训练提供更丰富的初始动作样本。它不负责自主选择任务、定义验收标准、验证跨引擎一致性或批准真机部署。

建议将其输出纳入版本化训练证据包：

- 人体动作来源及许可
- SOMA 版本、配置、机器人模型版本
- 原始 BVH 与转换后的 CSV
- IK 和足部修正参数
- Isaac Lab 训练配置与策略检查点
- Isaac/PhysX 验收结果及失败片段
- 真机日志与回退策略

这样可以把“动作重定向质量”和“控制策略跟踪质量”分开追踪，便于识别失败来自动作参考、机器人映射、动力学模型还是控制器。

## 9. 证据索引

- **S1 NVIDIA SOMA Retargeter 技术介绍与 MicroDuck 示例：** [NVIDIA Technical Blog](https://developer.nvidia.com/blog/adapt-human-motion-for-robots-with-nvidia-soma-retargeter)
- **S2 官方代码、支持机器人、输入输出、beta 状态和许可：** [NVIDIA/soma-retargeter](https://github.com/nvidia/soma-retargeter)
- **S3 MicroDuck 障碍课程、Newton/Isaac Lab 和真机迁移流程：** [Using AI Agents to Teach Robots Like Microduck to Walk in Simulation](https://developer.nvidia.com/blog/using-ai-agents-to-teach-robots-like-microduck-to-walk-in-simulation)
- **S4 MicroDuck 61 维观测、14 关节动作、BAM、域随机化与 ONNX 部署：** [Microduck with Isaac Lab 3.0](https://huggingface.co/blog/nvidia/microduck-isaac-lab-sim-to-real)
- **S5 自定义 URDF/MJCF 机器人配置、单位、坐标和映射检查：** [Robot Configurator 文档](https://github.com/nvidia/soma-retargeter/blob/main/documentation/robot-configurator.md)
- **S6 接触检测与足部着地修正：** [Contact detection & foot-plant correction 文档](https://github.com/nvidia/soma-retargeter/blob/main/documentation/foot-contact.md)
