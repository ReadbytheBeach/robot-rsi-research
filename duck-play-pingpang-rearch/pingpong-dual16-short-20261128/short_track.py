"""Straight 2.5 m and isolated one-metre tests for the unchanged MicroDuck double-ball plant.

The walking, sensor, contact, impulse, torque and stop loops are the hash-checked frozen course.
The adapter supplies a different physical heightfield and records gates strictly after its loss check.
"""
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch
import argparse
import hashlib
import inspect
import json
import math
import sys

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'pingpong-turn-pit-20261128'
FROZEN = OLD / 'frozen/double16-stand'
PREVIOUS = HERE.parent / 'pingpong-dual16-antigravity-20261128'
sys.path.insert(0, str(FROZEN))
import course
import locomotion as loc
import path_geom

DEGREES = 1.0
GRADIENT = math.tan(math.radians(DEGREES))
TRACKS = ('combined', 'flat', 'incline')
BASE = json.loads((PREVIOUS/'sealed/extension/candidate.json').read_text())['params']


def height(track, x):
    """Surface height at horizontal course coordinate x, metres. Incline spans the release footprint."""
    if track == 'combined':
        return GRADIENT * np.clip(np.asarray(x)-1, 0., 1.)
    if track == 'incline':
        return GRADIENT * np.clip(x, -.48, 1.50)
    if track == 'flat':
        return np.zeros_like(x, dtype=float)
    raise ValueError(track)


def write_profile(m, track):
    floor = m.geom('floor').id
    h = int(m.geom_dataid[floor]); a = int(m.hfield_adr[h])
    rows, cols = int(m.hfield_nrow[h]), int(m.hfield_ncol[h])
    radius_x, _, span, _ = m.hfield_size[h]
    x0, _, z0 = m.geom_pos[floor]
    xx = np.linspace(x0-radius_x, x0+radius_x, cols)
    elevations = (height(track, xx) - z0) / span
    assert np.all((elevations >= 0) & (elevations <= 1))
    m.hfield_data[a:a+rows*cols].reshape(rows, cols)[:] = elevations
    # Visible course marks have no collision affinity. Keep their location consistent with the scorer.
    stops = (0., .5, 1., 1.5, 2., 2.5) if track == 'combined' else (0., .25, .5, .75, 1.)
    for i in range(11):
        for suffix, y in [('l', .56), ('r', -.56)]:
            g = m.geom(f'marker_{i}_{suffix}').id
            if i >= len(stops):
                m.geom_rgba[g,3] = 0.
                continue
            x = stops[i]
            m.geom_pos[g] = [x, y, float(height(track, x))+.001]
            m.geom_quat[g] = [1.,0.,0.,0.]
            m.geom_rgba[g, :3] = (.09,.68,.46) if x == stops[-1] else (.90,.67,.12)
    return m


@lru_cache(maxsize=8)
def _template(track, terrain, mass, count, diameter):
    if not terrain or mass != 40 or count != 2 or diameter != 16:
        raise ValueError((terrain, mass, count, diameter))
    import copy
    return write_profile(copy.copy(course.template(terrain,mass,count,diameter)), track)


def render_model(track='combined', origin_x=0., model_hook=None):
    """Copy the static model for rendering an .npz with its recorded physical release origin."""
    import copy
    m = copy.copy(_template(track, True, 40., 2, 16.))
    move_marks(m, origin_x)
    if track == 'combined': m.geom_pos[m.geom('floor').id,0] += origin_x
    if model_hook: model_hook(m)
    return m


def move_marks(m, origin_x):
    for i in range(11):
        for side in ('l','r'):
            m.geom_pos[m.geom(f'marker_{i}_{side}').id,0] += origin_x


class Meter:
    def __init__(self, track, model_hook):
        self.track, self.model_hook = track, model_hook
        self.origin = 0.
        self.valid_peak = self.both_peak = self.last_both = self.slope_m = 0.
        self.gates = {}
        self.valid = True

    def setup(self, model):
        if self.model_hook: self.model_hook(model)

    def release(self, model, data, start):
        self.origin = float(start[0]); self.start_y = float(start[1])
        if self.track == 'combined':
            # Translate the terrain before the balls are released, while under the stationary
            # robot it is a horizontal plane. All future feature boundaries follow actual origin.
            model.geom_pos[model.geom('floor').id,0] += self.origin
        if self.track == 'incline' and not (-.3 < self.origin < .30):
            raise ValueError(f'Footprint would leave the uniform part of the 1° slope at {self.origin}')
        move_marks(model, self.origin)
        mujoco.mj_forward(model, data)

    def ground(self, x, y=None):
        return float(height(self.track, x-self.origin if self.track == 'combined' else x))

    def observe(self, t, distance, fail, on_face, audit, controller):
        if fail or audit.contact_stats[0] > 0:
            self.valid = False
        if not self.valid: return
        self.valid_peak = max(self.valid_peak, float(distance))
        if not on_face: return
        assert len(controller.last_contacts)==2 and all(controller.last_contacts)
        self.last_both = float(distance)
        self.both_peak = max(self.both_peak, self.last_both)
        if self.track == 'combined':
            self.slope_m = max(self.slope_m, min(1., self.last_both-1.))
            gates = [('flat_1m',1.),('slope_1m',2.),('cross_2p5',2.5)]
        else:
            if self.track=='incline':self.slope_m=max(self.slope_m,min(1., self.last_both))
            gates = [('flat_1m' if self.track == 'flat' else 'slope_1m', 1.)]
        for name, threshold in gates:
            if self.last_both < threshold or name in self.gates: continue
            # A terminal gate on the mixed course requires a witnessed first metre.
            if self.track=='combined' and name=='slope_1m' and 'flat_1m' not in self.gates: continue
            self.gates[name] = dict(t=float(t), progress_m=self.last_both, x_m=self.origin+self.last_both,
                                    both_contact=True,radii_mm=(1000*np.asarray(controller.last_radii)).tolist())


@lru_cache(maxsize=1)
def _compiled():
    manifest=json.loads((FROZEN/'manifest.json').read_text())
    assert hashlib.sha256((FROZEN/'course.py').read_bytes()).hexdigest()==manifest['files']['course.py']
    source=inspect.getsource(course.run)
    substitutions=[
        ('copy.copy(template(', 'copy.copy(_short_template('),
        (';d=mujoco.MjData(m)', ';_meter.setup(m);d=mujoco.MjData(m)'),
        ('    bc.reset(seed,difficulty=', '    _meter.release(m,d,start)\n    bc.reset(seed,difficulty='),
        ('        pace.observe(step*DT,progress)', '        _meter.observe(step*DT,progress,fail,on,audit,bc)\n        pace.observe(step*DT,progress)')]
    for before,after in substitutions:
        if source.count(before)!=1:raise RuntimeError(f'Frozen course instrumentation mismatch: {before}')
        source=source.replace(before, after)
    return compile(source, str(FROZEN/'course.py'), 'exec')


def run(track, seed, params=None, *, trace=None, timeout=45., model_hook=None):
    if track not in TRACKS:raise ValueError(track)
    meter=Meter(track,model_hook)
    ns={**course.__dict__, '_meter':meter,
        '_short_template':lambda terrain,mass,n,diam:_template(track,terrain,mass,n,diam)}
    exec(_compiled(),ns)
    target=2.5 if track=='combined' else 1.
    def projection(x,y):return float(x),float(y)
    with ExitStack() as stack:
        stack.enter_context(patch.multiple(path_geom, project=projection,tangent=lambda s:0.,center=lambda s:(s,0.),ground_height=meter.ground))
        stack.enter_context(patch.multiple(loc, project=projection,tangent=lambda s:0.,center=lambda s:(s,0.),ground_height=meter.ground))
        result=ns['run']('route',int(seed),BASE if params is None else params,length=target,trace=trace,timeout=timeout)
    result.update(track=track, track_origin_x_m=meter.origin, valid_peak_m=meter.valid_peak,
                  both_peak_m=meter.both_peak,last_both_m=meter.last_both,slope_progress_m=meter.slope_m,
                  flat_1m='flat_1m' in meter.gates,slope_1m='slope_1m' in meter.gates,
                  finish_2p5=bool(track=='combined' and result['success'] and 'cross_2p5' in meter.gates),
                  gates=meter.gates)
    if trace is not None:
        metadata=Path(trace).with_suffix('.json');old=json.loads(metadata.read_text());course.save(metadata,{**old,**result})
    return result


def verify_geometry():
    probes={}
    for track in TRACKS:
        for offset in (-.025,0.,.025):
            m=render_model(track,offset);d=mujoco.MjData(m);mujoco.mj_forward(m,d)
            f=m.geom('floor').id
            def ray(x):
                p=np.array([x, .1173, .45]); v=np.array([0.,0.,-1.]); l=mujoco.mj_rayHfield(m,d,f,p,v)
                assert l>=0;return p[2]-l
            ys=[]
            for probe in (-.23, .001, .499, .999,1.001,1.499,1.999,2.001,2.499):
                x=offset+probe; actual=ray(x); expected=float(height(track, probe if track=='combined' else x))
                assert abs(actual-expected)<2e-8,(track,probe,actual,expected)
                ys.append([probe,actual])
            rise=lambda x:math.degrees(math.atan((ray(offset+x+.001)-ray(offset+x-.001))/.002))
            angles=[rise(el) for el in [.5,1.5,2.25]] if track!='incline' else [rise(el) for el in [-.2,.2,.9]]
            assert np.allclose(angles,{'combined':[0.,1.,0.],'incline':[1.,1.,1.],'flat':[0.,0.,0.]}[track],atol=.0001)
            probes[f'{track}/{offset}']=dict(probes_relative_x_m_and_world_height_m=ys,measured_angles_deg=angles)
    return {'angle_deg':DEGREES,'rise_per_horizontal_m':GRADIENT,'profiles':probes,
            'gates':'Horizontal projected displacement from physical release. Mixed track boundaries are aligned to that release before loading. Credit at first 50 Hz both-contact state at or beyond each boundary while all previous 500 Hz hard checks remain clean. No negative tolerance. Endpoint requires 1 s stop and both-contact state.',
            'independent_incline':'Constant 1 degree in world x from -0.48 to 1.50; release changes by a few mm, and start-x assertion protects the full one-metre uphill measurement.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('track',choices=(*TRACKS,'verify'));p.add_argument('seed',nargs='?',type=int,default=12600381);p.add_argument('--trace',type=Path);a=p.parse_args()
    if a.track=='verify':
        out=verify_geometry();course.save(HERE/'geometry/rays.json',out);print('verified',len(out['profiles']),'geometry configurations')
    else:
        r=run(a.track,a.seed,trace=a.trace);print({k:r[k] for k in ('seconds','reason','valid_peak_m','last_both_m','flat_1m','slope_1m','finish_2p5')})
