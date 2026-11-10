# USB 差分阻抗计算依据

本设计采用 **90 Ω 差分阻抗目标**。最终名义叠层：顶层阻焊 0.010 mm、L1 铜 0.035 mm、FR-4 介质 0.910 mm、L2 铜 0.035 mm、底层阻焊 0.010 mm，合计 1.000 mm；实际成品公差由板厂确认。阻焊已计入厚度合计，但当前公式不计其电磁加载效应。介质相对介电常数暂取 4.2，不能把它视为任意 FR-4 板材的精确实测值。

## 计算方法

使用 KiCad 9 中的 Kirschning／Jansen 静态耦合微带模型，包含 Jansen／Atwater 的有限铜厚修正；单线参考由 Hammerstad／Jensen 型表达式计算。差分阻抗为：

$$Z_{diff}=2Z_{odd}$$

无穷大连续底层地平面、上方无盖板。模型不含阻焊、同层共面地、连接器／焊盘／缩颈、不规则铜形及实际材料损耗。

固定来源：KiCad `ce707d0a6c8736cbf4689560be4fee3d6a7f7f5e`：

- [c_microstrip.cpp](https://github.com/KiCad/kicad-source-mirror/blob/ce707d0a6c8736cbf4689560be4fee3d6a7f7f5e/pcb_calculator/transline/c_microstrip.cpp)，`delta_u_thickness`、`er_eff_static`、`Z0_even_odd`、`diff_impedance`。
- [microstrip.cpp](https://github.com/KiCad/kicad-source-mirror/blob/ce707d0a6c8736cbf4689560be4fee3d6a7f7f5e/pcb_calculator/transline/microstrip.cpp)，单线参考的填充系数及静态特性阻抗。

本地 [usb_impedance.py](../scripts/usb_impedance.py) 为对应公式的可审计 Python 实现，按照上游代码 GPL-2.0-or-later 许可提供；许可全文见 [GPL-2.0-or-later.txt](GPL-2.0-or-later.txt)。这仅适用于计算 helper 的代码，不对设计电路施加额外技术要求。

```bash
python3 scripts/usb_impedance.py --self-test --output analysis/usb-impedance.json
```

## 名义尺寸

| 参数 | 名义值 |
|---|---:|
| 信号到参考地介质厚度 h | 0.910 mm |
| 铜厚 t | 0.035 mm |
| 假定 εr | 4.2 |
| 差分线单线宽 w | 0.750 mm |
| 两线边缘间距 s | 0.150 mm |
| 两线中心距 | 0.900 mm |
| 模型估计 Zdiff | 89.859 Ω |
| 精确反解 90 Ω 的模型线宽 | 0.746177 mm |

实际布线采用可制造的 0.750 mm 线宽，不需要按计算器显示的小数精度制造。0.15 mm 是**边到边**间距，不能误作中心距。

这组数值是名义设计估计，不是实测或板厂场求解确认。完整数值和单参数敏感性见 [usb-impedance.json](../analysis/usb-impedance.json)。例如只改变 εr 为 3.8／4.6，模型分别约为 93.54／86.58 Ω，说明必须使用实际材料参数。

## 布线与制板要求

1. 主差分段用 L1，两根线一起走，保持 0.75／0.15 mm 名义宽间距；使用 45° 或圆弧转弯，避免直角拐角。
2. L2 在差分段下方保持连续地参考，不允许地平面切缝或其他网络穿过主要参考区域。
3. 上层邻近地铜会改变阻抗。计算按非共面微带模型；主差分段旁的上层铺铜应退让，建议尽可能保留约 3h（2.8 mm）侧向空间。若无法保证，应由板厂按实际共面几何重新求解，而不是照用本估计。
4. Type-C、ESD 与芯片焊盘存在不可避免的短缩颈和展开段，应尽量短且对称，不把其局部结构宣称为整段恒定 90 Ω。主干与局部过渡分别检查。
5. 制板图要求 **90 Ω differential，建议公差 ±10%**，板厂生产前应按实际 1.0 mm 叠层、Dk、铜厚和阻焊确认或调整线宽／间距。需要保证时应提供阻抗测试条及测试记录。
6. CH340 属于 USB Full-Speed，仍保留明确的 90 Ω 设计目标；不能因为只有 12 Mbps 就把阻抗要求从用户规格中删掉。

脚本自检覆盖宽线降低阻抗、间距增大提高阻抗、介电常数升高降低阻抗、整体几何缩放不改变静态阻抗，以及弱耦合趋向两倍单线阻抗等物理一致性检查。它不取代场求解器或实物测试。
