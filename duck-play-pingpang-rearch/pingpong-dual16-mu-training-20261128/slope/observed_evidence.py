"""Render the largest gain and loss for the frozen paired blind comparison."""
import subprocess
import sys
from unittest.mock import patch
from action_transfer import DEST, TIMED, episode
from high_slope import HERE, OLD, read


def main():
    selected=read(DEST/'seal.json')['selected']
    held=read(DEST/'blind-rows.json')
    get=lambda p:{x['seed']:x for x in held if x['recipe']==p['name']}
    baseline,observed=get(TIMED),get(selected)
    ordered=sorted(baseline,key=lambda k:observed[k]['last_both_m']-baseline[k]['last_both_m'])
    clips=[]
    for kind,label,seed in [('gain','改善最多',ordered[-1]),('loss','退步最多',ordered[0])]:
        for p,name in [(TIMED,'定时'),(selected,'观测')]:
            stem=kind+'-'+p['name']
            trace=DEST/(stem+'.npz');movie=DEST/(stem+'.mp4')
            row=episode((p,seed),trace=trace)
            assert row==get(p)[seed]
            title=f'{label} · {seed} · {name} · 最后双球接触 {row["last_both_m"]:.3f} m'
            subprocess.run([sys.executable,str(HERE/'observed_evidence.py'),'--render',stem,title],check=True)
            clips.append((movie,row['seconds']))
    dest=DEST/'paired-extremes.mp4'
    cmd=['ffmpeg','-nostdin','-v','error','-y']
    longest=max(s for p,s in clips)+.08
    for p,_ in clips:cmd+=['-i',str(p)]
    filters=[f'[{i}:v]scale=768:444,tpad=stop_mode=clone:stop_duration={longest},trim=duration={longest},setpts=PTS-STARTPTS[v{i}]' for i in range(4)]
    filters+=['[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[out]']
    cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-c:v','libx264','-pix_fmt','yuv420p','-crf','20','-movflags','+faststart',str(dest)]
    subprocess.run(cmd,check=True)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(dest),'-f','null','-'],check=True)
    print('comparison',dest,ordered[-1],ordered[0],flush=True)


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--render':
        sys.path.insert(0,str(OLD/'media'))
        import film
        stem,title=sys.argv[2:]
        with patch.object(film,'ROOT',DEST):
            film.encode(DEST/(stem+'.npz'),DEST/(stem+'.mp4'),title,rate=25.)
    else:
        main()
