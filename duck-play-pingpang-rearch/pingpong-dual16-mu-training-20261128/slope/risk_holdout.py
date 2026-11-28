"""Lock the best camera-risk arm from development and evaluate it as a secondary blind comparison."""
from concurrent.futures import ProcessPoolExecutor
from action_transfer import DEST, TEST, TEACHER, bank, episode, evaluate, order, save, summary
from high_slope import read


def main():
    stats=read(DEST/'select-summary.json')
    candidates=[p for p in bank() if p['name'] in stats and p['risk'] is not None]
    p=order(stats,candidates)[0]
    save('risk-seal.json',dict(selected=p,range=[TEST.start,TEST.stop-1],selection='highest validation score among the vision-risk variants, locked before opening this blind comparison'))
    with ProcessPoolExecutor(3) as pool:
        rows=evaluate(pool,[p],TEST)
    save('risk-blind.json',rows)
    save('risk-summary.json',summary(rows,[p]))
    save('risk-opened.json',episode((p,TEACHER['config']['seed'])))


if __name__=='__main__':
    main()
