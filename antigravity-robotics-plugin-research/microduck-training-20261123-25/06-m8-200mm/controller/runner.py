"""Run one uninterrupted physical MicroDuck delivery beginning with both nuts 200 mm apart."""
import argparse
import importlib
import json
from pathlib import Path
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from episode import GroundContext, deliver, dual, parameters, play_pick, settings


def result(ctx):
    a=ctx.audit
    row=dict(seed=ctx.seed,layout=ctx.label,delay_ms=20*ctx.delay,strategy='together',
        engine='MuJoCo',reason=ctx.reason or 'uncompleted',success=ctx.reason=='success',stage=ctx.stage,
        t=round(ctx.time,5),scope='Ropedia scan S0–S2, 200 mm floor pair, known simulator state',
        initial_nuts=ctx.initial,actual_initial_angle_deg=float(np.degrees(np.arctan2(
            ctx.initial[1][1]-ctx.initial[0][1],ctx.initial[1][0]-ctx.initial[0][0]))),
        angle_sector=ctx.sector,asset_profile='official-bom',diagnostic_fork=ctx.diagnostic,
        first_failure=a.problem or ctx.gap.problem,recovery_incidents=[],routes=ctx.routes,
        events=a.events,released=ctx.released,maximum_pick_seconds=a.best.tolist(),
        physical_steps=a.physical_steps,max_pad_penetration_m=a.max_pad_depth.tolist(),
        robot_final=ctx.d.qpos[ctx.root:ctx.root+3].tolist(),nut_final=ctx.d.xpos[a.nut].tolist(),
        last_support=a.basket.last,final_drift_m=ctx.final_drift,placement_probes=ctx.probes,
        double_witness=ctx.dual.report(),gap_witness=ctx.gap.report(),development=ctx.details)
    if row['success']:
        issues=dual.discrepancies(row)
        witness=row['gap_witness']
        if witness['settled_distance_m'] is None or abs(witness['settled_distance_m']-.2)>.001:issues.append('start_distance')
        if witness['closed_bites']!=1 or witness['first_lift_difference_s'] is None or witness['first_lift_difference_s']>.02000001:issues.append('one_synchronized_bite')
        if witness['exit_at'] is None or witness['exit_at']<ctx.dual.qualified:issues.append('near_station_exit')
        if issues:
            row.update(success=False,reason='witness_'+issues[0],audit_issues=issues)
    if ctx.trace and a.rows:
        trace=Path(ctx.trace);trace.parent.mkdir(parents=True,exist_ok=True)
        from xml.etree import ElementTree as ET
        xml=ET.fromstring(ctx.xml);xml.find('option').set('timestep',str(.02/ctx.standard))
        trace.with_suffix('.xml').write_text(ET.tostring(xml,encoding='unicode'))
        names=('t','stage','qpos','ctrl','robot_com','nut_com','low_z','pad_force','in_basket_s','pad_penetration_m')
        arrays={key:np.asarray(col) for key,col in zip(names,zip(*a.rows))}
        arrays['gap_floor_witness']=np.asarray(ctx.gap.rows)
        np.savez_compressed(trace,**arrays)
        trace.with_suffix('.json').write_text(json.dumps(dict(result=row),indent=2,allow_nan=False))
    return row


def run_audited(job):
    ctx=GroundContext(job)
    cfg=ctx.config
    if ctx.settle():
        method=cfg.get('gather_controller')
        if method is None:
            ctx.reason='ground_controller_not_selected'
        else:
            outcome=importlib.import_module(method).gather(ctx,cfg.get('gather_options',{}))
            if not isinstance(outcome,dict):raise TypeError('gather() must return a result dictionary')
            ctx.details['gather']=outcome
            if not ctx.reason and not outcome.get('success',False):
                ctx.reason=outcome.get('reason','gather_failed')
    if not ctx.reason:
        import align_pair
        entry=align_pair.align(ctx,ctx.params,cfg)
        if entry is None and not ctx.reason:ctx.reason='pickup_alignment_timeout'
        if entry is not None:
            ctx.details['entry']={k:v for k,v in entry.items() if k not in ('params','history')}
            if not ctx.reason:
                from transport_variants import variants
                ctx.config=dict(variants(ctx.config))[entry.get("transport_preset","original")]
                action=play_pick(ctx,entry)
                if action is not None:deliver(ctx,action)
    return result(ctx)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--layout',default='S0')
    p.add_argument('--delay-ms',type=int,choices=(0,20),default=0)
    p.add_argument('--config',type=Path)
    p.add_argument('--params',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--trace',action='store_true')
    args=p.parse_args()
    cfg=settings() | (json.loads(args.config.read_text()) if args.config else {})
    pars=json.loads(args.params.read_text()) if args.params else parameters()
    args.out.mkdir(parents=True,exist_ok=True)
    target=args.out/f'seed-{args.seed}.json'
    if target.exists():p.error(f'Output already present: {target}')
    trace=args.out/'trace'/f'seed-{args.seed}.npz' if args.trace else None
    row=run_audited((args.seed,args.layout,args.delay_ms//20,pars,cfg,trace))
    partial=target.with_suffix('.partial')
    partial.write_text(json.dumps(row,indent=2,allow_nan=False)+'\n')
    partial.replace(target)
    print(row['seed'],row['reason'],row['t'],flush=True)


if __name__=='__main__':main()
