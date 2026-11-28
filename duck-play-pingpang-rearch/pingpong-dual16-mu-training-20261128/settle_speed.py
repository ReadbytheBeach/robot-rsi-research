"""Train a single unloaded waiting time and walking speed for unseen natural releases."""
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch
import csv
import json
import statistics
import sys

from material import HERE, save, study

sys.path.insert(0, str(HERE / "opening"))
import train_opening as opening

OUT = HERE / "settle-speed"
OUT.mkdir(exist_ok=True)
STANDARD = (1.0, .44)


def run(job):
    settle, speed, material, seed = job
    params = dict(study.BASE["params"], settle_s=settle)
    with patch.dict(study.BASE, {"params": params}), patch.dict(opening.RECIPE, {"cruise": speed}):
        result = opening.run_seed(seed, material, name="phase_08")
    result.update(settle=settle, speed=speed)
    return result


def sample(pool, actions, materials, start, n, label):
    results = list(pool.map(run, [(t, v, mu, seed) for seed in range(start, start+n)
                                  for mu in materials for t, v in actions], chunksize=4))
    with (OUT / f"{label}.csv").open("w", newline="") as source:
        writer = csv.DictWriter(source, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    table = {}
    for action in actions:
        entries = {}
        for mu in materials:
            rows = [r for r in results if (r["settle"], r["speed"]) == action and r["material"] == mu]
            assert len(rows) == len({r["seed"] for r in rows}) == n
            assert all(r["torque"] <= .20000001 and r["mu_a"] == mu == r["mu_b"] for r in rows)
            entries[mu] = {k: sum(r[k] for r in rows) for k in ("flat", "slope", "finish", "half", "qtr", "both2")}
            entries[mu].update(n=n, average=statistics.mean(r["m"] for r in rows), maximum=max(r["m"] for r in rows))
        table[action] = entries
    save(OUT / f"{label}.json", [{"action": a, "results": x} for a, x in table.items()])
    return table


def rank(conditions):
    return tuple(sum(x[k] for x in conditions.values()) for k in ("finish", "slope", "flat", "half", "qtr", "both2", "average"))


def main():
    actions = [(s, v) for s in (.58, .82, 1., 1.18, 1.46, 1.72) for v in (.33, .44, .55, .65)]
    save(OUT / "protocol.json", dict(actions=actions, fixed_opening="phase_08", control=STANDARD,
         screen=[17810000, 24], selection=[17811000, 64], independent=[17812000, 192],
         score=["finish", "slope", "flat", "half", "qtr", "both2", "average"],
         setup="Unloaded stationary preparation before natural release. Walking cruise varied through the intact motor policy."))
    with ProcessPoolExecutor(7) as pool:
        first = sample(pool, actions, [.416], 17810000, 24, "screen")
        top = sorted(actions, key=lambda a: rank(first[a]), reverse=True)[:5]
        top = list(dict.fromkeys([STANDARD, *top]))
        second = sample(pool, top, [.416, .224], 17811000, 64, "select")
        winner = max(top, key=lambda a: rank(second[a]))
        save(OUT / "frozen.json", {"winner": winner, "reference": STANDARD})
        sample(pool, list(dict.fromkeys([winner, STANDARD])), [.416, .224], 17812000, 192, "independent")


def compare_alternative():
    selection = json.loads((OUT / "select.json").read_text())
    alternatives = [r for r in selection if tuple(r["action"]) != STANDARD]
    runner = tuple(max(alternatives, key=lambda r: rank(r["results"]))["action"])
    save(OUT / "alternative-protocol.json", dict(action=runner, reference=STANDARD, independent=[17813000, 192],
         reason="Best nonstandard preparation from the original selection, compared on a new cohort."))
    with ProcessPoolExecutor(7) as pool:
        sample(pool, [STANDARD, runner], [.416, .224], 17813000, 192, "alternative")


if __name__ == "__main__":
    if sys.argv[1:] == ["alternative"]:
        compare_alternative()
    else:
        main()
