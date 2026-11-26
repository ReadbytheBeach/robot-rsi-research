"""Continuous MuJoCo episode for ground gathering followed by one dual grasp."""
import importlib.util
import json
from pathlib import Path
import sys

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import course

REF = ROOT / 'double-trip/validation-v2-48531500'
OPEN = course.OPEN
HOME = course.HOME


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dual = module_at('m8_two_nut_witness', ROOT / 'double-trip/audit.py')


def settings():
    return json.loads((REF / 'settings.json').read_text())


def parameters():
    return json.loads((REF / 'parameters.json').read_text())


def placement(seed, config):
    rng = np.random.default_rng(np.random.SeedSequence([seed, 0x200]))
    ordinal = config.get('within_cell', (seed - config.get('first_seed', 0)) // 6)
    sector = int(ordinal % 4)
    angle = float(np.deg2rad(sector * 45 + rng.uniform(-22.5, 22.5)))
    center = np.array([.19, -.035]) + rng.uniform(-.015, .015, 2)
    axis = np.array([np.cos(angle), np.sin(angle)])
    if ordinal // 4 % 2:
        axis = -axis
    xy = np.array([center - .10 * axis, center + .10 * axis])
    return xy, rng.uniform(-np.pi/6, np.pi/6, 2), sector


class GroundContext:
    """The trial owns one physical data, delay queue, contact audit, and walking policies."""
    def __init__(self, job, *, diagnostic_xy=None):
        seed, label, delay, params, config, trace = job
        self.job = job
        self.seed, self.label, self.delay = int(seed), label, int(delay)
        self.params, self.config, self.trace = params, config, trace
        self.scene, self.xml = course.build_scene(label, params['x'], 'together', .2, asset_profile='official-bom')
        self.m = mujoco.MjModel.from_xml_string(self.xml)
        self.standard = int(config.get('substeps', 4))
        self.m.opt.timestep = .02/self.standard
        self.d = mujoco.MjData(self.m)
        self.root = int(self.m.joint('trunk_base_freejoint').qposadr[0])
        self.trunk = self.m.body('trunk_base').id
        self.q = np.array([self.m.joint(k).qposadr[0] for k in course.POLICY_JOINTS])
        self.v = np.array([self.m.joint(k).dofadr[0] for k in course.POLICY_JOINTS])
        self.d.qpos[self.root:self.root+7] = [0,0,.125,1,0,0,0]
        self.d.qpos[self.q] = HOME
        self.d.qpos[self.m.joint('mouth').qposadr[0]] = OPEN
        xy, yaws, self.sector = placement(seed, config)
        self.diagnostic = diagnostic_xy is not None
        if self.diagnostic:
            xy = np.array(diagnostic_xy, dtype=float)
        self.initial = []
        for name, point, angle in zip(('nut_a','nut_b'),xy,yaws):
            q = self.m.joint(name+'_free').qposadr[0]
            self.d.qpos[q:q+2] = point
            self.d.qpos[q+3:q+7] = [np.cos(angle/2),0,0,np.sin(angle/2)]
            self.initial.append(self.d.qpos[q:q+7].copy().tolist())
        self.prev = np.r_[HOME, OPEN]
        self.d.ctrl[:] = self.prev
        mujoco.mj_forward(self.m,self.d)
        self.audit = course.Audit(self.m,self.d,logging=trace is not None,accelerated=True)
        self.dual = dual.Witness(self.audit)
        from audit200 import GapWitness
        self.gap = GapWitness(self)
        self.walker = course.Walker(session=course.world.net('alpha_walking'))
        self.stand = course.Walker(session=course.world.net('velstand'))
        self.stage = 'settle'
        self.reason = None
        self.routes = []
        self.released = []
        self.final_drift = 0.
        self.probes = 0
        self.details = {}

    @property
    def time(self):
        return float(self.d.time)

    @property
    def yaw(self):
        return course.forward_yaw(self.d.qpos[self.root+3:self.root+7])

    @property
    def xy(self):
        return self.d.qpos[self.root:self.root+2]

    def walk(self, command, policy=None):
        p = self.walker if policy is None else policy
        return p.command(self.d.sensor('imu_ang_vel').data, -self.d.xmat[self.trunk,6:9],
                         self.d.qpos[self.q], self.d.qvel[self.v], command)

    def walk_step(self, command, jaw=OPEN, stage='gather'):
        return self.step(np.r_[self.walk(command), jaw], stage)

    def pick_outputs(self, params, history=None):
        return course.NutPickController(self.m,self.d,params,history)

    def step(self, action, stage='gather', carry=(), fine=False, score_basket=False):
        if self.reason: return False
        if self.time >= 240 - 1e-6:
            self.reason = 'timeout'
            return False
        action = np.asarray(action, dtype=float)
        if action.shape != (15,) or not np.isfinite(action).all():
            raise ValueError('Expected 15 finite actuator targets')
        self.stage = stage
        self.d.ctrl[:] = self.prev if self.delay else action
        self.prev = action.copy()
        n = max(8,self.standard) if fine else self.standard
        self.m.opt.timestep = .02/n
        self.audit.check_basket = score_basket
        for _ in range(n):
            mujoco.mj_step(self.m,self.d)
            self.audit.sample(stage,carry)
            self.dual.observe(self.audit,stage,carry)
            self.gap.observe(self,stage)
            if self.audit.problem or self.gap.problem:
                self.reason = (self.audit.problem or self.gap.problem)['reason']
                return False
        return True

    def settle(self):
        for _ in range(15):
            if not self.step(np.r_[HOME, OPEN], 'settle'):
                return False
        self.gap.confirm_settled(self)
        if self.gap.problem:
            self.reason = self.gap.problem['reason']
        return not self.reason

    def event(self, name, carry=()):
        self.audit.events.append(dict(event=name, t=round(self.time,5), carrying=list(carry)))


def play_pick(ctx, entry):
    p = entry['params']
    control = ctx.pick_outputs(p,entry.get('history'))
    ctx.event('pick')
    for _ in range(round(ctx.config.get('pick_s',5.08)/.02)):
        action = control.step(ctx.d)
        if not ctx.step(action,'pick'): return None
    if min(ctx.audit.held)<2.-1e-7:
        ctx.reason = 'pickup_failed'
        return None
    if ctx.gap.lift_difference() > .02000001:
        ctx.reason = 'asynchronous_lift'
        return None
    ctx.walker.obs[0,34:48] = control.obs[0,34:48]
    ctx.walker.previous_raw = action[:14].copy()
    return action


def deliver(ctx, pick_end):
    cfg, d, scene = ctx.config, ctx.d, ctx.scene
    ids = [0,1]
    station = np.asarray(scene['far_station']) + np.asarray(cfg.get('far_offset',[0.,0.]))
    nav = course.Navigator(scene, station=station,tolerance=cfg.get('far_tol',.045),
        settle_ticks=3,yaw_tol=cfg.get('far_yaw_tol',.06),micro=.17)
    at = ctx.time
    drive = course.CorridorDrive('cross',ids,scene,cfg,cfg['carry'],pick_end[:14],
        ctx.q,ctx.v,ctx.trunk,ctx.root,ctx.delay,at)
    pacer=course.TurnPacer()
    advance=course.CarryAdvance(pick_end[:14])
    ctx.event('cross',ids)
    if ctx.trace:
        # Freeze integration state for diagnostic turn branches, without altering the live plant.
        size=mujoco.mj_stateSize(ctx.m,mujoco.mjtState.mjSTATE_INTEGRATION)
        state=np.empty(size);mujoco.mj_getState(ctx.m,d,state,mujoco.mjtState.mjSTATE_INTEGRATION)
        path=Path(ctx.trace).with_name('before-cross.npz');path.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(path,state=state,prev=ctx.prev,walker_obs=ctx.walker.obs,
                            walker_raw=ctx.walker.previous_raw,pick_end=pick_end)
    if cfg.get('loaded_pivot',True):
        original_command=nav.command
        def command(xy,yaw,t):
            if nav.stage=='turn' and abs(course.forward_yaw([np.cos(yaw/2),0,0,np.sin(yaw/2)]))>.20:
                options=cfg.get('pivot_options',{})
                # The motion policy needs translational drive to initiate alternating foot support.
                sign=-np.sign(yaw)
                return (options.get('forward',.34),sign*options.get('side',.09),sign*options.get('yaw',1.8))
            return original_command(xy,yaw,t)
        nav.command=command
    while not nav.done:
        if ctx.time-at>cfg.get('navigation_timeout',90.):
            ctx.reason='navigation_timeout';return
        action=drive.step(d,nav,ctx.walker,pacer,advance,None,ctx.audit.mouth_force)
        if not ctx.step(action,'cross',ids): return
    ctx.routes.append(dict(leg='cross',items=ids,gates=nav.events,t=ctx.time,
                           xy=ctx.xy.tolist(),yaw=ctx.yaw))
    ctx.event('place',ids)
    from functools import partial
    auditor=partial(course.Audit,accelerated=True)
    rim=np.asarray(scene['basket_xy'])
    loaded=action.copy()
    for attempt in range(int(cfg.get('dock_retries',0))+1):
        plan=course.plan_approach(ctx.m,d,ctx.walker,ctx.stand,ctx.prev,ctx.delay,
                                 ids,rim,auditor,cfg)
        ctx.probes+=1
        if plan is not None: break
        if attempt==cfg.get('dock_retries',0):
            ctx.reason='no_safe_dock_trajectory';return
        at=ctx.time
        origin=ctx.xy.copy()
        retreat=True
        while ctx.time-at<6:
            if retreat and (ctx.xy[0]<origin[0]-.10 or ctx.time-at>2):retreat=False
            destination=np.array([scene['far_station'][0]-.052,.012*(-1)**(attempt+1)])
            if not retreat and np.linalg.norm(destination-ctx.xy)<.043 and abs(ctx.yaw)<.19:break
            cmd=(-.29,0.,np.clip(-2.*ctx.yaw,-.3,.3)) if retreat else np.clip(np.r_[4*(destination-ctx.xy),-2.*ctx.yaw],[-.18,-.22,-.35],[.24,.22,.35])
            target=ctx.walk(cmd);target[5:9]=loaded[5:9]
            if not ctx.step(np.r_[target,loaded[-1]],'realign_basket',ids):return
    ctx.event('dock_plan',ids)
    for i,action in enumerate(plan[0]):
        prelude=i<plan[4]
        if not ctx.step(action,'dock_plan',ids if prelude else [],fine=not prelude,score_basket=not prelude):return
    ctx.walker.obs[:]=plan[1];ctx.walker.previous_raw=plan[2].copy()
    if not all(ctx.audit.basket.seconds[j]>.10 for j in ids):
        ctx.reason='dock_observed_support_failed';return
    ctx.released=ids
    for phase, limit in [('brake',.86),('finish',cfg.get('finish_wait',10.))]:
        ctx.event(phase);origin=ctx.xy.copy();at=ctx.time
        ctx.stand.obs[0,34:48]=ctx.walker.obs[0,34:48]
        ctx.stand.previous_raw=ctx.walker.previous_raw.copy()
        while ctx.time-at < limit-1e-6:
            age=ctx.time-at
            move=ctx.walk((0,0,0));still=ctx.walk((0,0,0),ctx.stand)
            blend=min(1,age/.50)
            if not ctx.step(np.r_[(1-blend)*move+blend*still, OPEN],phase,fine=True,score_basket=True):return
            if phase=='finish':
                ctx.final_drift=max(ctx.final_drift,float(np.linalg.norm(ctx.xy-origin)))
                if ctx.time-at>=2.2-1e-7 and ctx.audit.basket.both_stable and ctx.final_drift<=.05 and plan[3][0]-ctx.xy[0]>=.07:
                    ctx.reason='success';return
    ctx.reason='finish_failed'
