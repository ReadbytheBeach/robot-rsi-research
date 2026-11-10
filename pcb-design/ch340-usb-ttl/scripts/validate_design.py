#!/usr/bin/env python3
"""Check the physical user requirements and schematic-to-pad net agreement."""
import collections,json,math
from pathlib import Path
import pcbnew

ROOT=Path(__file__).resolve().parents[1]
board=pcbnew.LoadBoard(str(ROOT/'ch340-usb-ttl.kicad_pcb'))
design=json.loads((ROOT/'design.json').read_text())
checks={};errors=[]
def check(name,value,ok):
 checks[name]=value
 if not ok:errors.append(name)
points=[]
for edge in board.GetDrawings():
 if edge.GetLayer()==pcbnew.Edge_Cuts:
  points += [edge.GetStart(),edge.GetEnd()]
assert points,'No Edge.Cuts'
width=(max(p.x for p in points)-min(p.x for p in points))/1e6
height=(max(p.y for p in points)-min(p.y for p in points))/1e6
check('outline_mm',[width,height],abs(width-30)<1e-5 and abs(height-30)<1e-5)
thickness=board.GetDesignSettings().GetBoardThickness()/1e6
check('thickness_mm',thickness,abs(thickness-1.0)<1e-6)
check('copper_layers',board.GetCopperLayerCount(),board.GetCopperLayerCount()==2)
fps={p.GetReference():p for p in board.GetFootprints()}
back=[r for r,fp in fps.items() if fp.GetLayer()!=pcbnew.F_Cu]
check('non_front_footprints',back,not back)
expected={p['ref']:p for p in design['components']}
check('component_refs',sorted(fps),set(fps)==set(expected))
pin_errors=[]
for ref,spec in expected.items():
 if ref not in fps:continue
 pads=collections.defaultdict(list)
 for pad in fps[ref].Pads():pads[pad.GetNumber()].append(pad)
 for number,net in spec['pins'].items():
  if number not in pads:
   pin_errors.append([ref,number,'missing footprint pad'])
   continue
  for pad in pads[number]:
   actual=pad.GetNetname().removeprefix('/')
   if net is None:
    okay=actual=='' or actual.startswith('unconnected-(')
   else:okay=actual==net
   if not okay:pin_errors.append([ref,number,net,pad.GetNetname()])
check('pin_to_pad_net_errors',pin_errors,not pin_errors)
usb={name:[] for name in ['USB_D+','USB_D-']}
endpoints=collections.defaultdict(list)
for t in board.GetTracks():
 if t.Type()!=pcbnew.PCB_TRACE_T:continue
 a,b=t.GetStart(),t.GetEnd()
 if a==b:continue
 endpoints[t.GetNetCode(),t.GetLayer(),a.x,a.y].append((b.x-a.x,b.y-a.y))
 endpoints[t.GetNetCode(),t.GetLayer(),b.x,b.y].append((a.x-b.x,a.y-b.y))
 name=t.GetNetname().removeprefix('/')
 if name in usb:
  usb[name].append({'width_mm':t.GetWidth()/1e6,'length_mm':t.GetLength()/1e6,
                              'layer':board.GetLayerName(t.GetLayer())})
corners=[];terminal_corners=[]
all_pads=[p for fp in fps.values() for p in fp.Pads()]
all_vias=[t for t in board.GetTracks() if t.Type()==pcbnew.PCB_VIA_T]
for key,vectors in endpoints.items():
 if len(vectors)!=2:continue # Branches are junctions, not degree-two bends.
 a,b=vectors
 dot=a[0]*b[0]+a[1]*b[1]
 norm=math.hypot(*a)*math.hypot(*b)
 if norm and abs(dot)/norm<1e-5:
  item={'net_code':key[0],'layer':board.GetLayerName(key[1]),'x_mm':key[2]/1e6,'y_mm':key[3]/1e6}
  point=pcbnew.VECTOR2I(key[2],key[3])
  pad_terminal=any(p.GetNetCode()==key[0] and p.IsOnLayer(key[1]) and p.HitTest(point) for p in all_pads)
  via_terminal=any(v.GetNetCode()==key[0] and math.hypot(v.GetPosition().x-key[2],v.GetPosition().y-key[3])<=v.GetWidth(key[1])/2 for v in all_vias)
  if pad_terminal or via_terminal:terminal_corners.append(item)
  else:corners.append(item)
check('right_angle_degree2_corners',corners,not corners)
checks['excluded_terminal_junctions']=terminal_corners
stats={}
for name,segments in usb.items():
 controlled=sum(s['length_mm'] for s in segments if abs(s['width_mm']-.75)<1e-5)
 stats[name]={'controlled_width_length_mm':controlled,'all_segment_length_mm':sum(s['length_mm'] for s in segments),
              'widths_mm':sorted({s['width_mm'] for s in segments}),'layers':sorted({s['layer'] for s in segments})}
 check(name+'_front_controlled_segment',stats[name],controlled>0 and all(s['layer']=='F.Cu' for s in segments if abs(s['width_mm']-.75)<1e-5))
check('J2_pinout',[expected['J2']['pins'][str(i)] for i in range(1,5)],
      [expected['J2']['pins'][str(i)] for i in range(1,5)]==['+3V3','UART_TX','UART_RX','GND'])
for name in ['erc','drc']:
 p=ROOT/'analysis'/f'{name}.json'
 if p.exists():
  d=json.loads(p.read_text())
  findings=d.get('violations',[]) + d.get('unconnected_items',[])
  for sheet in d.get('sheets',[]):findings+=sheet.get('violations',[])
  check('native_'+name+'_findings',len(findings),not findings)
 else:check('native_'+name+'_report','missing',False)
result={'status':'passed' if not errors else 'failed','checks':checks,'failed_checks':errors,
        'limits':'Geometry/net consistency checks; impedance is calculated, not measured; branches and vertices inside same-net pads/via disks are terminal junctions, excluded from free-trace bend count.'}
(ROOT/'analysis/requirements-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(0 if not errors else 1)
