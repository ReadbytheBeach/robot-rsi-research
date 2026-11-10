# 本工程使用的 KiCad 3D 模型

下载日期：2026-11-10。模型原样保存，没有缩放、改色或修改几何。

来源是 KiCad 官方 `kicad-packages3D`。旧 GitHub 仓库仅提供迁移说明，实际源代码托管在：

<https://gitlab.com/kicad/libraries/kicad-packages3D>

固定版本为 **9.0.2**，解引用提交：`52c1fa2ebb96a20df158c59a357b93343b5fa271`。文件路径沿用 `*.3dshapes/*.step` 结构，与本机 KiCad 9 标准封装的 model 属性对应。

## 已取得的模型

| 器件 | 模型 |
|---|---|
| J1 USB4105 系列 Type-C | `Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step` |
| U1 CH340C 封装 | `Package_SO.3dshapes/SOIC-16_3.9x9.9mm_P1.27mm.step` |
| U2 AP2112K 封装 | `Package_TO_SOT_SMD.3dshapes/SOT-23-5.step` |
| D1 USBLC6-2SC6 封装 | `Package_TO_SOT_SMD.3dshapes/SOT-23-6.step` |
| R1–R3 | `Resistor_SMD.3dshapes/R_0603_1608Metric.step` |
| C1–C5 | `Capacitor_SMD.3dshapes/C_0603_1608Metric.step` |
| D2 LED | `LED_SMD.3dshapes/LED_0603_1608Metric.step` |

SOIC、SOT 和无源器件是对应标准封装的模型，不是保证每个厂家具体料号的外观、颜色或最大尺寸都一致的独立机械认证。机械验收仍须对照实际采购图纸。

## 明确缺失的模型

- **J2**：`Connector_JST.3dshapes/JST_SUR_SM04B-SURS-TF_1x04-1MP_P0.80mm_Horizontal.step`。
- **F1**：`Fuse.3dshapes/Fuse_1812_4532Metric.step`。

这两个标准封装引用的 STEP 在 9.0.2 中不可取得，对应 WRL 以及本次查到的 master 提交 `afa6aab16f43a736cd062b8c853863e753653921` 上相同 STEP 路径也不可取得。未使用错误脚距的连接器或其他尺寸保险丝代替，也未自行虚构模型。

TP1–TP4 是裸铜测试焊盘，标准封装本身没有 3D 实体模型。

因此，3D 渲染中未出现 J2／F1 实体不能解释为它们未装配；请结合真实 PCB 封装、BOM 和装配图查看。

## 路径配置与许可

标准封装的模型原先使用 `${KICAD9_3DMODEL_DIR}`。本工程可将该变量设为本目录，或在 PCB 文件中改为 `${KIPRJMOD}/3dmodels/...` 的项目相对路径；应保留标准模型的原始位移与旋转参数。

KiCad 库许可为 **CC BY-SA 4.0，附 KiCad 电子设计及生成文件例外**，详见 [KiCad-LIBRARY-LICENSE.md](KiCad-LIBRARY-LICENSE.md)。各 STEP 文件中的原作者及许可声明均保留；各库目录中提供的 `CREDITS.md` 也已保留。

下载 URL、字节数、SHA-256、器件对应关系与缺失记录见 [manifest.json](manifest.json)。下载时验证了 STEP 文本首尾标识；未将此检查等同于完整机械装配碰撞验证。
