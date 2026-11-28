# 双球实验的历史模拟依赖与复跑

历史运行包包含本次训练实际引用的本地球拍接触模型、相机观测与时延、短赛道裁判、坡度和准备姿势、扭矩审计 C 源码、控制器与热启动权重，以及用于选取开发起点的必要记录。审计 C 模块会在本机编译。压缩包保留五个实验目录的同级关系。阅读数据、复核 CSV 或播放归档视频时无需安装模拟器。

## 放置文件

在本研究目录 `duck-play-pingpang-rearch` 的工作副本中执行。解压后，五个历史目录和本轮实验目录处于同一级。

```bash
export EXPERIMENT_DIR="$PWD/pingpong-dual16-mu-training-20261128"
export RUNTIME_ARCHIVE="$EXPERIMENT_DIR/runtime/historical-runtime.tar.gz"
tar -xzf "$RUNTIME_ARCHIVE" -C .
python3 -m venv .venv
. .venv/bin/activate
python -m pip install mujoco==3.10.0 numpy==2.4.1 onnxruntime==1.24.4 Pillow==12.2.0
export MICRODUCK_PYTHON="$PWD/.venv/bin/python"
```

物理回放需要 Linux、Python 3.12 和 C 编译器。重新训练 PPO 还需与机器匹配的 PyTorch 2.9.1；绘图使用 Matplotlib 3.10.9。渲染使用 EGL、FFmpeg 和 Noto Sans CJK 字体。包中的 `pingpong-turn-pit-20261128/run-local` 使用已激活的 Python，也支持上方的 `MICRODUCK_PYTHON` 指定路径。

## 取得实测版本的机器人与步态

下载 Pollen Robotics 的 MJCF 仓库时保留其相邻网格、配置和许可证。本轮使用提交 `ceca01706143d729305baa94cbd8ab990979e325` 下的 `src/mjlab_microduck/robot/microduck/scene.xml`。基础步态使用官方 v7 策略集提交 `6677ec007142bbaf05123a468f6ae58d13808786` 中的 `alpha_walking.onnx`。[MJCF 与网格来源](https://github.com/pollen-robotics/microduck_rl/tree/ceca01706143d729305baa94cbd8ab990979e325/src/mjlab_microduck/robot/microduck) · [固定版本步态文件](https://huggingface.co/pollen-robotics/microduck-policies/blob/6677ec007142bbaf05123a468f6ae58d13808786/alpha_walking.onnx)

```bash
export MICRODUCK_SCENE="$PWD/microduck_rl/src/mjlab_microduck/robot/microduck/scene.xml"
export MICRODUCK_POLICY="$PWD/alpha_walking.onnx"
sha256sum "$MICRODUCK_POLICY"
```

步态文件应得到 `e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c`。

## 重放同一次连续赛道

设置 `EXPERIMENT_DIR` 为解包后本轮训练目录的绝对路径，从已有动作重跑一个开发起点。

```bash
cd "$EXPERIMENT_DIR/low-route"
../../pingpong-turn-pit-20261128/run-local - <<'PY'
import extend
saved = extend.read(extend.d.HERE / "extension-result.json")
row = extend.replay(saved["best"])
print(row["last_both_m"], row["flat_1m"], row["finish_2p5"])
PY
```

在独立的目录解压后，用本机原测试引擎与指定上游资产验证，实验源码不得访问原先的实验目录。上面这条重跑得到 `1.2500622719477126 True False`。独立坡道过线策略重现 `1.0285482090628129` 米并停车 1 秒。正式软件验收的 17410001 号起点，固定高摩擦时中档步态为 `0.39554769292352454` 米，PPO 候选为 `0.30681977658903237` 米。其他系统或不同版本浮点库仍需单独核对。

包中的材料路径和机器人模型位置可重定位。原裁判源码与被检查的赛道源码保持原字节，运行包提供裁判实际核对的 SHA-256。历史开发筛选记录只保留本次所需的种子及排序字段。包覆盖本轮主要训练与回放入口；本次隔离验证覆盖上面四次回放，未从零重跑整批调参。上游网格、MJCF 与官方 ONNX 由读者按上述版本单独取得。
