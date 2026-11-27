"""训练 MicroDuck 的双轴乒乓球平衡策略。"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    from microduck_env import MicroDuckEnv


@dataclass
class Evaluation:
    successes: int
    mean_reward: float
    median_error_mm: float
    p95_error_mm: float
    median_time_s: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="用 PPO 微调 MicroDuck 的 PD 稳球控制，比较两种控制在同一组留出种子上的表现。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--upstream", type=Path, required=True, help="已检出的 microduck_rl 仓库路径"
    )
    parser.add_argument(
        "--steps", "--timesteps", type=int, default=100_000, help="训练总步数"
    )
    parser.add_argument("--envs", type=int, default=4, help="训练环境数量")
    parser.add_argument(
        "--rollout-steps",
        type=int,
        default=256,
        help="每轮更新前，每个环境收集的步数",
    )
    parser.add_argument(
        "--difficulty", type=float, default=1.0, help="环境难度，范围为 0 到 1"
    )
    parser.add_argument("--seed", type=int, default=17, help="训练随机种子")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models/microduck_ppo.zip"),
        help="模型保存路径",
    )
    parser.add_argument(
        "--eval-episodes", type=int, default=30, help="留出种子评估回合数"
    )
    parser.add_argument(
        "--eval-seed",
        type=int,
        help="首个评估随机种子，默认在训练环境的种子范围上方另加 10000",
    )
    args = parser.parse_args()
    if not args.upstream.is_dir():
        parser.error("--upstream 必须指向已检出的 microduck_rl 仓库目录")
    if args.steps < 1 or args.envs < 1 or args.rollout_steps < 2:
        parser.error("--steps 和 --envs 至少为 1，--rollout-steps 至少为 2")
    if not 0.0 <= args.difficulty <= 1.0:
        parser.error("--difficulty 必须在 0 到 1 之间")
    if args.seed < 0 or args.seed + args.envs > 2**32:
        parser.error("训练环境的随机种子必须在 0 到 2³²−1 之间")
    if args.eval_episodes < 1:
        parser.error("--eval-episodes 至少为 1")
    if args.eval_seed is None:
        args.eval_seed = args.seed + args.envs + 10_000
    if args.eval_seed < 0:
        parser.error("--eval-seed 必须为非负整数")
    if (
        args.eval_seed < args.seed + args.envs
        and args.seed < args.eval_seed + args.eval_episodes
    ):
        parser.error("评估种子区间必须与训练环境的初始种子区间分开")
    return args


def evaluate(
    choose_action: Callable[[np.ndarray], np.ndarray],
    env: MicroDuckEnv,
    episodes: int,
    seed: int,
) -> Evaluation:
    import numpy as np

    successes = 0
    total_reward = 0.0
    errors_mm = []
    times_s = []
    for episode_seed in range(seed, seed + episodes):
        observation, _ = env.reset(seed=episode_seed)
        terminated = truncated = False
        while not (terminated or truncated):
            action = choose_action(observation)
            observation, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            errors_mm.append(info["error_mm"])
        successes += int(truncated and not terminated)
        times_s.append(info["time_s"])
    return Evaluation(
        successes=successes,
        mean_reward=total_reward / episodes,
        median_error_mm=float(np.median(errors_mm)),
        p95_error_mm=float(np.percentile(errors_mm, 95)),
        median_time_s=float(np.median(times_s)),
    )


def print_evaluation(label: str, result: Evaluation, episodes: int) -> None:
    print(
        f"{label}，稳球成功 {result.successes}/{episodes} "
        f"({result.successes / episodes:.1%})，"
        f"径向误差中位数 {result.median_error_mm:.2f} mm，"
        f"P95 {result.p95_error_mm:.2f} mm，"
        f"稳球时长中位数 {result.median_time_s:.2f} s，"
        f"平均回合奖励 {result.mean_reward:.3f}。"
    )


def main() -> None:
    args = parse_args()
    import numpy as np
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from microduck_env import MicroDuckEnv

    torch.set_num_threads(1)

    def make_env() -> MicroDuckEnv:
        return MicroDuckEnv(upstream=args.upstream, difficulty=args.difficulty)

    training_env = DummyVecEnv([make_env] * args.envs)
    try:
        policy = PPO(
            "MlpPolicy",
            training_env,
            n_steps=args.rollout_steps,
            batch_size=min(64, args.rollout_steps * args.envs),
            policy_kwargs={"log_std_init": -1.0},
            seed=args.seed,
            device="cpu",
            verbose=1,
        )
        policy.learn(total_timesteps=args.steps)
        model_path = args.model if args.model.suffix else args.model.with_suffix(".zip")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        policy.save(model_path)
        print(f"已训练 {policy.num_timesteps:,} 步。模型已保存至 {model_path}")
    finally:
        training_env.close()

    eval_env = make_env()
    try:
        ppo_result = evaluate(
            lambda obs: policy.predict(obs, deterministic=True)[0],
            eval_env,
            args.eval_episodes,
            args.eval_seed,
        )
        pd_action = np.zeros(eval_env.action_space.shape, dtype=np.float32)
        pd_result = evaluate(
            lambda _: pd_action, eval_env, args.eval_episodes, args.eval_seed
        )
    finally:
        eval_env.close()
    print(
        f"难度 {args.difficulty:g} 的留出种子评估 "
        f"({args.eval_seed}–{args.eval_seed + args.eval_episodes - 1})。"
    )
    print_evaluation("PD", pd_result, args.eval_episodes)
    print_evaluation("PD + PPO", ppo_result, args.eval_episodes)


if __name__ == "__main__":
    main()
