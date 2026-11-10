#!/usr/bin/env python3
"""Review calculations and native-netlist checks; this does not simulate the ICs."""
from pathlib import Path
import json,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
tree=ET.parse(ROOT/'ch340-usb-ttl.net')
pin_net={}
for net in tree.findall('./nets/net'):
    for p in net.findall('node'):
        pin_net[p.attrib['ref'],p.attrib['pin']]=net.attrib['name'].lstrip('/')
requirements={
 'U1':{'1':'GND','2':'UART_TX','3':'UART_RX','4':'+3V3','5':'USB_D+','6':'USB_D-','16':'+3V3'},
 'U2':{'1':'+5V_FUSED','2':'GND','3':'+5V_FUSED','5':'+3V3'},
 'D1':{'1':'USB_D+','2':'GND','3':'USB_D-','4':'USB_D-','5':'+5V_USB','6':'USB_D+'},
 'J2':{'1':'+3V3','2':'UART_TX','3':'UART_RX','4':'GND'},
 'R1':{'1':'CC1','2':'GND'},'R2':{'1':'CC2','2':'GND'},
 'R3':{'1':'+3V3','2':'LED_A'},'D2':{'1':'GND','2':'LED_A'},
 'F1':{'1':'+5V_USB','2':'+5V_FUSED'},
}
errors=[]
for ref,pins in requirements.items():
    for pin,net in pins.items():
        if pin_net.get((ref,pin))!=net:errors.append([ref,pin,net,pin_net.get((ref,pin))])
for ref,pins in {'U1':['7','8','9','10','11','12','13','14','15'],'U2':['4'],'J1':['A8','B8']}.items():
    for pin in pins:
        if (ref,pin) in pin_net and not pin_net[ref,pin].startswith('unconnected-('):
            errors.append([ref,pin,'expected no-connect',pin_net[ref,pin]])
for pin in ['A6','B6']:
    if pin_net.get(('J1',pin))!='USB_D+':errors.append(['J1',pin,'USB_D+'])
for pin in ['A7','B7']:
    if pin_net.get(('J1',pin))!='USB_D-':errors.append(['J1',pin,'USB_D-'])
for pin,net in [('A5','CC1'),('B5','CC2')]:
    if pin_net.get(('J1',pin))!=net:errors.append(['J1',pin,net])
vnom=3.3
vmin=vnom*(1-.015)
vmax=vnom*(1+.015)
# Upper bound ignores LED forward voltage, so it is conservative.
iled=vmax/(1000*(1-.01))
iout=.050+.012+iled
iq=.000100 # conservative rounded budget; AP2112 table max Iq is 80 uA.
pd=(5.25-vmin)*iout+5.25*iq
report={
 'native_netlist_required_connections':{'status':'passed' if not errors else 'failed','errors':errors},
 'power_budget':{
   'external_3v3_mA':50,'ch340c_max_mA':12,'led_conservative_upper_mA':iled*1000,
   'ldo_iq_budget_mA':iq*1000,'usb_dc_total_upper_mA':(iout+iq)*1000,
   'output_nominal_V':vnom,'output_1p5pct_range_V':[vmin,vmax],
   'ch340c_3v3_allowed_range_V':[3.1,3.6],
   'ldo_dissipation_at_USB5p25V_W':pd,'thetaJA_datasheet_C_per_W':184,
   'junction_rise_estimate_C':pd*184,'ambient_assumption_C':50,
   'junction_estimate_at_ambient50_C':50+pd*184,
 },
 'limits':[
   'DC and first-order thermal calculations only; not measured board temperatures.',
   'Output tolerance is the stated AP2112 accuracy basis; load/temperature/board effects need bring-up measurement.',
   'Capacitor effective capacitance under DC bias has not been measured.',
   'No USB suspend load gating: external 3.3V output and LED remain powered; suspend-current compliance not established.',
   'No USB enumeration, hotplug inrush, ESD, or complete active-chip SPICE validation.',
 ]
}
(ROOT/'analysis/review-electrical-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(bool(errors))
