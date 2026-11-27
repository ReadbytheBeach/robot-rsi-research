"""Phase-local landing recovery from body IMU, hip speed and bounded servo actions."""
from functools import lru_cache
from pathlib import Path
import sys
import numpy as np
import onnx
from onnx import compose, helper, numpy_helper

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import adapter
import run
td=run.td
PARENT=HERE.parent/"models/repeat-left-warm.onnx"
EXPERTS={name:HERE.parent/"models"/(name+".onnx") for name in ("guard18p8","original11")}
NAMES=("first_gain","third_gain","first_offset_s","third_offset_s","release_s","floor_weight",
       "tilt_gain","angular_gain","hip_velocity_gain","roll_reaction","pitch_reaction")
LO=np.array([.10,.10,-.40,-.30,-.16,0.,.2,.03,0.,-.35,-.3])
HI=np.array([1.,1.,.18,.22,.35,.92,3.,.40,.30,.35,.30])


def schedules(p):
    t=td.TIME_GRID - 2/30
    w=np.zeros(len(t))
    for start,plateau,out,end,offset,gain in [(3.54,3.80,4.31,4.64,p[2],p[0]),
                                               (7.30,7.53,7.99,8.30,p[3],p[1])]:
        pulse=adapter._pulse(t,start+offset,plateau+offset,out+offset+p[4],end+offset+p[4])
        w=np.maximum(w,gain*pulse)
    return w.astype('f')


def actor(p,expert):
    p=np.asarray(p,'f'); weights=schedules(p)
    dance=td.wrapped_actor(str(PARENT));steady=td.wrapped_actor(str(EXPERTS[expert]))
    lo,hi=adapter.command_limits()
    roll=np.zeros(14,'f');roll[[1,10]]=1.
    pitch=np.zeros(14,'f');pitch[[4,13]]=[1.,-1.]
    def policy(obs):
        phase=int(np.argmax(obs[48:50]@td.BASIS))
        measured=np.maximum(0.,np.max(np.abs(obs[3:5]))-.12)*p[6]
        measured+=np.maximum(0.,np.max(np.abs(obs[:2]))-.55)*p[7]
        measured+=np.maximum(0.,np.max(np.abs(obs[[21,30]]))-1.5)*p[8]
        w=np.float32(weights[phase]*min(1.,p[5]+measured))
        base=dance(obs)
        if w==0.:
            return base
        rx=p[9]*(obs[4]+np.float32(.065)*obs[0])
        py=p[10]*(obs[3]+np.float32(.065)*obs[1])
        blend=base+w*(steady(obs)-base+rx*roll+py*pitch)
        last=obs[34:48]
        return np.clip(last+np.clip(blend-last,-adapter.MAX_STEP,adapter.MAX_STEP),lo,hi)
    return policy


def export(p,expert,path):
    p=np.asarray(p,'f')
    model=compose.add_prefix(onnx.load(PARENT),"lf_move/")
    still=compose.add_prefix(onnx.load(EXPERTS[expert]),"lf_recover/")
    g=model.graph; obs=g.input[0].name
    g.node.append(helper.make_node("Identity",[obs],[still.graph.input[0].name]))
    g.initializer.extend(still.graph.initializer);g.node.extend(still.graph.node)
    def arr(k,x):
        k="landing/"+k;g.initializer.append(numpy_helper.from_array(np.asarray(x),k));return k
    def op(kind,ins,k,**kw):
        k="landing/"+k;g.node.append(helper.make_node(kind,ins,[k],**kw));return k
    def cols(ix,k):
        return op("Gather",[obs,arr(k+"i",np.array(ix,np.int64))],k,axis=1)
    def coef(x,k):return arr(k,np.float32(x))
    def mul(input,x,k):return op("Mul",[input,coef(x,k+"c")],k)
    def add(x,y,k):return op("Add",[x,y],k)
    def sub(x,y,k):return op("Sub",[x,y],k)
    def risk(ix,thr,gain,k):
        mag=op("ReduceMax",[op("Abs",[cols(ix,k+"cols")],k+"abs"),arr(k+"ax",np.array([1],np.int64))],k+"mag",keepdims=1)
        return mul(op("Relu",[sub(mag,coef(thr,k+"thr"),k+"dist")],k+"ex"),gain,k+"risk")
    idx=op("ArgMax",[op("MatMul",[cols([48,49],"phase"),arr("basis",td.BASIS)],"phase_dot")],"phaseid",axis=1,keepdims=0)
    sched=op("Gather",[arr("window",schedules(p)[:,None]),idx],"window_at",axis=0)
    rr=add(risk([3,4],.12,p[6],"tilt"),risk([0,1],.55,p[7],"gyro"),"bodyrisk")
    rr=add(rr,risk([21,30],1.5,p[8],"hip"),"risk")
    w=op("Mul",[sched,op("Min",[coef(1.,"one"),add(coef(p[5],"floor"),rr,"floor_risk")],"bound")],"w")
    roll=np.zeros(14,'f');roll[[1,10]]=1.
    pitch=np.zeros(14,'f');pitch[[4,13]]=[1.,-1.]
    def corr(s,g,k,axis,sgn):
        signal=add(cols([s],k+"pos"),mul(cols([g],k+"rate"),.065,k+"lead"),k+"state")
        return op("Mul",[mul(signal,sgn,k+"gain"),arr(k+"axes",axis)],k+"q")
    base=g.output[0].name;steady=still.graph.output[0].name
    direction=add(add(sub(steady,base,"delta"),corr(4,0,"roll",roll,p[9]),"rollfix"),corr(3,1,"pitch",pitch,p[10]),"fullfix")
    target=add(base,op("Mul",[w,direction],"scaled"),"target")
    prev=cols(np.arange(34,48),"prev");lo,hi=adapter.command_limits()
    bounded=op("Clip",[sub(target,prev,"step"),coef(-adapter.MAX_STEP,"minus_step"),coef(adapter.MAX_STEP,"plus_step")],"step_bound")
    option=op("Min",[op("Max",[add(prev,bounded,"action"),arr("lower",lo)],"above"),arr("upper",hi)],"inside")
    g.output[0].name=op("Where",[op("Equal",[w,coef(0,"zero")],"idle"),base,option],"out")
    onnx.checker.check_model(model)
    onnx.save(model,str(path))
