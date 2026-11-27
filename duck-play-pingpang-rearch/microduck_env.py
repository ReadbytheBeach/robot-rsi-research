"""Fixed-base MicroDuck mouth-mounted ping-pong balance in MuJoCo."""
from collections import deque
from pathlib import Path
import xml.etree.ElementTree as ET

import gymnasium as gym
import mujoco
import numpy as np


UPSTREAM_REVISION = "0daab160d3fb1c2cbaba16a4a19052f36709dd9e"
BALL_RADIUS = 0.020
BALL_MASS = 0.0027
PADDLE_RADIUS = 0.055
PADDLE_HALF_THICKNESS = 0.002
CONTROL_AXES = ("head_pitch", "head_roll")
PHYSICS_DT = 0.002
SUBSTEPS = 10
CONTROL_DT = PHYSICS_DT * SUBSTEPS
ACTION_LIMIT = np.deg2rad(10)
HORIZON = round(10.0 / CONTROL_DT)
HEAD_KP = 3.2
HEAD_KV = 0.075


def _numbers(values):
    return " ".join(f"{value:.12g}" for value in values)


def _paddle_xml(upstream: Path) -> tuple[str, np.ndarray]:
    robot_folder = Path(upstream) / "src/mjlab_microduck/robot/microduck"
    scene = robot_folder / "scene.xml"
    if not scene.is_file():
        raise FileNotFoundError(
            f"{scene} is missing. Use the microduck_rl checkout at {UPSTREAM_REVISION}."
        )
    native = mujoco.MjModel.from_xml_path(str(scene))
    stand = native.key("STAND")
    pose = mujoco.MjData(native)
    mujoco.mj_resetDataKeyframe(native, pose, stand.id)
    mujoco.mj_forward(native, pose)

    jaw = pose.body("jaw_soft")
    mouth = pose.site("mouth_tip")
    jaw_rotation = jaw.xmat.reshape(3, 3)
    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, np.ascontiguousarray(jaw_rotation.T).ravel())

    # Make the top plane horizontal in the official STAND pose, with +X forward.
    center_offset = np.array([0.066, 0, 0.008])
    attachment = jaw_rotation.T @ (mouth.xpos + center_offset - jaw.xpos)

    root = ET.parse(robot_folder / "robot_groundcontact.xml").getroot()
    root.find("compiler").set("meshdir", str((robot_folder / "assets").resolve()))
    ET.SubElement(root, "option", timestep=str(PHYSICS_DT), integrator="implicitfast")
    world = root.find("worldbody")
    trunk = world.find("body[@name='trunk_base']")
    trunk.remove(trunk.find("freejoint"))
    for geom in world.iter("geom"):
        geom.set("contype", "0")
        geom.set("conaffinity", "0")
    for actuator in root.find("actuator"):
        active = actuator.get("name") in CONTROL_AXES
        actuator.set("kp", str(HEAD_KP if active else 12.0))
        actuator.set("kv", str(HEAD_KV if active else 0.15))

    paddle = ET.SubElement(
        trunk.find(".//body[@name='jaw_soft']"), "body",
        name="paddle", pos=_numbers(attachment), quat=_numbers(quat),
    )
    # Explicit payload prevents the inherited visual geoms from changing inertia.
    ET.SubElement(
        paddle, "inertial", pos="-0.008 0 0", mass="0.018",
        diaginertia="0.000012 0.000018 0.000029",
    )
    ET.SubElement(
        paddle, "geom", name="paddle_face", type="cylinder",
        size=_numbers([PADDLE_RADIUS, PADDLE_HALF_THICKNESS]),
        rgba="0.09 0.36 0.50 1", contype="1", conaffinity="0",
        friction="0.32 0.003 0.00002", condim="6",
        solref="0.006 0.68", solimp="0.94 0.99 0.001",
    )
    ET.SubElement(
        paddle, "geom", name="paddle_handle", type="box",
        pos="-0.055 0 -0.005", size="0.025 0.008 0.0035",
        rgba="0.82 0.70 0.48 1", contype="0", conaffinity="0",
    )
    ET.SubElement(
        paddle, "site", name="paddle_center", type="sphere",
        pos=_numbers([0, 0, PADDLE_HALF_THICKNESS]), size="0.002",
        rgba="0.7 0.92 1 0.65",
    )
    ET.SubElement(world, "light", pos="0.3 -0.6 1", dir="-0.3 0.6 -1", directional="true")
    ET.SubElement(world, "light", pos="-0.4 0.6 0.6", dir="0.4 -0.6 -0.6", diffuse="0.45 0.50 0.58")
    ET.SubElement(
        world, "geom", name="floor", type="plane", size="1 1 0.05",
        rgba="0.16 0.18 0.21 1", contype="1", conaffinity="0",
    )
    ball_pos = mouth.xpos + center_offset + np.array([0, 0, PADDLE_HALF_THICKNESS + BALL_RADIUS])
    ball = ET.SubElement(world, "body", name="ball", pos=_numbers(ball_pos))
    ET.SubElement(ball, "freejoint", name="ball_free")
    inertia = 2 * BALL_MASS * BALL_RADIUS**2 / 3  # Thin spherical shell.
    ET.SubElement(ball, "inertial", pos="0 0 0", mass=str(BALL_MASS), diaginertia=_numbers([inertia] * 3))
    ET.SubElement(
        ball, "geom", name="ball_geom", type="sphere", size=str(BALL_RADIUS),
        rgba="1 0.47 0.08 1", contype="0", conaffinity="1",
        friction="0.32 0.003 0.00002", condim="6",
        solref="0.006 0.68", solimp="0.94 0.99 0.001",
    )
    return ET.tostring(root, encoding="unicode"), stand.ctrl.copy()


class MicroDuckEnv(gym.Env):
    """Two PPO residuals on top of a ball position/velocity PD controller."""

    metadata = {"render_modes": []}

    def __init__(self, upstream: Path, difficulty: float = 1.0, flat: bool = False):
        super().__init__()
        if not 0 <= difficulty <= 1:
            raise ValueError("difficulty must be between 0 and 1")
        self.difficulty = difficulty
        self.flat = flat
        self.model_xml, self.home_ctrl = _paddle_xml(upstream)
        self.model = mujoco.MjModel.from_xml_string(self.model_xml)
        self.data = mujoco.MjData(self.model)
        self.action_space = gym.spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, shape=(14,), dtype=np.float32)

        self.site = self.data.site("paddle_center")
        self.site_id = self.model.site("paddle_center").id
        self.ball_body_id = self.model.body("ball").id
        self.ball_dof = self.model.joint("ball_free").dofadr.item()
        self.ball_qpos = self.model.joint("ball_free").qposadr.item()
        self.face_geom = self.model.geom("paddle_face").id
        self.ball_geom = self.model.geom("ball_geom").id
        self.head_act = np.array([self.model.actuator(name).id for name in CONTROL_AXES])
        self.head_qpos = np.array([self.model.joint(name).qposadr.item() for name in CONTROL_AXES])
        self.head_dof = np.array([self.model.joint(name).dofadr.item() for name in CONTROL_AXES])
        self.act_dof = self.model.jnt_dofadr[self.model.actuator_trnid[:, 0]]
        self.act_qpos = self.model.jnt_qposadr[self.model.actuator_trnid[:, 0]]
        self.contact_friction = self.model.geom_friction[[self.face_geom, self.ball_geom]].copy()

        self._reset_neutral()
        self.tilt_jacobian = self._tilt_jacobian()
        singular_values = np.linalg.svd(self.tilt_jacobian, compute_uv=False)
        if singular_values[-1] < 0.5:
            raise RuntimeError(f"Head cannot tilt paddle in both axes: {singular_values}")
        self.tilt_inverse = np.linalg.inv(self.tilt_jacobian)

    def _reset_neutral(self):
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self.act_qpos] = self.home_ctrl
        mujoco.mj_forward(self.model, self.data)
        # Compensate static head and payload torque at the level pose.
        self.level_ctrl = self.home_ctrl.copy()
        self.level_ctrl += self.data.qfrc_bias[self.act_dof] / self.model.actuator_gainprm[:, 0]
        self.data.ctrl[:] = self.level_ctrl

    def _tilt_jacobian(self):
        derivative = np.empty((2, 2))
        for index, qpos in enumerate(self.head_qpos):
            self.data.qpos[qpos] += 0.0001
            mujoco.mj_kinematics(self.model, self.data)
            derivative[:, index] = self.site.xmat.reshape(3, 3)[:2, 2] / 0.0001
            self.data.qpos[qpos] -= 0.0001
        mujoco.mj_forward(self.model, self.data)
        return derivative

    def ball_state(self):
        rotation = self.site.xmat.reshape(3, 3)
        arm = self.data.qpos[self.ball_qpos:self.ball_qpos + 3] - self.site.xpos
        paddle_velocity = np.empty(6)
        mujoco.mj_objectVelocity(
            self.model, self.data, mujoco.mjtObj.mjOBJ_SITE, self.site_id, paddle_velocity, 0,
        )
        ball_velocity = self.data.qvel[self.ball_dof:self.ball_dof + 3]
        relative_velocity = ball_velocity - paddle_velocity[3:] - np.cross(paddle_velocity[:3], arm)
        return rotation.T @ arm, rotation.T @ relative_velocity

    def _measurement(self, position, velocity):
        return np.concatenate((position[:2], velocity[:2])) + self.np_random.normal(
            0, self.difficulty * np.array([0.0005, 0.0005, 0.004, 0.004]),
        )

    def _observation(self):
        ball = self.measurements[0] / np.array([PADDLE_RADIUS] * 2 + [0.2] * 2)
        head = (self.data.qpos[self.head_qpos] - self.home_ctrl[self.head_act]) / ACTION_LIMIT
        angular_velocity = self.data.qvel[self.head_dof] / 3.0
        normal_xy = self.site.xmat.reshape(3, 3)[:2, 2] / ACTION_LIMIT
        return np.concatenate((
            ball, head, angular_velocity, normal_xy, self.command / ACTION_LIMIT,
            self.previous_action,
        )).astype(np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        d = self.difficulty
        rng = self.np_random
        stiffness = HEAD_KP * (1 + rng.uniform(-0.18, 0.18, size=2) * d)
        damping = HEAD_KV * (1 + rng.uniform(-0.18, 0.18, size=2) * d)
        self.model.actuator_gainprm[self.head_act, 0] = stiffness
        self.model.actuator_biasprm[self.head_act, 1] = -stiffness
        self.model.actuator_biasprm[self.head_act, 2] = -damping
        self.model.geom_friction[[self.face_geom, self.ball_geom]] = self.contact_friction * (
            1 + rng.uniform(-0.30, 0.30) * d
        )
        self._reset_neutral()
        yaw = rng.uniform(-np.pi, np.pi)
        offset = rng.uniform(0.006, 0.014 + 0.018 * d) * np.array([np.cos(yaw), np.sin(yaw)])
        launch = rng.uniform(-0.015 - 0.044 * d, 0.015 + 0.044 * d, size=2)
        rotation = self.site.xmat.reshape(3, 3)
        self.data.qpos[self.ball_qpos:self.ball_qpos + 3] = (
            self.site.xpos + rotation @ np.r_[offset, BALL_RADIUS + 0.0002]
        )
        self.data.qvel[self.ball_dof:self.ball_dof + 3] = rotation @ np.r_[launch, 0.0]
        spin = np.cross([0, 0, 1], np.r_[launch, 0]) / BALL_RADIUS
        self.data.qvel[self.ball_dof + 3:self.ball_dof + 6] = rotation @ spin
        mujoco.mj_forward(self.model, self.data)

        self.elapsed_steps = 0
        self.air_steps = 0
        self.command = np.zeros(2)
        self.previous_action = np.zeros(2)
        observation_delay = int(rng.integers(0, round(2 * d) + 1))
        control_delay = int(rng.integers(0, round(2 * d) + 1))
        first_measurement = self._measurement(*self.ball_state())
        self.measurements = deque([first_measurement] * (observation_delay + 1), maxlen=observation_delay + 1)
        self.commands = deque([self.command] * (control_delay + 1), maxlen=control_delay + 1)
        self.kick_steps = (rng.integers(80, 180), rng.integers(255, 400))
        kick_angles = rng.uniform(-np.pi, np.pi, size=2)
        self.kicks = (0.018 + 0.09 * d) * np.stack((np.cos(kick_angles), np.sin(kick_angles)), axis=1)
        return self._observation(), {"error_mm": float(np.linalg.norm(offset) * 1000), "time_s": 0.0}

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=float), -1, 1)
        measurement = self.measurements[0]
        # A positive paddle normal in +X or +Y accelerates the ball that way.
        normal_target = -3.6 * measurement[:2] - 0.78 * measurement[2:]
        target = self.tilt_inverse @ normal_target + 0.05 * action
        target = np.zeros(2) if self.flat else np.clip(target, -ACTION_LIMIT, ACTION_LIMIT)
        self.commands.append(target)
        max_change = np.deg2rad(115) * CONTROL_DT
        self.command += np.clip(self.commands[0] - self.command, -max_change, max_change)
        self.data.ctrl[self.head_act] = self.level_ctrl[self.head_act] + self.command

        if self.elapsed_steps in self.kick_steps:
            kick = self.kicks[self.kick_steps.index(self.elapsed_steps)]
            self.data.qvel[self.ball_dof:self.ball_dof + 3] += self.site.xmat.reshape(3, 3) @ np.r_[kick, 0]
        mujoco.mj_step(self.model, self.data, nstep=SUBSTEPS)
        mujoco.mj_forward(self.model, self.data)
        self.elapsed_steps += 1
        position, velocity = self.ball_state()
        self.measurements.append(self._measurement(position, velocity))

        paddle_contact = any(
            {self.face_geom, self.ball_geom} == {contact.geom1, contact.geom2}
            for contact in self.data.contact
        )
        self.air_steps = 0 if paddle_contact else self.air_steps + 1
        radial_error = np.linalg.norm(position[:2])
        # Crossing the face boundary while supported at the edge is tolerated by 2 mm.
        failed = bool(
            radial_error > PADDLE_RADIUS + 0.002
            or position[2] < BALL_RADIUS - 0.006
            or self.air_steps > 9
            or not np.all(np.isfinite(position))
        )
        completed = self.elapsed_steps >= HORIZON and not failed
        action_change = action - self.previous_action
        self.previous_action = action
        reward = 1.0 - 0.25 * (radial_error / PADDLE_RADIUS)
        reward -= 0.75 * (radial_error / PADDLE_RADIUS)**2
        reward -= 0.003 * np.dot(action, action)
        reward -= 0.08 * np.linalg.norm(velocity[:2]) / 0.2
        reward -= 0.015 * np.dot(action_change, action_change)
        if failed:
            reward = -5.0
        info = {
            "error_mm": float(radial_error * 1000), "time_s": self.elapsed_steps * CONTROL_DT,
            "paddle_contact": paddle_contact,
        }
        return self._observation(), float(reward), failed, completed, info
