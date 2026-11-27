"""Render a reproducible MicroDuck balance rollout and show its measured error."""
import argparse
from pathlib import Path

import mujoco
import numpy as np

from microduck_env import CONTROL_DT, HORIZON, MicroDuckEnv


def main():
    parser = argparse.ArgumentParser(description="运行 MuJoCo 稳球回合，可选导出 MP4。")
    parser.add_argument("--upstream", type=Path, required=True, help="官方 microduck_rl 检出目录")
    parser.add_argument("--seed", type=int, default=30021, help="回合随机种子")
    parser.add_argument("--difficulty", type=float, default=1.0, help="难度，0 到 1")
    parser.add_argument("--controller", choices=["flat", "pd", "ppo"], default="pd")
    parser.add_argument("--model", type=Path, help="PPO 模型 ZIP，使用 ppo 时必填")
    parser.add_argument("--video", type=Path, help="MP4 输出路径")
    args = parser.parse_args()
    if args.controller == "ppo" and args.model is None:
        parser.error("--controller ppo 需要 --model")
    env = MicroDuckEnv(args.upstream, args.difficulty, flat=args.controller == "flat")
    action = np.zeros(2, dtype=np.float32)
    policy = None
    if args.model and args.controller == "ppo":
        from stable_baselines3 import PPO
        policy = PPO.load(args.model, device="cpu")
    observation, info = env.reset(seed=args.seed)
    if args.video:
        import imageio.v2 as imageio
        from PIL import Image, ImageDraw

        args.video.parent.mkdir(parents=True, exist_ok=True)
        camera = mujoco.MjvCamera()
        camera.lookat[:] = [0.038, 0, 0.14]
        camera.distance = 0.44
        camera.azimuth = 143
        camera.elevation = -20
        renderer = mujoco.Renderer(env.model, height=384, width=512)
        writer = imageio.get_writer(args.video, fps=round(1 / (2 * CONTROL_DT)), codec="libx264")
    errors = []
    try:
        for i in range(HORIZON):
            if args.video and i % 2 == 0:
                renderer.update_scene(env.data, camera=camera)
                renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False
                frame = Image.fromarray(renderer.render())
                draw = ImageDraw.Draw(frame)
                draw.rounded_rectangle((14, 14, 226, 73), radius=8, fill=(13, 23, 36))
                label = {"flat": "LEVEL PADDLE", "pd": "PD", "ppo": "PD + PPO"}[args.controller]
                draw.text((26, 23), f"MicroDuck  /  {label}", fill=(220, 234, 246), font_size=15)
                draw.text((26, 45), f"{info['time_s']:5.2f} s   |   {info['error_mm']:5.1f} mm", fill=(147, 211, 243), font_size=15)
                writer.append_data(np.asarray(frame))
            if policy is not None:
                action = policy.predict(observation, deterministic=True)[0]
            observation, _, terminated, truncated, info = env.step(action)
            errors.append(info["error_mm"])
            if terminated or truncated:
                break
    finally:
        if args.video:
            writer.close()
            renderer.close()
        env.close()
    outcome = "成功" if truncated else "掉球"
    print(f"{outcome}，用时 {info['time_s']:.2f} 秒，球心偏移 P95 {np.percentile(errors, 95):.2f} mm。")


if __name__ == "__main__":
    main()
