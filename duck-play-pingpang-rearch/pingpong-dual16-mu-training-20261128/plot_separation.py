"""Plot the actual final 1.2 s of the release-aligned 1.250 m trial in paddle coordinates."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle
import mujoco
import numpy as np

from material import HERE, short_track


def main():
    font = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({"font.family": font_manager.FontProperties(fname=font).get_name(), "font.size": 11})
    meta = json.loads((HERE / "low-route/extension-low.json").read_text())
    model = short_track.render_model("combined", meta["track_origin_x_m"])
    data = mujoco.MjData(model)
    ball_ids = [model.geom(n).id for n in ("ball_geom", "ball_geom_b")]
    site = model.site("paddle_center").id
    with np.load(HERE / "low-route/extension-low.npz") as trace:
        keep = trace["t"] >= meta["seconds"] - 1.20001
        times, poses = trace["t"][keep], trace["qpos"][keep]
    xy = []
    for pose in poses:
        data.qpos[:] = pose
        mujoco.mj_kinematics(model, data)
        local = (data.geom_xpos[ball_ids] - data.site_xpos[site]) @ data.site_xmat[site].reshape(3, 3)
        xy.append(local[:, :2] * 1000)
    xy = np.asarray(xy)
    span = np.linalg.norm(xy[:, 1] - xy[:, 0], axis=1)
    assert len(times) == 61 and span[0] < 32 and span[-1] > 110
    midpoint = len(times) // 2
    fig, (face, chart) = plt.subplots(1, 2, figsize=(9.6, 4.1), gridspec_kw={"width_ratios": [1, 1.5]}, layout="constrained")
    face.add_patch(Circle((0, 0), 55, fc="#f5f6f2", ec="#495a64", lw=1.2))
    for i, color in enumerate(("#0a746c", "#ab513a")):
        points = xy[:, i]
        face.plot(*points.T, color=color, lw=2, label=f"球 {'AB'[i]}")
        face.scatter(*points[0], facecolor="white", edgecolor=color, s=37, zorder=3)
        face.scatter(*points[-1], color=color, s=37, zorder=3)
    face.set(xlim=(-64, 64), ylim=(-64, 64), aspect="equal", title="球心在拍面上的投影", xlabel="拍面坐标（毫米）")
    face.set_yticks([-55, 0, 55])
    face.set_xticks([-55, 0, 55])
    face.legend(loc="upper right", fontsize=9, frameon=False)
    chart.axhline(110, lw=1.2, ls="--", color="#ab513a")
    chart.text(times[0], 112.5, "平拍直径 110 毫米", color="#983d2b")
    chart.plot(times, span, color="#254a67", lw=2.2)
    for idx in (0, midpoint, -1):
        chart.scatter(times[idx], span[idx], color="#254a67", s=26)
        offset = (-19, 7) if idx == -1 else (3, 8)
        chart.annotate(f"{span[idx]:.1f}", (times[idx],span[idx]), xytext=offset, textcoords="offset points")
    chart.set(xlabel="从放球开始（秒）", ylabel="球心投影间距（毫米）", title="失球前的最后 1.2 秒", ylim=(20, 128))
    chart.grid(axis="y", alpha=.18)
    for axis in (face, chart):
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle("低摩擦主赛道 1.250 米回放  ·  空心为起点，实心为终点", fontsize=14)
    fig.savefig(HERE / "media/separation-before-loss.png", dpi=155)
    plt.close(fig)


if __name__ == "__main__":
    main()
