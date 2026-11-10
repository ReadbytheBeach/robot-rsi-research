#!/usr/bin/env python3
"""Package only a natively checked release, omitting intermediate build artifacts."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
validation=json.loads((ROOT/'analysis/requirements-validation.json').read_text())
if validation.get('status')!='passed':raise SystemExit('Requirements validation has not passed')
for required in ['ch340-usb-ttl.kicad_pro','ch340-usb-ttl.kicad_sch','ch340-usb-ttl.kicad_pcb',
                 'README.zh-CN.md','REVIEW.zh-CN.md','FABRICATION.zh-CN.md','BOM.csv']:
 if not (ROOT/required).is_file():raise SystemExit(f'Missing release artifact: {required}')
if '等待最终 PCB' in (ROOT/'REVIEW.zh-CN.md').read_text():raise SystemExit('Review is still a draft')
fabrication=json.loads((ROOT/'analysis/fabrication-export.json').read_text())
if fabrication.get('source_board_sha256')!=hashlib.sha256((ROOT/'ch340-usb-ttl.kicad_pcb').read_bytes()).hexdigest():
 raise SystemExit('Fabrication export does not match the current PCB')
for artifact in fabrication['files']:
 p=ROOT/artifact['path']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=artifact['sha256']:
  raise SystemExit(f'Fabrication artifact changed: {p}')

fab_dirs=[p for p in [ROOT/'exports/gerbers',ROOT/'exports/drill'] if p.is_dir()]
if len(fab_dirs)!=2:raise SystemExit('Missing Gerber/drill output directories')
fab=ROOT/'exports/CH340C_USB_TTL_RevA_Gerber.zip'
with zipfile.ZipFile(fab,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for d in fab_dirs:
  for p in sorted(d.rglob('*')):
   if p.is_file():z.write(p,str(p.relative_to(ROOT/'exports')))
 z.write(ROOT/'FABRICATION.zh-CN.md','FABRICATION.zh-CN.md')

files=[]
for p in ROOT.iterdir():
 if p.is_file() and (p.suffix in {'.kicad_sch','.kicad_pcb','.kicad_pro','.kicad_dru','.kicad_sym','.net','.md','.json','.csv'} or p.name in {'sym-lib-table','fp-lib-table'}):
  if p.name!='RELEASE-MANIFEST.json':files.append(p)
for name in ['datasheets','3dmodels','references','exports','scripts']:
 for p in (ROOT/name).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith(('.pyc','.partial')):files.append(p)
for p in (ROOT/'analysis').rglob('*'):
 if not p.is_file() or p.suffix not in {'.json','.py','.cir','.log','.out'}:continue
 if '.prev.' in p.name:continue
 if any(x in str(p.relative_to(ROOT/'analysis')).lower() for x in ['preliminary','initial-drc','mcp-','routing/','build-seed']):continue
 files.append(p)
files=sorted(set(files))
manifest={'revision':'A','date':'2026-11-10 Asia/Singapore','requirements_validation':'passed',
          'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
mp=ROOT/'RELEASE-MANIFEST.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');files.append(mp)
target=ROOT.parent/'CH340C_USB_TTL_30x30_RevA.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in files:z.write(p,str(Path(ROOT.name)/p.relative_to(ROOT)))
with zipfile.ZipFile(target) as z:
 if z.testzip() is not None:raise SystemExit('Archive integrity failure')
print(json.dumps({'project_archive':str(target),'gerber_archive':str(fab),
                  'files':len(files),'bytes':target.stat().st_size,
                  'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2))
