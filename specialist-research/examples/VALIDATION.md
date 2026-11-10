# 教学示例验证记录

日期：2026-11-10（新加坡时间）。工作目录：`specialist-research`。

这两个脚本是独立编写的教学示例，未复制官方求解器实现。全部测试使用合成数据，不代表原始 `.insv`、真实麦克风、相机、IMU 或机器人的评测。

## 环境与执行

在新建的 `/tmp/specialist-demo-venv` 内安装 [requirements-demo.txt](../requirements-demo.txt)，验证 Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、Matplotlib 3.10.8；`python -m pip check` 通过。依赖清单包含本次实际使用的传递依赖版本。

复现命令：

```bash
python3 -m venv /tmp/specialist-demo-venv
/tmp/specialist-demo-venv/bin/python -m pip install -r requirements-demo.txt
export MPLCONFIGDIR=/tmp/specialist-matplotlib
export XDG_CACHE_HOME=/tmp/specialist-cache

/tmp/specialist-demo-venv/bin/python examples/audio_align.py \
  --self-test --plot assets/audio-alignment-demo.png

/tmp/specialist-demo-venv/bin/python examples/world_trajectory.py \
  --self-test --plot assets/world-trajectory-demo.png \
  --output-json examples/world-trajectory-result.json
```

图可另存为 `.svg` 供矢量导出：将 `--plot` 参数的扩展名改成 `.svg`。正文使用 PNG，便于直接显示。

## 音频同步

已执行四项自检：

| 检查 | 预设偏移 | 估计偏移 | 结果 |
|---|---:|---:|---|
| 负偏移，不同采样率 | -0.613 s | -0.6130015224 s | 通过 |
| 正偏移，PCM16、增益差与噪声 | +0.827 s | +0.8269892347 s | 通过 |
| 静音 | 不可估计 | 拒绝 | 通过 |
| 周期性歧义音频 | 不应强行接受 | 拒绝 | 通过 |

两个偏移用例均实际写入并读取临时 WAV，检查了时间映射及两侧裁剪起点。通过条件是恢复误差小于 3 ms，不将合成数据中更小的数值误差宣称为实机精度。

另外从独立生成的 44.1／48 kHz WAV 经命令行入口测试：预设 +0.250 s，估计 +0.2499999517 s，两侧裁剪映射正确；静音输入确认返回退出码 2。这检验了普通文件参数入口，不仅是脚本内部自检路径。

约定为 `t_right = t_left + offset_seconds`，右侧时间转到左侧时减去偏移。脚本输出为 JSON；拒绝同步时返回非零退出码 2，原因写入标准错误。

与官方的主要区别：教学实现使用重叠窗口归一化相关，并加入静音／包络变化、最小相关、最小重叠和边界峰检查。1.3 的峰值比与其他阈值都是启发式，未在真实录制上完成统计校准。

本脚本不处理 `.insv` 元数据、音视频 PTS 差、时钟漂移或声音传播时延，不直接重编码视频。

## 世界轨迹

固定 seed 7 的合成场景含 14 个相机位姿、已知 0.12 m 平面标签、0.7 px 图像噪声、一处异常角点和有噪相对位姿约束。初值由合成真值加扰动生成，不是实际视频初始化方法。

| 指标 | 初始 | 优化后 |
|---|---:|---:|
| 相机位置 RMSE | 52.5320046 mm | 11.7360547 mm |
| 相机旋转 RMSE | 4.4963512° | 0.9870276° |
| 相对无噪声角点的像素分量 RMSE | 35.1385200 px | 0.4946951 px |

独立环境中优化收敛，三个误差均满足至少降低一半的自检条件。精确输出保存在 [world-trajectory-result.json](world-trajectory-result.json)。

同时检查了：

- 刚体逆变换、相机光轴投影和负深度拒绝；
- 相机转动后工具偏移的正确变换方向；
- 批量投影与逐帧投影的一致性；
- 优化后标签仍位于相机前方。

评估不进行事后 SE(3)／Sim(3) 真值拟合或尺度校正。真值不进入优化残差，只用于合成观测、生成初值和最后评价。相对位姿输入不是原始 IMU，不包含 IMU 偏置、预积分或完整鱼眼模型。

上述结果说明该受控场景中的代码行为正确，不证明官方硬件能达到相同结果，也不代表示例优于其他求解器。
