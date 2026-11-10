# 首板检查与串口回环

以下为实物验证计划，尚未执行。

1. 按 BOM 检查型号、方向、焊点及 Type-C 两排数据／电源焊盘，尤其不要将 CH340G 当作内置时钟的 CH340C 使用。
2. 不插 USB，检查 VBUS、3.3V 对地是否短路，确认 JST 的 1 脚方向。
3. 通过带限流／电流监测的 USB 供电首次上电，不先接外部设备；测 J2 pin1 对 pin4，目标为 3.3V，并检查 CH340C 的 VCC16、V3 pin4。
4. 安装对应 WCH 驱动或使用系统驱动，确认枚举为一个串口；Type-C 正反插都要试验。
5. 将 J2 pin2 TX 与 pin3 RX 短接，使用 115200、8N1、关闭硬件流控发送测试数据；接收字节应完全一致，再逐步测试目标波特率。
6. 移除短接，连接目标设备时本板 TX 接目标 RX、本板 RX 接目标 TX，GND 共地。目标若已有电源，先确认是否应连接 J2 的 3.3V 输出，避免两个电源互相灌电。
   目标独立供电而本板 USB 断开时，应停止驱动本板 RX；当前没有专用的 UART 断电隔离。
7. 对 3.3V 输出逐步加载至本设计的 50mA 外供预算，记录输出电压、纹波、启动波形、USB 总电流和 LDO 温升。
8. 检查主机休眠／恢复与拔插行为。外部负载没有独立的 USB 挂起电流门控，需要单独评估总取电。
9. 由板厂或测试机构提供所订叠层的阻抗 coupon／TDR 结果；不能把软件计算值当作实测 90Ω。

需要串口回环自动化时，可使用下列独立示例，需先安装 pyserial、将 `PORT` 改为实际端口并接好 TX/RX 短接：

```python
import serial

PORT = "/dev/ttyUSB0"  # Windows 示例：COM5
payload = bytes(range(256)) * 4
with serial.Serial(PORT, 115200, timeout=2, rtscts=False, dsrdtr=False) as port:
    port.reset_input_buffer()
    port.write(payload)
    port.flush()
    received = port.read(len(payload))
    assert received == payload, (len(received), len(payload))
print("UART loopback passed")
```

上述示例只说明验证方法；本次没有真实串口设备，因此没有将其报告为已通过测试。
