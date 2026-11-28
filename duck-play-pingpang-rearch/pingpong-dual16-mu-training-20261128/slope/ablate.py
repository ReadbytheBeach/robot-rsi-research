"""Recheck the full parked release with selected interventions removed, one at a time."""
from concurrent.futures import ProcessPoolExecutor
from high_slope import HERE, MAX_ARM, read, run, save
from sweep import ARMS


def test(case):
    name, arm, config = case
    return dict(name=name, **run(config,arm))


def main():
    c = read(HERE/'sprint-best.json')['config']
    cases = [('fixed-recipe', arm, c) for arm in ARMS]
    cases += [
        ('remove-brake-override', MAX_ARM, dict(c, brake=None)),
        ('remove-final-pulse', MAX_ARM, dict(c, actions=c['actions'][:-1])),
        ('remove-all-pulses', MAX_ARM, dict(c, actions=[])),
        ('restore-preparation', MAX_ARM, dict(c, values=None)),
        ('restore-nominal-gait-scale', MAX_ARM, dict(c, scale=1.)),
        ('restore-all-controls', MAX_ARM, dict(c, values=None, actions=[], brake=None, scale=1.)),
    ]
    with ProcessPoolExecutor(3) as pool:
        rows = list(pool.map(test,cases))
    save('sprint-ablations.json',rows)


if __name__=='__main__':
    main()
