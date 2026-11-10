#!/usr/bin/env python3
"""Synthetic metric-world trajectory optimization: a small factor-graph lesson.

This is an original educational example, NOT Specialist's MEI fisheye solver.
It uses a calibrated pinhole/rectified camera, a stationary 0.12 m square tag,
and noisy *relative-pose* observations (not raw IMU or IMU preintegration).

Convention: W_T_C maps a camera-frame point into world coordinates:
    p_W = W_R_C @ p_C + W_t_C
The camera is optical x-right/y-down/z-forward. Positions are metres, rotation
vectors radians, image observations pixels. In this synthetic scene the tag is
horizontal at world z=0, so its normal is the world vertical. Specialist's real
world-frame construction additionally uses gravity: do not set an arbitrarily
tilted wall tag equal to a gravity-aligned world frame.

Only image corners, known tag geometry, and relative-pose measurements enter
the optimizer. Ground truth is used ONLY to synthesize measurements and report
errors, plus deliberately perturbing the initial guesses. This is not a real
initialization algorithm. No SE(3)/Sim(3) alignment, scale fit, or ground-truth
prior is applied. Reported trajectory errors refer to the camera origin.

Examples (run from repository root):
    python3 specialist-research/examples/world_trajectory.py --self-test
    python3 specialist-research/examples/world_trajectory.py \
        --plot /tmp/world-trajectory.svg --json /tmp/world-trajectory.json

Dependencies: numpy, scipy; matplotlib is needed only for --plot.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def make_transform(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    """Return A_T_B from A_R_B and A_t_B."""
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    return transform


def invert_transform(transform: np.ndarray) -> np.ndarray:
    """Invert a rigid transform without a general matrix inverse."""
    rotation = transform[:3, :3]
    return make_transform(rotation.T, -rotation.T @ transform[:3, 3])


def project_world_points(
    world_points: np.ndarray, world_from_camera: np.ndarray, intrinsics: np.ndarray
) -> np.ndarray:
    """Project W points into a calibrated pinhole camera; reject points behind it."""
    camera_from_world = invert_transform(world_from_camera)
    camera_points = world_points @ camera_from_world[:3, :3].T
    camera_points += camera_from_world[:3, 3]
    if np.any(camera_points[:, 2] <= 0):
        raise ValueError("A projected point has nonpositive optical depth")
    pixels_h = camera_points @ intrinsics.T
    return pixels_h[:, :2] / pixels_h[:, 2, None]


def unpack_poses(parameters: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rows are [world rotation vector (rad), world translation (m)]."""
    rows = parameters.reshape(-1, 6)
    return Rotation.from_rotvec(rows[:, :3]).as_matrix(), rows[:, 3:]


def pack_poses(rotations: np.ndarray, translations: np.ndarray) -> np.ndarray:
    return np.column_stack((Rotation.from_matrix(rotations).as_rotvec(), translations))


def gripper_poses_from_camera(
    parameters: np.ndarray, camera_from_gripper: np.ndarray
) -> np.ndarray:
    """Apply calibrated rigid extrinsics: W_T_G = W_T_C @ C_T_G."""
    rotations, translations = unpack_poses(parameters)
    return np.array([make_transform(r, t) @ camera_from_gripper
                     for r, t in zip(rotations, translations)])


def scene(seed: int = 7, frames: int = 14) -> dict:
    """Create observations; keep truth separate from measurements."""
    rng = np.random.default_rng(seed)
    time = np.linspace(0, 1, frames)
    translations = np.column_stack(
        (-0.09 + 0.18 * time, 0.025 * np.sin(2 * np.pi * time),
         0.65 + 0.035 * np.sin(np.pi * time))
    )
    # Camera above a horizontal marker, looking down toward the world z=0 plane.
    base_rotation = Rotation.from_euler("x", np.pi).as_matrix()
    small_rotations = Rotation.from_euler(
        "xyz", np.column_stack((0.025 * np.sin(2 * np.pi * time),
                                0.035 * np.cos(2 * np.pi * time),
                                0.06 * np.sin(np.pi * time)))
    ).as_matrix()
    rotations = small_rotations @ base_rotation
    corners = np.array([[-0.06, -0.06, 0], [0.06, -0.06, 0],
                        [0.06, 0.06, 0], [-0.06, 0.06, 0]])
    intrinsics = np.array([[700., 0., 360.], [0., 700., 360.], [0., 0., 1.]])
    clean_pixels = np.array([
        project_world_points(corners, make_transform(r, t), intrinsics)
        for r, t in zip(rotations, translations)
    ])
    pixels = clean_pixels + rng.normal(0, 0.7, clean_pixels.shape)
    pixels[frames // 2, 0] += [22., -18.]  # One deliberately bad corner observation.

    # C_i_T_C_(i+1) = inverse(W_T_C_i) @ W_T_C_(i+1).
    relative_rotations = np.swapaxes(rotations[:-1], 1, 2) @ rotations[1:]
    relative_translations = np.einsum(
        "nij,nj->ni", np.swapaxes(rotations[:-1], 1, 2),
        translations[1:] - translations[:-1]
    )
    relative_rotations = relative_rotations @ Rotation.from_rotvec(
        rng.normal(0, 0.008, (frames - 1, 3))
    ).as_matrix()
    relative_translations += rng.normal(0, 0.004, relative_translations.shape)

    initial_rotations = Rotation.from_rotvec(
        rng.normal(0, 0.045, (frames, 3))
    ).as_matrix() @ rotations
    initial_translations = translations + rng.normal(0, 0.028, translations.shape)
    return {
        "truth": (rotations, translations),
        "initial": pack_poses(initial_rotations, initial_translations),
        "corners": corners, "K": intrinsics,
        "pixels": pixels, "clean_pixels": clean_pixels,
        "relative_R": relative_rotations, "relative_t": relative_translations,
    }


def predicted_pixels(parameters: np.ndarray, data: dict) -> np.ndarray:
    rotations, translations = unpack_poses(parameters)
    points_c = np.einsum("nji,nkj->nki", rotations,
                         data["corners"][None, :, :] - translations[:, None, :])
    # A hinge penalty in residuals discourages any trial stepping behind camera.
    # Clipping here merely keeps numerical trial evaluations finite.
    depth = np.maximum(points_c[:, :, 2], 0.02)
    homogeneous = points_c @ data["K"].T
    return homogeneous[:, :, :2] / depth[:, :, None]


def residuals(parameters: np.ndarray, data: dict) -> np.ndarray:
    """Concatenate normalized image and relative-pose factor residuals."""
    rotations, translations = unpack_poses(parameters)
    image_error = (predicted_pixels(parameters, data) - data["pixels"]) / 0.7
    estimated_relative_r = np.swapaxes(rotations[:-1], 1, 2) @ rotations[1:]
    rotation_error = Rotation.from_matrix(
        np.swapaxes(data["relative_R"], 1, 2) @ estimated_relative_r
    ).as_rotvec() / 0.008
    estimated_relative_t = np.einsum(
        "nij,nj->ni", np.swapaxes(rotations[:-1], 1, 2),
        translations[1:] - translations[:-1]
    )
    translation_error = (estimated_relative_t - data["relative_t"]) / 0.004
    points_c = np.einsum("nji,nkj->nki", rotations,
                         data["corners"][None, :, :] - translations[:, None, :])
    depth_penalty = np.minimum(points_c[:, :, 2] - 0.02, 0) / 0.001
    return np.concatenate((image_error.ravel(), rotation_error.ravel(),
                           translation_error.ravel(), depth_penalty.ravel()))


def errors(parameters: np.ndarray, data: dict) -> dict:
    rotations, translations = unpack_poses(parameters)
    true_r, true_t = data["truth"]
    position_error = np.linalg.norm(translations - true_t, axis=1)
    angle_error = Rotation.from_matrix(
        np.swapaxes(true_r, 1, 2) @ rotations
    ).magnitude()
    pixel_error = predicted_pixels(parameters, data) - data["clean_pixels"]
    return {
        "translation_rmse_mm": float(np.sqrt(np.mean(position_error**2)) * 1000),
        "rotation_rmse_deg": float(np.rad2deg(np.sqrt(np.mean(angle_error**2)))),
        "clean_corner_reprojection_rmse_px": float(np.sqrt(np.mean(pixel_error**2))),
    }


def solve(data: dict):
    return least_squares(residuals, data["initial"].ravel(), args=(data,),
                         loss="soft_l1", f_scale=2.0, max_nfev=180,
                         ftol=1e-8, xtol=1e-8, gtol=1e-8)


def geometry_self_test() -> None:
    """Catch inversion, frame-composition, and optical-axis sign mistakes."""
    w_from_c = make_transform(Rotation.from_euler("xyz", [.2, -.1, .3]).as_matrix(),
                              np.array([.3, -.2, .7]))
    c_from_g = make_transform(Rotation.from_euler("z", .4).as_matrix(),
                              np.array([.03, 0., .08]))
    # A camera rotated +90 degrees around world z: its local +x points world +y.
    known_w_from_c = make_transform(Rotation.from_euler("z", np.pi / 2).as_matrix(),
                                    np.array([1., 2., 3.]))
    known_c_from_g = make_transform(np.eye(3), np.array([.1, 0., 0.]))
    camera_parameters = pack_poses(known_w_from_c[None, :3, :3],
                                    known_w_from_c[None, :3, 3])
    gripper_pose = gripper_poses_from_camera(camera_parameters, known_c_from_g)[0]
    np.testing.assert_allclose(gripper_pose[:3, 3], [1., 2.1, 3.], atol=1e-12)
    np.testing.assert_allclose(invert_transform(w_from_c) @ w_from_c,
                               np.eye(4), atol=1e-12)
    k = np.array([[500., 0., 320.], [0., 500., 240.], [0., 0., 1.]])
    np.testing.assert_allclose(project_world_points(np.array([[0., 0., 1.]]),
                                                    np.eye(4), k), [[320., 240.]])
    try:
        project_world_points(np.array([[0., 0., -1.]]), np.eye(4), k)
    except ValueError:
        pass
    else:
        raise AssertionError("Negative optical depth must be rejected")


def plot_result(data: dict, optimized: np.ndarray, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    initial_t = unpack_poses(data["initial"])[1]
    optimized_t = unpack_poses(optimized)[1]
    true_t = data["truth"][1]
    frame = np.arange(len(true_t))
    fig, axes = plt.subplots(1, 3, figsize=(12.3, 3.6), constrained_layout=True)
    for t, name, style in [(true_t, "Ground truth", "-k"),
                            (initial_t, "Initial", ":o"),
                            (optimized_t, "Optimized", "-o")]:
        axes[0].plot(t[:, 0], t[:, 1], style, label=name, markersize=3)
        axes[1].plot(frame, t[:, 2], style, label=name, markersize=3)
    axes[0].plot(*np.vstack((data["corners"], data["corners"][0]))[:, :2].T,
                 "--", color="gray", label="Fixed 0.12 m tag")
    axes[0].set(xlabel="World x (m)", ylabel="World y (m)", title="Metric world trajectory")
    axes[0].axis("equal")
    axes[0].legend(fontsize=7)
    axes[1].set(xlabel="Frame", ylabel="World z (m)", title="Depth is part of the estimate")
    for t, name in [(initial_t, "Initial"), (optimized_t, "Optimized")]:
        axes[2].plot(frame, np.linalg.norm(t-true_t, axis=1)*1000, "-o",
                     label=name, markersize=3)
    axes[2].set(xlabel="Frame", ylabel="Translation error (mm)",
                title="Synthetic errors; no GT alignment")
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.25)
    fig.suptitle("Teaching example only: pinhole camera + fixed tag + relative poses", fontsize=11)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, metadata={"Creator": "world_trajectory.py"})
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--plot", type=Path, help="Write SVG/PNG synthetic result plot")
    parser.add_argument("--json", "--output-json", dest="json", type=Path,
                        help="Write the same metrics printed to stdout")
    args = parser.parse_args()
    geometry_self_test()
    data = scene(seed=args.seed)
    initial_r, initial_t = unpack_poses(data["initial"])
    scalar_projections = np.array([
        project_world_points(data["corners"], make_transform(r, t), data["K"])
        for r, t in zip(initial_r, initial_t)
    ])
    np.testing.assert_allclose(predicted_pixels(data["initial"], data),
                               scalar_projections, atol=1e-10)
    result = solve(data)
    if not result.success:
        raise RuntimeError(f"Optimization did not converge: {result.message}")
    before, after = errors(data["initial"], data), errors(result.x, data)
    if args.self_test:
        for key in before:
            if not after[key] < before[key] * 0.5:
                raise AssertionError(f"Synthetic optimization did not improve {key}")
        rotations, translations = unpack_poses(result.x)
        for r, t in zip(rotations, translations):
            project_world_points(data["corners"], make_transform(r, t), data["K"])
    report = {
        "synthetic_only": True, "seed": args.seed,
        "camera_model": "calibrated pinhole; NOT raw Specialist MEI/fisheye",
        "motion_factor": "noisy relative pose; NOT raw IMU integration",
        "world_scale": "fixed 0.12 m tag; no truth alignment or scale fitting",
        "trajectory_frame": "camera origin; W_T_G = W_T_C @ C_T_G for gripper",
        "initialization": "synthetic truth perturbed; NOT a real pose initializer",
        "self_test": "passed" if args.self_test else "not requested",
        "initial": before, "optimized": after,
        "function_evaluations": result.nfev,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")
    if args.plot:
        plot_result(data, result.x, args.plot)


if __name__ == "__main__":
    main()
