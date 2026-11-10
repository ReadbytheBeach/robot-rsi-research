# 连接器、电源与 USB 保护器件核查

> 最终工程采用对外 3.3V ≤50mA 的保守使用预算。下文提到的 100mA 为选型阶段的热估算例子，不是最终额定输出承诺。

日期：2026-11-10。用于本项目 CH340C、30×30 mm、双层 1.0 mm、顶层器件方案。

## 已取得的厂家资料

| 器件 | PDF | 内容与来源 |
|---|---|---|
| AP2112K-3.3TRG1 | `AP2112.pdf` | Diodes Incorporated DS39724 Rev.2-2，June 2017，18页；来自 GitHub 保存的厂家文档镜像 |
| USBLC6-2SC6 | `USBLC6-2.pdf` | STMicroelectronics DS4260 Rev.7，December 2021，20页；来自 GitHub 保存的厂家文档镜像 |

精确镜像 URL、提交和 SHA256 见 `verified-mirror-sources.json`。原始厂家 URL 分别为 `https://www.diodes.com/assets/Datasheets/AP2112.pdf` 和 `https://www.st.com/resource/en/datasheet/usblc6-2.pdf`；本环境直接访问被代理策略拒绝。下载内容已用 PDF 魔数和文本内容检查，未把网页误存为 PDF。

## AP2112K-3.3TRG1

KiCad 符号：`Regulator_Linear:AP2112K-3.3`；封装：`Package_TO_SOT_SMD:SOT-23-5`。

| 引脚 | 定义 | 本项目连接 |
|---|---|---|
| 1 | VIN | 保险丝后的 USB 5V |
| 2 | GND | GND |
| 3 | EN | VIN，高电平使能 |
| 4 | NC | 不连接 |
| 5 | VOUT | +3V3 |

厂家资料第1页给出 SOT25 顶视引脚，第2页给出应用与引脚表。KiCad 别名继承 AP2204K-1.5 的图形与引脚，但本器件属性／MPN 必须保持 AP2112K-3.3TRG1，不应改为 AP2204K。

- 输入输出各需至少 1.0 µF 有效电容；推荐 X5R／X7R，厂商第2页明确提及。
- 推荐使用输入4.7µF或更高、输出10µF，并计入 DC bias 降容；不能只看标称值。
- 数据表额定输出600mA不等于该 USB 小板可向外持续输出600mA。建议本板外部输出设计目标100mA，仍需加上 CH340C 和指示电路电流核算 USB 负载与热耗散。
- 功耗近似 `P=(VIN−3.3V)*I_total`。仅100mA外部负载在5V输入下就产生约170mW，不含芯片自耗。厂家无散热器 SOT25 θJA 表值184°C/W只能用于量级估计，不能代替本板测温。
- 不允许从 UART 连接器反向向3.3V输出供电；AP2112含输出放电行为，不能把它当作电源自动切换器。

## USBLC6-2SC6

KiCad 符号：`Power_Protection:USBLC6-2SC6`；封装：`Package_TO_SOT_SMD:SOT-23-6`。

厂家第1页：USB2.0最高480Mb/s、I/O对地电容最大3.5pF，SOT23-6L顶视引脚。

| 引脚 | 定义 | 使用示例 |
|---|---|---|
| 1、6 | I/O1，器件内部共用一条保护通道 | USB D+ 从一侧进，另一侧出 |
| 3、4 | I/O2，器件内部共用另一条保护通道 | USB D− 从一侧进，另一侧出 |
| 2 | GND | 尽短接地，附近过孔 |
| 5 | VBUS | USB 5V 电源钳位参考 |

靠近 USB 插座布置，避免把过长支线引到保护器件。通道可交换，但每对线必须保持完整对应，不得把1与3误认为一条内部连接。VBUS不是3.3V钳位参考。

## JST SUR 0.8 mm 4PIN 卧插

候选 MPN：`SM04B-SURS-TF(LF)(SN)`，JST SUR 系列0.8mm水平／侧向插入、表面贴装。

本机标准封装：

`Connector_JST:JST_SUR_SM04B-SURS-TF_1x04-1MP_P0.80mm_Horizontal`

封装0°、顶层视图、原点为封装原点时：

| 焊盘 | X / mm | Y / mm | 大小 / mm | 定义 |
|---|---:|---:|---|---|
| 1 | −1.2 | −1.15 | 0.5×1.0 | 3.3V |
| 2 | −0.4 | −1.15 | 0.5×1.0 | TX（本板输出） |
| 3 | +0.4 | −1.15 | 0.5×1.0 | RX（本板输入） |
| 4 | +1.2 | −1.15 | 0.5×1.0 | GND |
| MP | ±2.5 | +0.8 | 1.2×1.7 | 机械焊脚，不是第5信号引脚 |

Courtyard为X±3.6、Y±2.15mm，故占位约7.2×4.3mm。0°时插入口朝+Y，1脚位于−X侧，原库含1脚三角形标记。旋转180°后插入口朝−Y。按实际顶视方向标注Pin1，不用线缆颜色推断引脚。

核查边界：标准 KiCad 封装本身注明来源 `http://www.jst-mfg.com/product/pdf/eng/eSUR.pdf`；该厂家PDF本次直接访问被代理拒绝，尚未取得可核对镜像。因此以上尺寸与编号是对安装的官方KiCad库实际几何的确认，不冒充本次已完成厂家图纸的独立核验。采购前需核实确切后缀、对配件和线序。

## GCT USB4105-GF-A

本机标准封装：

`Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal`

该封装描述明确列出 USB4105-GF-A、USB4105-GF-A-060/-120 等匹配版本，引用厂家 `https://gct.co/files/drawings/usb4105.pdf`。符号采用 `Connector:USB_C_Receptacle_USB2.0_16P`。

| 端子 | USB2.0连接 |
|---|---|
| A6、B6 | D+，尽靠插座汇合 |
| A7、B7 | D−，尽靠插座汇合 |
| A5 | CC1，独立5.1kΩ下拉到GND |
| B5 | CC2，另一独立5.1kΩ下拉到GND |
| A4、A9、B4、B9 | VBUS |
| A1、A12、B1、B12 | GND |
| A8、B8 | SBU1、SBU2，USB2.0 UART用途不连接 |
| S1 | 金属壳／机械脚，按本板地策略连接 |

0°时信号焊盘中心排在Y=−3.68mm，插入口朝+Y，封装的PCB Edge参考线Y=+3.675mm。若USB置板顶边、开口朝−Y，可旋转180°并按该参考线定位。Courtyard为X±5.32mm、Y=−4.76…+4.18mm，外壳F.Fab约8.94×7.35mm。

本次未取得GCT厂家图纸镜像，因此制造前仍需将实际采购型号与标准库及厂家机械图核对。完整焊盘尺寸、槽孔及坐标见 `footprint-pad-geometry.json`。

## USB与双层布局要点

- 两个CC各自独立5.1kΩ下拉；不把CC1、CC2短接，也不把本板作为USB PD升压请求设备。
- CH340C工作于USB全速，但用户要求的90Ω差分仍应按实际层叠校核。1.0mm双层板若参考地在背面，常见0.2～0.3mm窄线不能直接宣称90Ω。
- 以h约0.93～0.965mm、εr约4.2、35µm铜、0.15mm间距的简化微带模型估算，90Ω差分宽度约0.8mm量级；实际阻焊、频率、介质公差及铜厚影响结果，需要板厂给出确认值。
- 使用连续背面GND参考、短对称焊盘颈部、无90°拐角，避免分割地与长支路；颈部不属于均匀阻抗干线。
- 0.5A PTC是过流保护，不是USB枚举或精确输出限流器。本次尚未取得所选 `MF-MSMF050-2` 厂家资料，不在这里声明其精确电压／阻值／温度参数。
