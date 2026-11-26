"""Native narrow inner loop; all control is supplied through original joint targets."""
from functools import lru_cache
from pathlib import Path
from hashlib import sha256
import os,ctypes,tempfile,subprocess
import mujoco
import numpy as np

@lru_cache(None)
def load():
    src=Path(__file__).with_suffix('.c')
    package=Path(mujoco.__file__).parent
    so=next(package.glob('libmujoco.so.*'))
    key=sha256(src.read_bytes()+so.name.encode()).hexdigest()[:20]
    folder=Path(tempfile.gettempdir())/f'm8-preview-{os.getuid()}';folder.mkdir(mode=0o700,exist_ok=True)
    dll=folder/f'{key}.so'
    if not dll.exists():
        with tempfile.NamedTemporaryFile(dir=folder,delete=False,suffix='.so') as f:dest=Path(f.name)
        try:
            subprocess.run(['cc','-O2','-fPIC','-shared','-I'+str(package/'include'),str(src),str(so),'-Wl,-rpath,'+str(package),'-o',str(dest)],check=True)
            dest.replace(dll)
        finally:dest.unlink(missing_ok=True)
    fn=ctypes.CDLL(str(dll)).foot_roll
    T=ctypes.c_void_p;I=ctypes.c_int;F=ctypes.c_double
    fn.argtypes=[T,T,I,T,T,I,I,I,T,I,T,F,I,F,F,I]
    fn.restype=I
    return fn

class Roll:
    def __init__(self,ctx,verts):
        self.fn=load();self.ctx=ctx;self.verts=np.ascontiguousarray(verts,dtype=np.float64)
        a=ctx.audit;acc=a.accelerator
        self.args=(ctx.standard,acc.flags.ctypes.data,acc.owner.ctypes.data,int(a.nut[0]),int(a.nut[1]),int(a.trunk),self.verts.ctypes.data,len(self.verts))
        self.model=ctx.m._address
    def run(self,d,air,limit=.020,contact_guard=True,tilt_min=.62,max_x=.548):
        return self.fn(self.model,d._address,*self.args,air.ctypes.data,limit,int(contact_guard),tilt_min,max_x,self.ctx.root)
