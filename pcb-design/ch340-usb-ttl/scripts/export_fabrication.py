#!/usr/bin/env python3
"""Export native KiCad fabrication outputs using one common auxiliary origin."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/'ch340-usb-ttl.kicad_pcb'
CLI=['/workspace/pcb-tooling/bin/with-kicad-env','kicad-cli']
EXPORT=ROOT/'exports'
commands=[
 ['pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Paste,F.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
  '--use-drill-file-origin','--output',str(EXPORT/'gerbers')+'/',str(BOARD)],
 ['pcb','export','drill','--format','excellon','--drill-origin','plot','--excellon-units','mm',
  '--excellon-separate-th','--generate-map','--map-format','svg','--output',str(EXPORT/'drill')+'/',str(BOARD)],
 ['pcb','export','pos','--side','front','--format','csv','--units','mm','--use-drill-file-origin',
  '--exclude-dnp','--output',str(EXPORT/'ch340-usb-ttl-top-pos.csv'),str(BOARD)],
]
for cmd in commands:subprocess.run(CLI+cmd,check=True,cwd=ROOT)
files=[]
for directory in [EXPORT/'gerbers',EXPORT/'drill']:
 for p in sorted(directory.iterdir()):
  if p.is_file():files.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
pos=EXPORT/'ch340-usb-ttl-top-pos.csv'
files.append({'path':str(pos.relative_to(ROOT)),'bytes':pos.stat().st_size,'sha256':hashlib.sha256(pos.read_bytes()).hexdigest()})
report={'source_board_sha256':hashlib.sha256(BOARD.read_bytes()).hexdigest(),
        'origin':'Shared KiCad auxiliary origin at board-local (0,0); native export axis conventions are retained',
        'commands':commands,'files':files}
(ROOT/'analysis/fabrication-export.json').write_text(json.dumps(report,indent=2)+'\n')
print('Wrote',len(files),'fabrication/placement artifacts')
