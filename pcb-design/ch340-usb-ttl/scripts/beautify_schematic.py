#!/usr/bin/env python3
"""Apply repeatable readable field placement without changing component UUIDs."""
from pathlib import Path
import sys,uuid
import sexpdata
from sexpdata import Symbol as S
sys.path.insert(0,'/workspace/pcb-tooling/vendor/KiCAD-MCP-Server/python')
from utils.sexpr_format import dumps
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'ch340-usb-ttl.kicad_sch'
tree=sexpdata.loads(P.read_text())
def ch(p,k):return next((v for v in p if isinstance(v,list) and v and str(v[0])==k),None)
def cs(p,k):return [v for v in p if isinstance(v,list) and v and str(v[0])==k]
special={'J1':[(25.4,38.1),(25.4,40.64)],
         'D1':[(104.14,53.34),(104.14,55.88)],
         'U1':[(165.1,40.64),(165.1,43.18)],
         'J2':[(243.84,55.88),(243.84,58.42)],
         'U2':[(91.44,111.76),(91.44,114.3)],
         'D2':[(205.74,118.11),(205.74,120.65)]}
for inst in cs(tree,'symbol'):
    props={str(p[1]):p for p in cs(inst,'property')}
    ref=str(props['Reference'][2])
    if ref.startswith('#'):continue
    x,y=map(float,ch(inst,'at')[1:3])
    loc=special.get(ref,[(x+3.81,y-2.54),(x+3.81,y)])
    for (name,xy) in zip(['Reference','Value'],loc):
        p=props[name];ch(p,'at')[1:]=[*xy,0]
        e=ch(p,'effects');e[:]=[v for v in e if not (isinstance(v,list) and v and str(v[0])=='justify')]
        e.append([S('justify'),S('left')])
        if ref.startswith('TP') and name=='Value' and ch(e,'hide') is None:e.append([S('hide'),S('yes')])
for label in cs(tree,'label'):
    at=ch(label,'at')
    if float(at[3])==180:at[3]=0
# Merge the two same-rail power pin label stubs into one readable rail.
tree[:]=[v for v in tree if not (isinstance(v,list) and v and str(v[0])=='label'
          and str(v[1])=='+3V3' and abs(float(ch(v,'at')[1])-152.4)<1e-5
          and abs(float(ch(v,'at')[2])-45.72)<1e-5)]
points=[[149.86,45.72],[152.4,45.72]]
already=False
for w in cs(tree,'wire'):
    pts=ch(w,'pts')
    if [[float(z) for z in a[1:]] for a in pts[1:]]==points:already=True
if not already:
    tree.append([S('wire'),[S('pts'),*[ [S('xy'),*p] for p in points]],
                 [S('stroke'),[S('width'),0],[S('type'),S('default')]],
                 [S('uuid'),str(uuid.uuid4())]])
P.write_text(dumps(tree))
print(P)
