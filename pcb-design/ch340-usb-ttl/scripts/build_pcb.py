#!/usr/bin/env python3
"""Build the native KiCad 9 PCB from the exported schematic XML netlist.

Run with /usr/bin/python3 through pcb-tooling/bin/with-kicad-env.
All component pin assignments come from the native XML, not a parallel hand netlist.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import pcbnew as k

ROOT=Path(__file__).resolve().parents[1]
NAME='ch340-usb-ttl'
OFFSET=50.0
def mm(v): return k.FromMM(float(v))
def pt(p): return k.VECTOR2I(mm(p[0]+OFFSET),mm(p[1]+OFFSET))
def xy(v): return (k.ToMM(v.x)-OFFSET,k.ToMM(v.y)-OFFSET)
def plain(s): return s.lstrip('/')

PLACEMENTS={
 'J1':(15,3.675,180),'J2':(5.5,27.4,0),'U1':(15.9,22.2,270),
 'D1':(14.63,10.6,270),'F1':(6,11,270),'U2':(6.4,18.4,0),
 'R1':(22,7.5,0),'R2':(7.5,6.5,90),'R3':(6,21.5,0),
 'D2':(6,23.5,0),'C1':(18.3,11.8,0),'C2':(3.5,17.4,90),
 'C3':(9.3,16.6,90),'C4':(22.8,24.2,0),'C5':(19.1,16.3,90),
 'TP1':(27.1,14.2,0),'TP2':(27.1,17.2,0),'TP3':(27.1,20.2,0),'TP4':(27.1,23.2,0),
}

def load_design():
    data=json.loads((ROOT/'design.json').read_text())
    tree=ET.parse(ROOT/(NAME+'.net')).getroot()
    components={c.attrib['ref']:c for c in tree.findall('./components/comp')}
    net_nodes={}
    nets={}
    for e in tree.findall('./nets/net'):
        name=e.attrib['name'];nets[name]=int(e.attrib['code'])
        for node in e.findall('node'):net_nodes[(node.attrib['ref'],node.attrib['pin'])]=name
    return data,components,nets,net_nodes

def project_rules(nets):
    p=ROOT/(NAME+'.kicad_pro');x=json.loads(p.read_text())
    rules=x['board']['design_settings']['rules']
    rules.update(min_clearance=.15,min_track_width=.15,min_copper_edge_clearance=.25,
                 min_via_diameter=.5,min_through_hole_diameter=.25,min_via_annular_width=.125,
                 min_hole_clearance=.15,min_hole_to_hole=.25,min_silk_clearance=.15,
                 min_text_height=.8,min_text_thickness=.12)
    import copy
    base=x['net_settings']['classes'][0]
    base.update(name='Default',clearance=.15,track_width=.2,via_diameter=.6,via_drill=.3,
                diff_pair_width=.75,diff_pair_gap=.15)
    classes=[base]
    for name,width in [('Power',.4),('Ground',.3),('USB',.15)]:
        c=copy.deepcopy(base);c.update(name=name,track_width=width);classes.append(c)
    x['net_settings']['classes']=classes
    patterns=[]
    for n in nets:
        q=plain(n)
        cls='Ground' if q=='GND' else ('Power' if q in ('+3V3','+5V_USB','+5V_FUSED') else ('USB' if q in ('USB_D+','USB_D-') else None))
        if cls:patterns.append({'netclass':cls,'pattern':n})
    x['net_settings']['netclass_patterns']=patterns
    saved=json.dumps(x,indent=2)+'\n';p.write_text(saved)
    (ROOT/(NAME+'.kicad_dru')).write_text('''(version 1)
(rule "USB neck and nominal coupled width"
  (condition "A.NetClass == 'USB'")
  (constraint track_width (min 0.15mm) (opt 0.75mm)))
''')
    return saved

def line(board,a,b,net,width=.2,layer=k.F_Cu,locked=False):
    if math.dist(a,b)<1e-6:return None
    tr=k.PCB_TRACK(board);tr.SetStart(pt(a));tr.SetEnd(pt(b));tr.SetWidth(mm(width));tr.SetLayer(layer)
    tr.SetNet(net);tr.SetLocked(locked);board.Add(tr);return tr
def polyline(board,points,net,width=.2,layer=k.F_Cu,locked=False):
    return [line(board,a,b,net,width,layer,locked) for a,b in zip(points,points[1:])]
def via(board,p,net,diameter=.6,drill=.3,locked=False):
    v=k.PCB_VIA(board);v.SetPosition(pt(p));v.SetWidth(k.F_Cu,mm(diameter));v.SetDrill(mm(drill));v.SetViaType(k.VIATYPE_THROUGH)
    v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net);v.SetLocked(locked);board.Add(v);return v
def rectangle_zone(board,name,layer,box,net=None,keep_tracks=False,keep_vias=False,keep_pour=False):
    z=k.ZONE(board);z.SetLayer(layer);z.SetZoneName(name)
    if net is not None:z.SetNet(net)
    if keep_tracks or keep_vias or keep_pour:
        z.SetIsRuleArea(True);z.SetDoNotAllowTracks(keep_tracks);z.SetDoNotAllowVias(keep_vias)
        z.SetDoNotAllowCopperPour(keep_pour);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
    else:
        z.SetLocalClearance(mm(.2));z.SetMinThickness(mm(.15));z.SetPadConnection(k.ZONE_CONNECTION_FULL)
    x0,y0,x1,y1=box;o=z.Outline();o.NewOutline()
    for p in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]:
        q=pt(p);o.Append(q.x,q.y)
    board.Add(z);return z

def text(board,value,pos,size=.9,layer=k.F_SilkS):
    t=k.PCB_TEXT(board);t.SetText(value);t.SetPosition(pt(pos));t.SetLayer(layer)
    t.SetTextSize(k.VECTOR2I(mm(size),mm(size)));t.SetTextThickness(mm(.12));board.Add(t)

def footprints(board,data,components,net_objects,node_map):
    fps={};missing=[]
    for ref,c in components.items():
        footprint=c.findtext('footprint')
        if not footprint:continue
        lib,name=footprint.split(':',1)
        folder=ROOT/(lib+'.pretty')
        if not folder.is_dir():folder=Path('/usr/share/kicad/footprints')/(lib+'.pretty')
        fp=k.FootprintLoad(str(folder),name)
        if fp is None:raise RuntimeError(f'Footprint not found {footprint}')
        fp.SetReference(ref);fp.SetValue(c.findtext('value') or '')
        fp.SetFPID(k.LIB_ID(lib,name))
        identifier=c.findtext('tstamps') or next(a['uuid'] for a in data['components'] if a['ref']==ref)
        path=k.KIID_PATH();path.push_back(k.KIID(data['root_uuid']));path.push_back(k.KIID(identifier))
        fp.SetPath(path)
        x,y,angle=PLACEMENTS[ref];fp.SetPosition(pt((x,y)));fp.SetOrientationDegrees(angle)
        fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
        for pad in fp.Pads():
            net=node_map.get((ref,pad.GetNumber()))
            if net:pad.SetNet(net_objects[net])
        models=fp.Models()
        for index in range(len(models)):
            model=models[index]
            source=str(model.m_Filename)
            relative=source.replace('${KICAD9_3DMODEL_DIR}/','')
            model.m_Filename='${KIPRJMOD}/3dmodels/'+relative
            # KiCad 9's SWIG vector yields model values, not writable references.
            # Assign the changed value back into the footprint's model vector.
            models[index]=model
            if not (ROOT/'3dmodels'/relative).is_file():missing.append({'ref':ref,'model':model.m_Filename})
        board.Add(fp);fps[ref]=fp
    (ROOT/'analysis'/'missing-3d-models.json').write_text(json.dumps(missing,indent=2)+'\n')
    return fps

def usb_routes(board,net_objects):
    plus=next(v for n,v in net_objects.items() if plain(n)=='USB_D+')
    minus=next(v for n,v in net_objects.items() if plain(n)=='USB_D-')
    # USB-C's interleaved duplicate contacts: short branches before the main trunk.
    y=7.355
    polyline(board,[(14.25,y),(14.25,6.70),(14.55,6.40),(14.95,6.40),(15.25,6.70),(15.25,y)],plus,.15,locked=True)
    polyline(board,[(15.25,y),(15.25,8.0),(15.58,8.33),(15.58,9.4625)],plus,.15,locked=True)
    line(board,(14.75,y),(14.75,8.155),minus,.15,locked=True)
    via(board,(14.75,8.155),minus,.5,.25,True)
    polyline(board,[(15.75,y),(15.75,7.95),(16.25,8.45)],minus,.15,locked=True)
    via(board,(16.25,8.45),minus,.5,.25,True)
    polyline(board,[(14.75,8.155),(15.955,8.155),(16.25,8.45)],minus,.15,k.B_Cu,True)
    polyline(board,[(14.75,8.155),(14.645,8.155),(13.68,9.12),(13.68,9.4625)],minus,.15,locked=True)
    for n,x,end_x in [(plus,15.08,15.58),(minus,14.18,13.68)]:
        # Board copper explicitly joins the flow-through ESD pin pair.
        line(board,(end_x,9.4625),(end_x,11.7375),n,.3,locked=True)
        line(board,(end_x,11.7375),(end_x,12.8),n,.3,locked=True)
        line(board,(end_x,12.8),(x,13.3),n,.75,locked=True)
        line(board,(x,13.3),(x,18.3),n,.75,locked=True)
    polyline(board,[(15.08,18.3),(15.265,18.485),(15.265,19.725)],plus,.3,locked=True)
    polyline(board,[(14.18,18.3),(13.995,18.485),(13.995,19.725)],minus,.3,locked=True)
    rectangle_zone(board,'USB controlled trunk bottom reference',k.B_Cu,(13.6,13.1,15.65,18.65),keep_tracks=True,keep_vias=True)
    rectangle_zone(board,'USB top coplanar copper exclusion',k.F_Cu,(11.0,13.1,18.3,18.65),keep_pour=True)

def bbox_local(item):
    b=item.GetBoundingBox();return (k.ToMM(b.GetX())-OFFSET,k.ToMM(b.GetY())-OFFSET,k.ToMM(b.GetRight())-OFFSET,k.ToMM(b.GetBottom())-OFFSET)
def overlap(a,b):return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]

def ground_stitches(board,fps,net_objects):
    ground=next(v for n,v in net_objects.items() if plain(n)=='GND')
    # ESD ground returns vertically through a tented via under the package body.
    line(board,(14.63,9.4625),(14.63,10.6),ground,.3)
    via(board,(14.63,10.6),ground,.5,.25)
    pads=[p for f in fps.values() for p in f.Pads()]
    seen=set()
    for ref,fp in fps.items():
        for pad in fp.Pads():
            if pad.GetNetCode()!=ground.GetNetCode() or pad.GetAttribute()!=k.PAD_ATTRIB_SMD:continue
            p=xy(pad.GetPosition());key=tuple(round(v,5) for v in p)
            if key in seen or ref=='D1':continue
            seen.add(key)
            center=xy(fp.GetPosition());dx=p[0]-center[0];dy=p[1]-center[1]
            base=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]
            base.sort(key=lambda d:-(d[0]*dx+d[1]*dy)/(math.hypot(*d) or 1))
            chosen=None
            for distance in (1.1,1.5,2.0):
                for vx,vy in base:
                    q=(p[0]+vx*distance,p[1]+vy*distance)
                    if not(.7<q[0]<29.3 and .7<q[1]<29.3):continue
                    if 13.6<=q[0]<=15.65 and 13.1<=q[1]<=18.65:continue
                    vbox=(q[0]-.48,q[1]-.48,q[0]+.48,q[1]+.48)
                    seg=(min(p[0],q[0])-.26,min(p[1],q[1])-.26,max(p[0],q[0])+.26,max(p[1],q[1])+.26)
                    bad=False
                    for other in pads:
                        if other.GetNetCode()==ground.GetNetCode():continue
                        if overlap(vbox,bbox_local(other)) or overlap(seg,bbox_local(other)):
                            bad=True;break
                    if not bad:
                        for tr in board.GetTracks():
                            if tr.GetNetCode()==ground.GetNetCode():continue
                            if overlap(vbox,bbox_local(tr)) or (tr.GetLayer()==k.F_Cu and overlap(seg,bbox_local(tr))):bad=True;break
                    if not bad:chosen=q;break
                if chosen:break
            if chosen is None:raise RuntimeError(f'No conservative ground via location for {ref}.{pad.GetNumber()} at{p}')
            line(board,p,chosen,ground,.2);via(board,chosen,ground)
    # Peripheral stitching, outside signal fanout and connector bodies.
    for p in [(1.5,1.5),(28.5,1.5),(1.5,14),(28.5,27.5),(1.5,28.5),(9,26.5),(22,26.5)]:
        via(board,p,ground)
    # Close return stitches for the connector duplicate-contact branch and UART fanout.
    for p in [(13.78,8.34),(16.7,9.3),(4.8085,22.8392),(20.8,21.7)]:
        via(board,p,ground,.5,.25)
    return ground

def power_backbones(board,net_objects):
    """Three explicit short rail branches, with vias outside the USB reference strip."""
    p3=next(v for n,v in net_objects.items() if plain(n)=='+3V3')
    p5=next(v for n,v in net_objects.items() if plain(n)=='+5V_USB')
    # V3 bypass capacitor to CH340C V3, via a back-side path east of USB reference.
    line(board,(19.1,17.075),(19.1,18.1),p3,.3,locked=True)
    via(board,(19.1,18.1),p3,locked=True)
    line(board,(16.535,19.725),(16.535,18.2),p3,.3,locked=True)
    via(board,(16.535,18.2),p3,locked=True)
    polyline(board,[(19.1,18.1),(16.635,18.1),(16.535,18.2)],p3,.3,k.B_Cu,True)
    # Supply the LED and connector-side branch from the LDO output landing.
    line(board,(5.175,21.5),(4.1,21.5),p3,.3,locked=True)
    via(board,(4.1,21.5),p3,locked=True)
    polyline(board,[(8.2,17.375),(8.7,17.875),(8.7,18.4)],p3,.3,locked=True)
    via(board,(8.7,18.4),p3,locked=True)
    polyline(board,[(4.1,21.5),(5.6,21.5),(8.7,18.4)],p3,.3,k.B_Cu,True)
    # ESD rail clamp bypass branch. Both vias are before the controlled trunk.
    line(board,(14.63,11.7375),(14.63,12.6),p5,.3,locked=True)
    via(board,(14.63,12.6),p5,.5,.25,True)
    polyline(board,[(17.525,11.8),(18.1,11.225),(18.1,10.7)],p5,.3,locked=True)
    via(board,(18.1,10.7),p5,locked=True)
    polyline(board,[(14.63,12.6),(16.2,12.6),(18.1,10.7)],p5,.3,k.B_Cu,True)

def build():
    data,components,nets,nodes=load_design();project_text=project_rules(nets)
    board=k.BOARD();board.SetCopperLayerCount(2)
    ds=board.GetDesignSettings();ds.SetBoardThickness(mm(1.0));ds.m_MinClearance=mm(.15);ds.m_TrackMinWidth=mm(.15)
    ds.m_CopperEdgeClearance=mm(.25);ds.SetAuxOrigin(pt((0,0)));ds.SetGridOrigin(pt((0,0)))
    for a,b in [((0,0),(30,0)),((30,0),(30,30)),((30,30),(0,30)),((0,30),(0,0))]:
        sh=k.PCB_SHAPE();sh.SetShape(k.SHAPE_T_SEGMENT);sh.SetStart(pt(a));sh.SetEnd(pt(b));sh.SetLayer(k.Edge_Cuts);sh.SetWidth(mm(.05));board.Add(sh)
    objects={}
    for name,code in sorted(nets.items(),key=lambda v:v[1]):
        ni=k.NETINFO_ITEM(board,name,code);board.Add(ni);objects[name]=ni
    fps=footprints(board,data,components,objects,nodes)
    usb_routes(board,objects)
    ground=ground_stitches(board,fps,objects)
    power_backbones(board,objects)
    for layer in [k.F_Cu,k.B_Cu]:rectangle_zone(board,'GND pour '+k.LayerName(layer),layer,(.3,.3,29.7,29.7),ground)
    text(board,'CH340C USB / UART',(18.5,26.8),.85)
    text(board,'1:3V3 2:TX 3:RX 4:GND',(19,29.0),.8)
    text(board,'3V3 OUT',(25,2.5),.8);text(board,'50mA MAX',(25,3.8),.8)
    for ref,pos in [('J1',(7,3)),('U1',(23,20.0)),('D1',(11.7,10.7)),('U2',(3.1,19.8)),('F1',(3.0,11)),('J2',(10.0,27.4)),('D2',(3.4,24.1))]:text(board,ref,pos,.8)
    for ref in ('TP1','TP2','TP3','TP4'):
        p=PLACEMENTS[ref];text(board,plain(next(c['value'] for c in data['components'] if c['ref']==ref)),(25,p[1]-1.3),.8)
    print('Saving initial board',flush=True)
    board.BuildConnectivity();k.SaveBoard(str(ROOT/(NAME+'.kicad_pcb')),board)
    (ROOT/(NAME+'.kicad_pro')).write_text(project_text)
    # Reload attaches the saved project's settings; filling a detached freshly
    # constructed SWIG board can crash native KiCad 9's multithreaded filler.
    board=k.LoadBoard(str(ROOT/(NAME+'.kicad_pcb')))
    # Load project-based netclasses into the SWIG object before DSN export.
    sys.path.insert(0,'/workspace/pcb-tooling/vendor/KiCAD-MCP-Server/python')
    from utils.project_netclasses import load_project_net_classes,apply_net_classes_to_board
    apply_net_classes_to_board(board,load_project_net_classes(str(ROOT/(NAME+'.kicad_pro'))))
    k.SaveBoard(str(ROOT/(NAME+'.kicad_pcb')),board)
    print('Filling initial ground zones',flush=True)
    k.ZONE_FILLER(board).Fill(board.Zones());k.SaveBoard(str(ROOT/(NAME+'.kicad_pcb')),board)
    (ROOT/(NAME+'.kicad_pro')).write_text(project_text)
    (ROOT/'placements.json').write_text(json.dumps({ref:{'x':p[0],'y':p[1],'rotation':p[2]} for ref,p in PLACEMENTS.items()},indent=2)+'\n')
    return board

def route(board):
    folder=ROOT/'analysis'/'routing';folder.mkdir(parents=True,exist_ok=True)
    dsn=folder/(NAME+'.dsn');ses=folder/(NAME+'.ses')
    if not k.ExportSpecctraDSN(board,str(dsn)):raise RuntimeError('Native DSN export failed')
    # Ground is already connected by stitched, filled planes; preserve that geometry.
    cmd=['java','-Xmx2g','-jar','/workspace/pcb-tooling/freerouting/freerouting-2.1.0.jar','-de',str(dsn),'-do',str(ses),'--gui.enabled=false','--router.max_passes=40','--router.stop_pass_no=40','-da','-mp','40','-mt','0','-inc','Ground']
    with (folder/'freerouting.log').open('w') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    if result.returncode or not ses.is_file():raise RuntimeError('Freerouting failed; inspect routing/freerouting.log')
    # Upstream helper strips placement because authoring has already fixed it.
    from commands.freerouting import _strip_ses_placement
    ses.write_text(_strip_ses_placement(ses.read_text()))
    if not k.ImportSpecctraSES(board,str(ses)):raise RuntimeError('Native SES import failed')
    board.BuildConnectivity();k.ZONE_FILLER(board).Fill(board.Zones());k.SaveBoard(str(ROOT/(NAME+'.kicad_pcb')),board)
    project_rules({n.GetNetname():n.GetNetCode() for n in board.GetNetInfo().NetsByNetcode().values() if n.GetNetCode()>0})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--route',action='store_true');a=ap.parse_args()
    b=build()
    if a.route:route(b)
    print(ROOT/(NAME+'.kicad_pcb'))
