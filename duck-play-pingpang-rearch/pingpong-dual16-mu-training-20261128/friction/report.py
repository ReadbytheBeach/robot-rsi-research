"""Render the frozen friction sweep and verify the paired raw scores."""
import csv
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np

HERE=Path(__file__).resolve().parent
COLORS={'teacher':'#166177','medium':'#b64a23'}
NAMES={'teacher':'纪录动作','medium':'中档步态'}
MAX_ARM='fixed-0.416000'
plt.rcParams['font.family']=FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc').get_name()
plt.rcParams['axes.unicode_minus']=False


def main():
    s=json.loads((HERE/'summary.json').read_text())
    record=json.loads((HERE/'opened.json').read_text())
    audit=json.loads((HERE/'contact-audit.json').read_text())
    protocol=json.loads((HERE/'protocol.json').read_text())
    arms=protocol['arms']
    fixed=[k for k in arms if k.startswith('fixed-')]
    labels=[('纪录值\n0.364467' if abs(arms[k]-.36446)<.0001 else f'{arms[k]:.3f}') for k in fixed]
    n=protocol['n']
    contact_means={}
    for arm in ['fixed-0.224000',MAX_ARM]:
        matched=[run for run in audit['runs'] if run['row']['track']=='combined' and run['row']['arm']==arm]
        assert len(matched)==12
        intervals=[m['first_200ms'] for r in matched for k,m in r['observations'].items() if k.endswith('_face')]
        weights=[m['n_loaded'] for m in intervals]
        contact_means[arm]={key:np.average([m[key] for m in intervals],weights=weights)
                            for key in ('mean_tangential_mN','mean_scalar_bound_mN')}
    for policy,groups in s.items():
        with (HERE/f'{policy}-paired.csv').open() as f:
            rows=list(csv.DictReader(f))
        for arm,stat in groups.items():
            tagged=[r for r in rows if r['arm']==arm]
            assert len({r['seed'] for r in tagged})==len(tagged)==stat['n']==n
            assert abs(stat['mean_m']-np.mean([float(r['last_both_m']) for r in tagged]))<1e-12
            for key in ['half_m','alive_2s','both_2s','flat','slope','finish']:
                assert stat[key]==sum(r[key]=='True' for r in tagged)
    xs=np.arange(len(fixed))
    fig,(known,blind,diff)=plt.subplots(3,1,figsize=(9.8,8.4),gridspec_kw={'height_ratios':[1,1.13,1.15]},layout='constrained')
    fig.suptitle('球与拍面滑动摩擦系数对有效里程的影响',fontsize=18)
    for ax in (known,blind,diff):
        ax.spines[['top','right']].set_visible(False)
        ax.set_xticks(xs,labels);ax.set_xlim(-.4,len(fixed)-.6)
        ax.grid(axis='y',color='#d5dedd',linewidth=.6,zorder=0)
    one={r['arm']:r for r in record}
    known.bar(xs,[one[k]['last_both_m'] for k in fixed],width=.48,color=['#b4c8ca' if i!=3 else '#166177' for i in xs],zorder=2)
    known.set_ylim(0,1.6);known.set_ylabel('米')
    known.set_title('已知起点 12600381，固定网格，纪录动作',loc='left')
    for i,k in enumerate(fixed):
        y=one[k]['last_both_m']
        known.text(i,y+.035,f'{y:.3f}',ha='center',fontsize=9)
    blind.set_title(f'主赛道 {n} 个新起点，各策略的平均末次双球触拍里程',loc='left')
    blind.set_ylabel('厘米')
    for i,(policy,groups) in enumerate(s.items()):
        x=xs+(i-.5)*.18
        means=[groups[k]['mean_m']*100 for k in fixed]
        blind.scatter(x,means,label=NAMES[policy],color=COLORS[policy],marker=('o','s')[i],zorder=3)
        effect=[groups[k]['paired_diff_mm_vs_'+MAX_ARM] for k in fixed]
        y=np.array([r['mean'] for r in effect]);b=np.array([r['ci95'] for r in effect])
        diff.errorbar(x,y,yerr=[y-b[:,0],b[:,1]-y],fmt=('o','s')[i],color=COLORS[policy],capsize=3)
    blind.set_ylim(0,max(max(v[k]['mean_m'] for k in fixed) for v in s.values())*110+1)
    blind.legend(frameon=False,ncol=2,loc='lower left')
    diff.axhline(0,color='#536468',lw=1)
    diff.set_title('相对于同一起点 μ=0.416 的平均里程差，误差线为配对自助法 95% 区间',loc='left')
    diff.set_ylabel('毫米');diff.set_xlabel('固定球–拍滑动摩擦系数 μ')
    fig.savefig(HERE/'sliding-friction-sweep.png',dpi=155);plt.close(fig)
    body=['# 平拍双球的滑动摩擦扫描与真实接触力',
          f'按主赛道释放点计程，先平地一米、再上 1° 坡一米、最后平台半米并持球停一秒。7 个固定摩擦值、原宽随机组和高位窄带共 9 组，每组在相同的 {n} 个新自然起点上分别跑两套冻结动作。统计双球末次同时触拍的横向前进里程与物理门槛。有任一违规便停止计分。球–球摩擦、法向、扭转与滚动接触、原始扰动、电机限幅都保持原值。高位窄带将原有效滑动系数线性映入 [0.406,0.416]。',
          '[各固定摩擦的里程和配对差异图](sliding-friction-sweep.png) · [试验协议](protocol.json) · [逐项统计](summary.json)',
          '## 同一批新起点',
          '| 控制 | 滑动系数 | 平均里程（厘米） | 相对0.416的平均差及95%区间（毫米） | 最远（米） | 过2秒／2秒同触 | 同触过半米／平一米／坡顶／停车 |',
          '|---|---:|---:|---:|---:|---:|---:|']
    for policy,groups in s.items():
        for arm,v in groups.items():
            eff=v['paired_diff_mm_vs_'+MAX_ARM]; lo,hi=eff['ci95']
            name=arm[6:] if arm.startswith('fixed') else ('原宽' if arm=='wide' else '高位窄带')
            body.append(f"| {NAMES[policy]} | {name} | {v['mean_m']*100:.2f} | {eff['mean']:.2f} [{lo:.2f}, {hi:.2f}] | {v['max_m']:.3f} | {v['alive_2s']}/{v['both_2s']} | {v['half_m']}/{v['flat']}/{v['slope']}/{v['finish']} |")
    low=contact_means['fixed-0.224000'];upper=contact_means[MAX_ARM]
    body+=['','配对区间以起点为单位自助抽样一万次，表中为逐项区间。2秒同触使用恰好 2.00 秒控制帧及累计物理违规记录。有效半米按逐帧过线记录。每套策略在不同摩擦下使用同一控制配置及观测通道。[纪录动作逐回合](teacher-paired.csv) · [中档逐回合](medium-paired.csv)',
          '## 已知起点与接触力',
          f'在纪录开发起点 12600381，固定摩擦从标称 0.32 到纪录值再到上限 0.416，末次双球同触拍分别为 {one["fixed-0.320000"]["last_both_m"]:.3f}、{one["fixed-0.364467"]["last_both_m"]:.3f}、{one[MAX_ARM]["last_both_m"]:.3f} 米。此处用固定网格旧动作对照，主赛道新起点有单独的统计。[开发起点重放](opened.json)',
          'MuJoCo 逐 2 毫秒读取真实接触，逐项核对两球各自的球拍摩擦和球球接触。记录每个接触点的法向力、切向力和接触点相对切向速度。法向力大于 0.01 毫牛的接触作为有载样本，切向力取两方向合力的模。μ 乘法向力是标量摩擦上界，另有扭转及滚动负载。不同完整回合在不同时间终止。为保持相同计时，另存每次释放后头 200 毫秒的同窗统计。[求解器接触审计](contact-audit.json)',
          f'同 12 个主赛道新起点的前 200 毫秒，把两球的全部有载触拍样本合并，μ 从 0.224 提高到 0.416，平均 μFn 从 {low["mean_scalar_bound_mN"]:.3f} 升至 {upper["mean_scalar_bound_mN"]:.3f} 毫牛。实际切向力的模分别均为约 {low["mean_tangential_mN"]:.3f} 和 {upper["mean_tangential_mN"]:.3f} 毫牛。两种摩擦下的接触点数量随真实运动变化。',
          '## 复跑',
          '在本目录执行下列命令。',
          '```bash','../../pingpong-turn-pit-20261128/run-local sweep.py','../../pingpong-turn-pit-20261128/run-local contact_forces.py','../../pingpong-turn-pit-20261128/run-local report.py','```']
    # Put each prose paragraph on its own block while keeping table rows adjacent.
    text='\n\n'.join(body).replace('|\n\n|','|\n|').replace('里程。横向','里程。水平')
    text=text.replace('横向前进','水平前进').replace('```bash\n\n','```bash\n').replace('\n\n../../','\n../../').replace('report.py\n\n```','report.py\n```')
    existing=sorted(HERE.glob('双球滑动摩擦扫描与接触力_*.md'))
    stamp=datetime.now(ZoneInfo('Asia/Singapore')).strftime('%Y%m%d_%H%M%S')
    path=existing[-1] if existing else HERE/f'双球滑动摩擦扫描与接触力_{stamp}.md'
    path.write_text(text+'\n')
    print(path.name)


if __name__=='__main__':main()
