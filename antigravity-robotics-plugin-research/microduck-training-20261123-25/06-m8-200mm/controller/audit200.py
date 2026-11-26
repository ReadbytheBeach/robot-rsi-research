"""Contact, position and timing witnesses for genuine floor gathering from 200 mm."""
import numpy as np

# Separation from the floor must be sustained, so a single solver sample is not a lift.
AIR_HEIGHT = .001
AIR_DURATION = .020
SYNC_LIMIT = .020
EXIT_X = .55


def floor_forces(audit):
    contacts = audit.d.contact
    pairs = contacts.geom
    if not len(pairs):return np.zeros(2)
    valid = (contacts.dist <= 0) & (contacts.efc_address >= 0)
    floor = audit.floor
    owners = audit.owner
    values = np.zeros(2)
    for side in (0,1):
        other = owners[pairs[:,1-side]]
        ids = np.flatnonzero(valid & (pairs[:,side] == floor) & (other >= 0))
        if len(ids):
            # Elliptic cones store the normal contact force at the first constraint address.
            import mujoco
            force=np.zeros(6)
            for i in ids:
                mujoco.mj_contactForce(audit.m,audit.d,int(i),force)
                values[other[i]]+=max(0.,float(force[0]))
    return values


class GapWitness:
    def __init__(self,ctx):
        self.problem=None
        self.initial_xy=ctx.d.xpos[ctx.audit.nut,:2].copy()
        self.settled_xy=None
        self.settled_distance=None
        self.floor_streak=np.zeros(2)
        self.air_streak=np.zeros(2)
        self.maximum_preair=np.zeros(2)
        self.maximum_preheight=np.zeros(2)
        self.first_lift=[None,None]
        self.close_cycles=0
        self.last_open=True
        self.exit_t=None
        self.closest=.20
        self.floor=np.zeros(2)
        self.cargo_touched=False
        self.pregrasp_bilateral_streak=np.zeros(2)
        self.initial_forbidden_contacts=[]
        for c in ctx.d.contact:
            if c.dist>0:continue
            a,b=c.geom
            i,j=ctx.audit.owner[a],ctx.audit.owner[b]
            if i<0 and j<0:continue
            other=b if i>=0 else a
            if other!=ctx.audit.floor and (i!=j or i<0):
                self.initial_forbidden_contacts.append([ctx.m.geom(a).name,ctx.m.geom(b).name])
        if self.initial_forbidden_contacts:
            self.fault('initial_model_overlap',ctx.time)
        self.rows=[] if ctx.trace is not None else None

    def fault(self,reason,t):
        if self.problem is None:self.problem=dict(reason=reason,t=t)

    def confirm_settled(self,ctx):
        self.settled_xy=ctx.d.xpos[ctx.audit.nut,:2].copy()
        self.settled_distance=float(np.linalg.norm(self.settled_xy[1]-self.settled_xy[0]))
        if min(self.floor_streak)<.05-1e-7:
            self.fault('initial_floor_not_settled',ctx.time)
        if not ctx.diagnostic and abs(self.settled_distance-.20)>.001:
            self.fault('initial_200mm_not_met',ctx.time)

    def observe(self,ctx,stage):
        t=ctx.time;dt=ctx.m.opt.timestep;a=ctx.audit
        pre=stage not in ('pick','cross','place','dock_plan','realign_basket','brake','finish')
        xy=ctx.d.xpos[a.nut,:2];distance=float(np.linalg.norm(xy[1]-xy[0]))
        if pre or stage=='pick':
            self.floor=floor_forces(a)
            self.floor_streak=np.where(self.floor>1e-5,self.floor_streak+dt,0.)
            self.air_streak=np.where((self.floor<=1e-5)&(a.z>AIR_HEIGHT),self.air_streak+dt,0.)
            if stage!='settle':self.closest=min(self.closest,distance)
            if pre and stage!='settle':
                self.maximum_preair=np.maximum(self.maximum_preair,self.air_streak)
                self.maximum_preheight=np.maximum(self.maximum_preheight,a.z)
                self.pregrasp_bilateral_streak=np.where((a.mouth_force>1e-5).all(axis=1),self.pregrasp_bilateral_streak+dt,0.)
                if max(self.pregrasp_bilateral_streak)>=AIR_DURATION-1e-9:
                    self.fault('preparatory_bilateral_bite',t)
                if max(self.air_streak)>=AIR_DURATION-1e-9:
                    self.fault('nut_lift_before_single_bite',t)
            if stage=='pick':
                opening=float(ctx.d.ctrl[14])
                if self.last_open and opening<np.deg2rad(15):
                    self.close_cycles+=1;self.last_open=False
                elif opening>np.deg2rad(25):self.last_open=True
                for i in (0,1):
                    if self.first_lift[i] is None and self.air_streak[i]>=AIR_DURATION-1e-9:
                        self.first_lift[i]=float(t-self.air_streak[i]+dt)
        if self.exit_t is None and ctx.xy[0]>EXIT_X:
            self.exit_t=t
            if ctx.dual.qualified is None:self.fault('exit_before_dual_hold',t)
        if self.rows is not None:
            self.rows.append([t,distance,*(self.floor if pre or stage=='pick' else (np.nan,np.nan))])

    def lift_difference(self):
        if any(x is None for x in self.first_lift):return float('inf')
        return abs(self.first_lift[0]-self.first_lift[1])

    def report(self):
        return dict(nominal_distance_m=.2,settled_distance_m=self.settled_distance,
                    settled_xy=None if self.settled_xy is None else self.settled_xy.tolist(),
                    closest_predeparture_m=self.closest,max_prep_air_s=self.maximum_preair.tolist(),
                    max_prep_bottom_height_m=self.maximum_preheight.tolist(),first_sustained_lift_t=self.first_lift,
                    first_lift_difference_s=None if any(x is None for x in self.first_lift) else self.lift_difference(),
                    closed_bites=self.close_cycles,exit_line_x_m=EXIT_X,exit_at=self.exit_t,
                    initial_forbidden_contacts=self.initial_forbidden_contacts,problem=self.problem)
