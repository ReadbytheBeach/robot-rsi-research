"""Replay the two largest opposite paired friction effects, at true time."""
from contextlib import ExitStack
from pathlib import Path
import csv
import hashlib
import sys
import subprocess
import numpy as np
import mujoco
from PIL import Image,ImageDraw,ImageFont
from material import HERE,PILOT,RECIPE,save,short_track,study,surface
sys.path.insert(0,str(HERE.parent/'pingpong-speed-small-20261127'))
import movies as mv

OUT=HERE/'media';OUT.mkdir(exist_ok=True)


def main():
    data=list(csv.DictReader((HERE/'friction/medium-paired.csv').open()))
    arms=('fixed-0.224000','fixed-0.416000')
    rows={a:{int(r['seed']):float(r['last_both_m']) for r in data if r['arm']==a} for a in arms}
    differences={s:rows[arms[0]][s]-rows[arms[1]][s] for s in rows[arms[0]]}
    seeds=[max(differences,key=differences.get),min(differences,key=differences.get)]
    assert differences[seeds[0]]>0>differences[seeds[1]]
    panels=[];meta=[]
    fonts={n:ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',n) for n in (15,18,22,24)}
    with ExitStack() as resources:
        for s in seeds:
            for mat,mu,field in zip(('low','high'),(.224,.416),arms):
                path=OUT/f'medium-{s}-{mat}.npz'
                with surface(mat):
                    result=study.episode(('medium',RECIPE,'combined',s,path,None))
                assert abs(result['last_both_m']-rows[field][s])<1e-10
                with np.load(path) as archive:trace={k:v.copy() for k,v in archive.items() if k in ('t','qpos','progress_m','ball_contacts','ball_radii')}
                import json
                origin=json.loads(path.with_suffix('.json').read_text())['track_origin_x_m']
                model=short_track.render_model('combined',origin)
                mv.compact_visual_meshes(model,1.);model.vis.quality.offsamples=1
                dd=mujoco.MjData(model);rend=resources.enter_context(mujoco.Renderer(model,171,297))
                cam=mv.camera([0.,0.,.14],.54,140,-16)
                panels.append((s,mu,result,trace,model,dd,rend,cam))
                meta.append(dict(seed=s,mu=mu,last_m=result['last_both_m'],seconds=result['seconds'],trace=path.name))
        opt=mujoco.MjvOption();opt.geomgroup[3:]=0;opt.sitegroup[:]=0
        w,h=1040,566;duration=max(p[2]['seconds'] for p in panels)
        frames=1+int(np.ceil(duration*25));tmp=OUT/'endpoint-comparison.part.mp4';dest=OUT/'endpoint-comparison.mp4'
        cmd=['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r','25','-i','-','-an','-c:v','libx264','-preset','veryfast','-threads','2','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        panel_cache={}
        for frame in range(frames):
            im=Image.new('RGB',(w,h),'#17282b');d=ImageDraw.Draw(im)
            d.text((15,6),'同一控制与起点，比较原范围内的最低、最高滑动摩擦',font=fonts[24],fill='#eaf2ee')
            d.text((16,42),'各行对应一个新起点。选取两端摩擦效果差异最大的正反两例。',font=fonts[18],fill='#b4d0c5')
            for j,(seed,mu,result,z,m,dd,rend,cam) in enumerate(panels):
                x=14+(j%2)*513;y=80+(j//2)*232
                i=min(2*frame,len(z['t'])-1);last=i==len(z['t'])-1
                d.text((x,y),f'起点 {seed}  ·  μ = {mu:.3f}',font=fonts[18],fill='#d5ece0')
                if (j,i) not in panel_cache:
                    dd.qpos[:]=z['qpos'][i];mujoco.mj_kinematics(m,dd);mujoco.mj_camlight(m,dd)
                    face=dd.site_xpos[m.site('paddle_center').id];base=dd.xpos[m.body('trunk_base').id]
                    cam.lookat[:]=.65*base+.35*face;rend.update_scene(dd,camera=cam,scene_option=opt)
                    panel_cache[j,i]=Image.fromarray(rend.render())
                im.paste(panel_cache[j,i],(x,y+30))
                tx=x+306;green='#9ae2be'
                d.text((tx,y+37),f"{z['t'][i]:.2f} 秒",font=fonts[22],fill=green)
                d.text((tx,y+73),f"机身 {z['progress_m'][i]:.3f} 米",font=fonts[18],fill='#edf2e7')
                d.text((tx,y+108),'终止定格' if last else '回合进行中',font=fonts[18],fill='#edc18e' if last else '#b3c5b9')
                on='／'.join('触拍' if v else '离拍' for v in z['ball_contacts'][i])
                d.text((tx,y+139),f'A、B  {on}',font=fonts[15],fill='#ced8cf')
                d.text((tx,y+172),f"末次双触 {result['last_both_m']:.3f} 米",font=fonts[15],fill=green)
            d.text((16,542),'主赛道  ·  从真实释放起算  ·  两颗 16 mm 自由球  ·  40 g 平拍  ·  原速 25 帧/秒',font=fonts[15],fill='#aec8bd')
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
        if proc.wait():raise RuntimeError('ffmpeg failed')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(tmp),'-f','null','-'],check=True);tmp.replace(dest)
    save(OUT/'endpoint-comparison.json',dict(protocol='opposite extremes from same 144 paired seeds, examples only',panels=meta,
           fps=25,frames=frames,sha=hashlib.sha256(dest.read_bytes()).hexdigest()))


if __name__=='__main__':main()
