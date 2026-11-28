"""Read-only checks on the saved paired trials, frozen code and published videos."""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import statistics
import subprocess


ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cohorts(name, keys, start, count):
    groups = defaultdict(list)
    with (ROOT / name).open(newline="") as source:
        for row in csv.DictReader(source):
            groups[tuple(row[k] for k in keys)].append(row)
            torque = row.get("torque", row.get("peak_torque_nm"))
            assert 0 <= float(torque) <= 0.20000001, (name, row["seed"])
    for group, rows in groups.items():
        assert len(rows) == count, (name, group)
        assert {int(row["seed"]) for row in rows} == set(range(start, start + count))
    return groups


def check_counts(rows, summary, keys):
    assert summary["n"] == len(rows)
    for key in keys:
        assert sum(row[key] == "True" for row in rows) == summary[key], key


def check_test_sets():
    frozen = read("qualification/frozen.json")
    for name, expected in frozen["hashes"].items():
        assert digest(ROOT / name) == expected, name
    main = cohorts("qualification/blind.csv", ("arm", "mat", "track"), 17410000, 300)
    blind = read("qualification/blind.json")
    assert set("/".join(key) for key in main) == blind.keys() and len(main) == 7
    for group, rows in main.items():
        result = blind["/".join(group)]
        check_counts(rows, result, ("flat", "slope", "finish", "both2"))
        distances = [float(r["last_m"]) for r in rows]
        assert math.isclose(statistics.mean(distances), result["mean_m"])
        assert max(distances) == result["max_m"]
        for key, threshold in [("half", 0.5), ("quarter", 0.25)]:
            assert sum(float(r["both_peak_m"]) >= threshold for r in rows) == result[key]

    specialists = cohorts("specialists/independent.csv", ("material", "name"), 17552000, 300)
    assert len(specialists) == 9
    for (material, policy), rows in specialists.items():
        result = read("specialists/independent.json")[material][policy]
        check_counts(rows, result, ("flat", "slope", "finish", "both2", "half", "qtr"))
        assert all(float(r["mu_a"]) == float(material) == float(r["mu_b"]) for r in rows)
        assert math.isclose(statistics.mean(float(r["m"]) for r in rows), result["mean"])

    opening = cohorts("opening/validation.csv", ("name", "material"), 17042000, 160)
    assert len(opening) == 6
    for (policy, material), rows in opening.items():
        check_counts(rows, read("opening/validation.json")[policy][material], ("flat", "slope", "finish", "both2"))
    legs = cohorts("leg-catch/heldout.csv", ("action", "material"), 17703000, 192)
    assert len(legs) == 4
    for (action, material), rows in legs.items():
        check_counts(rows, read("leg-catch/heldout.json")[action][material], ("flat", "slope", "finish", "both2"))
    for policy in ("teacher", "medium"):
        groups = cohorts(f"friction/{policy}-paired.csv", ("arm",), 17640000, 144)
        assert len(groups) == 9
        for (name,), rows in groups.items():
            result = read("friction/summary.json")[policy][name]
            check_counts(rows, result, ("flat", "slope", "finish"))
            assert math.isclose(statistics.mean(float(r["last_both_m"]) for r in rows), result["mean_m"])
    print("Checked 2,100 formal rows, 2,700 material-specialist rows, 960 opening rows, 768 leg rows and 2,592 friction rows.")


def check_additional_trials():
    conditions = cohorts("settle-speed/alternative.csv", ("settle", "material"), 17813000, 192)
    assert len(conditions) == 4
    for action in read("settle-speed/alternative.json"):
        for mu, results in action["results"].items():
            rows = conditions[(str(action["action"][0]), mu)]
            check_counts(rows, results, ("both2", "qtr", "half", "flat", "slope", "finish"))

    before, after = read("narrow-slope/unseen-material-paired.json")
    materials = [r["mu"] for r in before["rows"]]
    assert len(set(materials)) == len(materials) == 48
    assert all(.414 <= mu <= .416 for mu in materials)
    assert materials == [r["mu"] for r in after["rows"]]
    for arm, expected in ((before, "baseline"), (after, "trained")):
        assert arm["config"]["seed"] == 14552505
        summary = read("narrow-slope/result.json")[expected]
        assert summary["park"] == sum(r["park"] for r in arm["rows"])
        assert summary["gate"] == sum(r["gate"] for r in arm["rows"])
        assert all(r["torque"] <= .20000001 for r in arm["rows"])
        assert math.isclose(summary["min_m"], min(r["m"] for r in arm["rows"]))

    a = read("low-route/extension-result.json")["verified"]
    assert a["gates"]["flat_1m"]["both_contact"] and a["track"] == "combined"
    assert not a["slope_1m"] and not a["finish_2p5"] and round(a["last_both_m"], 5) == 1.25006
    b = read("slope/parked-0416-proof.json")
    assert b["mu"] == [.416, .416] and b["row"]["success"] and b["row"]["track"] == "incline"
    assert b["row"]["stable_finish_s"] == 1 and b["row"]["gates"]["slope_1m"]["both_contact"]
    assert b["video_sha256"] == digest(ROOT / "slope/parked-0416-replay.mp4")
    print("Checked 768 speed/preparation trials, 48 unseen paired materials and the metre gates in the two selected replays.")

    protocol = read("outward/protocol.json")
    held = read("outward/paired-holdout.json")
    results = read("outward/validation.json")["results"]
    training_seeds = {r["seed"] for name in ("curriculum", "selection") for r in protocol[name]}
    assert len(training_seeds) == 68 and len(held) == 2 * (80 + 96)
    hard = {r["seed"] for r in protocol["hard"]}
    ordinary = {r["seed"] for r in protocol["ordinary"]}
    assert hard.isdisjoint(ordinary) and training_seeds.isdisjoint(hard | ordinary)
    for group, seeds in [("hard", hard), ("ordinary", ordinary)]:
        for name in ("phase_08", read("outward/frozen.json")["winner"]):
            rr = [r for r in held if r["seed"] in seeds and r["arm"] == name]
            assert len(seeds) == len({r["seed"] for r in rr}) == len(rr)
            for key in ("both2", "qtr", "flat", "finish"):
                assert sum(r[key] for r in rr) == results[group][name][key]
    print("Checked the early-action comparison on 80 outward and 96 unfiltered independent releases.")


def check_report():
    report, = ROOT.glob("最高滑动摩擦双球训练与验收_*.md")
    links = {ROOT / s for s in re.findall(r"\]\(([^)\n]+)\)", report.read_text())}
    for link in links:
        assert link.is_file(), link
    videos = sorted(path for path in links if path.suffix == ".mp4")
    for path in videos:
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], check=True)
        info = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=nb_frames,avg_frame_rate", "-of", "json", str(path)
        ])
        stream, = json.loads(info)["streams"]
        print(f"{path.relative_to(ROOT)}: {stream['nb_frames']} frames, {stream['avg_frame_rate']} fps")
        sidecar = path.with_suffix(".json")
        if sidecar.exists():
            meta = json.loads(sidecar.read_text())
            if "frames" in meta and isinstance(meta["frames"], int):
                assert int(stream["nb_frames"]) == meta["frames"], path
            if "trace" in meta and "sha256" in meta:
                candidates = (sidecar.parent / meta["trace"], sidecar.parent.parent / meta["trace"])
                trace = next(p for p in candidates if p.is_file())
                assert digest(trace) == meta["sha256"], trace
    assert digest(ROOT / "media/endpoint-comparison.mp4") == read("media/endpoint-comparison.json")["sha"]


if __name__ == "__main__":
    check_test_sets()
    check_additional_trials()
    check_report()
