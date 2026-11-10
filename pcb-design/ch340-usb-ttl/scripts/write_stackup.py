#!/usr/bin/env python3
"""Persist the explicit 1.000mm nominal stack without rewriting PCB geometry."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'ch340-usb-ttl.kicad_pcb'
text=p.read_text()
stack='''(stackup
      (layer "F.SilkS" (type "Top Silk Screen"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.010))
      (layer "F.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 1" (type "core") (thickness 0.910) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness 0.035))
      (layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.010))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen"))
      (copper_finish "ENIG")
      (dielectric_constraints yes)
    )'''
def node_end(s,start):
 depth=0;quoted=False;escaped=False
 for i in range(start,len(s)):
  c=s[i]
  if quoted:
   if escaped:escaped=False
   elif c=='\\':escaped=True
   elif c=='"':quoted=False
  elif c=='"':quoted=True
  elif c=='(':depth+=1
  elif c==')':
   depth-=1
   if depth==0:return i+1
 raise ValueError('Unbalanced PCB S-expression')
setup=re.search(r'\(setup\b',text)
if not setup:raise SystemExit('PCB setup not found')
end=node_end(text,setup.start())
old=re.search(r'\(stackup\b',text[setup.end():end])
if old:
 begin=setup.end()+old.start()
 text=text[:begin]+stack+text[node_end(text,begin):]
else:text=text[:setup.end()]+'\n    '+stack+text[setup.end():]
p.write_text(text)
assert abs(.010+.035+.910+.035+.010-1.000)<1e-12
print('Stack recorded: mask .010 + Cu .035 + core .910 + Cu .035 + mask .010 = 1.000 mm')
