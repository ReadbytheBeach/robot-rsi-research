#!/usr/bin/env python3
"""Generate the CH340C design via the prepared MCP plus deterministic net wiring.

Run with the prepared KiCad MCP Python venv. Generated files are rebuilt from
this specification; edit the specification rather than the generated schematic.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import uuid

import sexpdata
from sexpdata import Symbol as S

ROOT = Path(__file__).resolve().parents[1]
TOOL = Path('/workspace/pcb-tooling')
sys.path.insert(0, str(TOOL/'vendor/KiCAD-MCP-Server/python'))
from utils.sexpr_format import dumps


def node(name, *args):
    return [S(name), *args]


def child(parent, name):
    return next((x for x in parent if isinstance(x, list) and x and str(x[0]) == name), None)


def children(parent, name):
    return [x for x in parent if isinstance(x, list) and x and str(x[0]) == name]


def uid():
    return str(uuid.uuid4())


def part(ref, symbol, value, footprint, pos, pins, mpn, manufacturer, datasheet=''):
    return dict(ref=ref, symbol=symbol, value=value, footprint=footprint,
                pos=pos, pins=pins, mpn=mpn, manufacturer=manufacturer, datasheet=datasheet)


PARTS = [
 part('J1','Connector:USB_C_Receptacle_USB2.0_16P','USB-C USB2.0',
      'Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',[38.1,66.04],
      {'S1':'GND','A1':'GND','A12':'GND','B1':'GND','B12':'GND',
       'A4':'+5V_USB','A9':'+5V_USB','B4':'+5V_USB','B9':'+5V_USB',
       'A5':'CC1','B5':'CC2','A6':'USB_D+','B6':'USB_D+','A7':'USB_D-','B7':'USB_D-',
       'A8':None,'B8':None},'USB4105-GF-A','GCT','https://gct.co/files/drawings/usb4105.pdf'),
 part('U1','Interface_USB:CH340C','CH340C',
      'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm',[152.4,66.04],
      {'1':'GND','2':'UART_TX','3':'UART_RX','4':'+3V3','5':'USB_D+','6':'USB_D-',
       '7':None,'8':None,'9':None,'10':None,'11':None,'12':None,'13':None,'14':None,
       '15':None,'16':'+3V3'},'CH340C','WCH','https://www.wch-ic.com/downloads/CH340DS1_PDF.html'),
 part('J2','Connector_Generic:Conn_01x04','TTL 3V3 TX RX GND',
      'Connector_JST:JST_SUR_SM04B-SURS-TF_1x04-1MP_P0.80mm_Horizontal',[238.76,66.04],
      {'1':'+3V3','2':'UART_TX','3':'UART_RX','4':'GND'},'SM04B-SURS-TF(LF)(SN)','JST',
      'https://www.jst-mfg.com/product/pdf/eng/eSUR.pdf'),
 part('D1','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',
      'Package_TO_SOT_SMD:SOT-23-6',[93.98,66.04],
      {'1':'USB_D+','2':'GND','3':'USB_D-','4':'USB_D-','5':'+5V_USB','6':'USB_D+'},
      'USBLC6-2SC6','STMicroelectronics','https://www.st.com/resource/en/datasheet/usblc6-2.pdf'),
 part('F1','Device:Polyfuse','500mA hold',
      'Fuse:Fuse_1812_4532Metric',[45.72,127.0],
      {'1':'+5V_USB','2':'+5V_FUSED'},'MF-MSMF050-2','Bourns',
      'https://www.bourns.com/docs/product-datasheets/mfmsmf.pdf'),
 part('U2','Regulator_Linear:AP2112K-3.3','AP2112K-3.3',
      'Package_TO_SOT_SMD:SOT-23-5',[91.44,127.0],
      {'1':'+5V_FUSED','2':'GND','3':'+5V_FUSED','4':None,'5':'+3V3'},
      'AP2112K-3.3TRG1','Diodes Incorporated','https://www.diodes.com/assets/Datasheets/AP2112.pdf'),
 part('R1','Device:R','5.1k 1%','Resistor_SMD:R_0603_1608Metric',[63.5,104.14],
      {'1':'CC1','2':'GND'},'RC0603FR-075K1L','Yageo'),
 part('R2','Device:R','5.1k 1%','Resistor_SMD:R_0603_1608Metric',[81.28,104.14],
      {'1':'CC2','2':'GND'},'RC0603FR-075K1L','Yageo'),
 part('R3','Device:R','1k 1%','Resistor_SMD:R_0603_1608Metric',[182.88,127.0],
      {'1':'+3V3','2':'LED_A'},'RC0603FR-071KL','Yageo'),
 part('D2','Device:LED','GREEN','LED_SMD:LED_0603_1608Metric',[205.74,127.0],
      {'1':'GND','2':'LED_A'},'LTST-C190KGKT','Lite-On'),
]

for ref,value,mpn,pos,power in [
 ('C1','1uF 16V','C1608X7R1C105K080AC',[25.4,127.0],'+5V_USB'),
 ('C2','4.7uF 16V','C1608X5R1C475K080AC',[66.04,142.24],'+5V_FUSED'),
 ('C3','4.7uF 10V','C1608X5R1A475K080AC',[124.46,127.0],'+3V3'),
 ('C4','100nF 50V','C1608X7R1H104K080AA',[144.78,127.0],'+3V3'),
 ('C5','100nF 50V','C1608X7R1H104K080AA',[162.56,127.0],'+3V3'),
]:
    PARTS.append(part(ref,'Device:C',value,'Capacitor_SMD:C_0603_1608Metric',pos,
                      {'1':power,'2':'GND'},mpn,'TDK'))

for i,(net,pos) in enumerate([('+3V3',[213.36,93.98]),('GND',[236.22,93.98]),
                             ('UART_TX',[213.36,106.68]),('UART_RX',[236.22,106.68])],1):
    PARTS.append(part(f'TP{i}','Connector:TestPoint',net,'TestPoint:TestPoint_Pad_D1.0mm',pos,
                      {'1':net},'PCB TEST PAD','PCB copper'))

for i,(net,pos) in enumerate([('+5V_USB',[25.4,156.21]),('+5V_FUSED',[55.88,156.21]),
                             ('GND',[86.36,156.21])],1):
    PARTS.append(part(f'#FLG0{i}','power:PWR_FLAG','PWR_FLAG','',pos,
                      {'1':net},'',''))


def set_property(sym, name, value, at=None, hidden=False):
    prop=next((p for p in children(sym,'property') if str(p[1])==name),None)
    if prop is None:
        prop=node('property',name,value,node('at',*(at or [0,0]),0),
                  node('effects',node('font',node('size',1,1)),*[node('hide',S('yes'))] if hidden else []))
        sym.append(prop)
    else:
        prop[2]=value


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/'analysis').mkdir(exist_ok=True)
    target=ROOT/'ch340-usb-ttl.kicad_sch'
    scratch=ROOT/'analysis/build-seed.kicad_sch'
    scratch.unlink(missing_ok=True)
    subprocess.run([str(TOOL/'bin/new-kicad9-schematic'),str(scratch)],check=True)
    calls=[{'name':'add_schematic_component','arguments':dict(schematicPath=str(scratch),
            symbol=p['symbol'],reference=p['ref'],value=p['value'],
            footprint=p['footprint'],position=dict(zip(['x','y'],p['pos'])))} for p in PARTS]
    cp=ROOT/'analysis/mcp-schematic-calls.json'
    cp.write_text(json.dumps(calls,indent=2)+'\n')
    subprocess.run([str(TOOL/'bin/kicad-mcp-call'),'--allow-write','--calls',str(cp),
                    '--output',str(ROOT/'analysis/mcp-schematic-result.json')],check=True,
                   stdout=subprocess.DEVNULL)
    tree=sexpdata.loads(scratch.read_text())
    root_uuid=str(child(tree,'uuid')[1])
    lib=child(tree,'lib_symbols')
    spec={p['ref']:p for p in PARTS}
    # V3 is supplied externally in the selected 3.3V mode, not used as LDO output.
    chip=next(s for s in children(lib,'symbol') if str(s[1])=='Interface_USB:CH340C')
    chip[1]='CH340_USB_TTL:CH340C_3V3'
    for unit in children(chip,'symbol'):
        unit[1]=str(unit[1]).replace('CH340C_','CH340C_3V3_')
        for pin in children(unit,'pin'):
            if str(child(pin,'number')[1])=='4':pin[1]=S('power_in')
            if str(child(pin,'number')[1])=='8':
                pin[1]=S('output')
                child(pin,'name')[1]='~{OUT}'
                pin[:]=[x for x in pin if not (isinstance(x,list) and x and str(x[0])=='hide')]
    set_property(chip,'Description','CH340C; VCC and V3 externally supplied 3.3V mode')
    local=copy.deepcopy(chip);local[1]='CH340C_3V3'
    (ROOT/'CH340_USB_TTL.kicad_sym').write_text(dumps(node('kicad_symbol_lib',
        node('version',20241209),node('generator','kicad_symbol_editor'),local)))
    (ROOT/'sym-lib-table').write_text('(sym_lib_table\n (version 7)\n (lib (name "CH340_USB_TTL")(type "KiCad")(uri "${KIPRJMOD}/CH340_USB_TTL.kicad_sym")(options "")(descr "CH340C configured for external 3.3V supply"))\n)\n')
    all_lib={str(s[1]):s for s in children(lib,'symbol')}
    wiring=[];manifest=[]
    for inst in children(tree,'symbol'):
        props={str(p[1]):str(p[2]) for p in children(inst,'property')}
        ref=props['Reference'];p=spec[ref]
        if ref.startswith('TP'):child(inst,'in_bom')[1]=S('no')
        if ref=='U1':child(inst,'lib_id')[1]='CH340_USB_TTL:CH340C_3V3'
        lib_id=str(child(inst,'lib_id')[1]);defs=all_lib[lib_id]
        x0,y0=map(float,child(inst,'at')[1:3])
        set_property(inst,'MPN',p['mpn'],[x0,y0],True)
        set_property(inst,'Manufacturer',p['manufacturer'],[x0,y0],True)
        if p['datasheet']:set_property(inst,'Datasheet',p['datasheet'])
        set_property(inst,'Reference',ref)
        # Place reference and value away from pins; keep readable after native export.
        for name,dy in [('Reference',-5.08),('Value',-2.54)]:
            pr=next(pr for pr in children(inst,'property') if str(pr[1])==name)
            at=child(pr,'at');at[1:]=[x0+1.27,y0+dy,0]
        pin_defs=[]
        for unit in children(defs,'symbol'):
            pin_defs+=children(unit,'pin')
        occupied={}
        for pin in pin_defs:
            number=str(child(pin,'number')[1])
            if number not in p['pins']:raise ValueError(f'{ref} missing pin specification {number}')
            net=p['pins'][number]
            px,py,angle=map(float,child(pin,'at')[1:4])
            x,y=round(x0+px,4),round(y0-py,4)
            if net is None:
                wiring.append(node('no_connect',node('at',x,y),node('uuid',uid())))
                continue
            if (x,y) in occupied:
                assert occupied[x,y]==net
                continue
            occupied[x,y]=net
            direction={0:(-1,0),180:(1,0),90:(0,1),270:(0,-1)}[int(angle)%360]
            length=5.08
            xe,ye=round(x+direction[0]*length,4),round(y+direction[1]*length,4)
            wiring.append(node('wire',node('pts',node('xy',x,y),node('xy',xe,ye)),
                               node('stroke',node('width',0),node('type',S('default'))),node('uuid',uid())))
            label_angle=0 if direction[0]>=0 else 180
            justify=S('left') if label_angle==0 else S('right')
            wiring.append(node('label',net,node('at',xe,ye,label_angle),
                               node('effects',node('font',node('size',1,1)),node('justify',justify)),node('uuid',uid())))
        if not ref.startswith('#'):
            record={k:v for k,v in p.items() if k!='pos'}
            record['uuid']=str(child(inst,'uuid')[1])
            record['schematic_path']='/'+root_uuid+'/'+record['uuid']
            manifest.append(record)
    tree.extend(wiring)
    tree.append(node('title_block',node('title','CH340C USB-C to 3.3V TTL UART'),
                     node('date','2026-11-10'),node('rev','A'),node('company','30 x 30 mm / 2 layers / 1.0 mm')))
    for text,pos in [
        ('USB-C DEVICE / CC1 AND CC2: SEPARATE 5.1k Rd',[25.4,30.48]),
        ('CH340C: INTERNAL CLOCK / VCC=V3=3.3V',[134.62,30.48]),
        ('J2: 1=3V3  2=TX  3=RX  4=GND',[205.74,38.1]),
        ('TX/RX named from THIS adapter; TX to target RX',[187.96,83.82]),
        ('USB 5V -> PTC -> LDO 3V3; external output design budget 50 mA',[25.4,172.72]),
        ('USB D+/D- direct: no series resistors; target 90 ohm differential',[25.4,182.88]),
        ('Internal clock; unused I/O left open per WCH. Use UART without hardware flow control.',[25.4,190.5]),
    ]:
        tree.append(node('text',text,node('at',*pos,0),
                         node('effects',node('font',node('size',1.27,1.27)),node('justify',S('left'))),node('uuid',uid())))
    target.write_text(dumps(tree))
    (ROOT/'design.json').write_text(json.dumps(dict(project='ch340-usb-ttl',
        requirements=dict(width_mm=30,height_mm=30,thickness_mm=1.0,copper_layers=2,
                          populated_side='F.Cu',right_angle_tracks=False,usb_diff_ohms=90,
                          uart='single 3.3V UART',connector_pinout=['3V3','TX','RX','GND'],
                          external_3v3_budget_ma=50),
        root_uuid=root_uuid,components=manifest),indent=2)+'\n')
    print(target)


if __name__=='__main__':main()
