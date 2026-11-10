#!/usr/bin/env python3
"""Read-only review: native XML→every PCB pad; critical pin locations; geometry.

Run with KiCad's /usr/bin/python3. This does not certify physical parts or SI.
"""
import collections
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def normalized(name):
    return (name or "").removeprefix("/")


def nc(name):
    return not name or name.startswith("unconnected-(")


board = pcbnew.LoadBoard(str(ROOT / "ch340-usb-ttl.kicad_pcb"))
xml = ET.parse(ROOT / "ch340-usb-ttl.net").getroot()
native = collections.defaultdict(dict)
for net in xml.findall("./nets/net"):
    for node in net.findall("node"):
        native[node.attrib["ref"]][node.attrib["pin"]] = normalized(net.attrib["name"])

footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
errors = []
per_component = []
for component in xml.findall("./components/comp"):
    ref = component.attrib["ref"]
    if ref not in footprints:
        errors.append({"reference": ref, "reason": "missing footprint"})
        continue
    footprint = footprints[ref]
    pads = collections.defaultdict(list)
    for pad in footprint.Pads():
        pads[pad.GetNumber()].append(pad)
    checked = []
    for pin, expected in native[ref].items():
        if pin not in pads:
            errors.append({"reference": ref, "pin": pin, "reason": "missing pad"})
            continue
        for pad in pads[pin]:
            actual = normalized(pad.GetNetname())
            matches = actual == expected or (nc(actual) and nc(expected))
            checked.append({"pin": pin, "expected": expected, "actual": actual,
                            "matches": matches})
            if not matches:
                errors.append({"reference": ref, **checked[-1]})
    per_component.append({"reference": ref, "checked_pad_count": len(checked),
                          "all_match": all(p["matches"] for p in checked),
                          "pads": checked})

# Straight-line pad distances are placement evidence, not routed loop inductance.
def pad_xy(ref, number):
    pad = next(p for p in footprints[ref].Pads() if p.GetNumber() == str(number))
    position = pad.GetPosition()
    return [position.x / 1e6, position.y / 1e6]


distances = []
for a, b, label in [(("C4", 1), ("U1", 16), "CH340C VCC bypass"),
                    (("C5", 1), ("U1", 4), "CH340C V3 bypass"),
                    (("C2", 1), ("U2", 1), "LDO input"),
                    (("C3", 1), ("U2", 5), "LDO output"),
                    (("C1", 1), ("D1", 5), "ESD VBUS bypass")]:
    xy_a, xy_b = pad_xy(*a), pad_xy(*b)
    distances.append({"purpose": label, "from": list(a), "to": list(b),
                      "straight_pad_distance_mm": math.dist(xy_a, xy_b)})

usb = {}
for net_name in ("USB_D+", "USB_D-"):
    segments = []
    via_count = 0
    for track in board.GetTracks():
        if normalized(track.GetNetname()) != net_name:
            continue
        if track.Type() == pcbnew.PCB_VIA_T:
            via_count += 1
            continue
        start, end = track.GetStart(), track.GetEnd()
        segments.append({"start_mm": [start.x / 1e6, start.y / 1e6],
                         "end_mm": [end.x / 1e6, end.y / 1e6],
                         "width_mm": track.GetWidth() / 1e6,
                         "length_mm": track.GetLength() / 1e6,
                         "layer": board.GetLayerName(track.GetLayer())})
    usb[net_name] = {"all_copper_segment_length_mm": sum(s["length_mm"] for s in segments),
                     "nominal_0p75_width_length_mm": sum(s["length_mm"] for s in segments
                                                         if abs(s["width_mm"] - 0.75) < 1e-6),
                     "widths_mm": sorted({s["width_mm"] for s in segments}),
                     "signal_via_count": via_count,
                     "segments": segments}

ground_zones = [zone for zone in board.Zones()
                if normalized(zone.GetNetname()) == "GND" and not zone.GetIsRuleArea()]
# Actual filled copper, not zone outlines; sample the complete uniform trunk width.
reference_samples = []
for ix in range(18):
    for iy in range(51):
        x, y = 63.805 + ix * 0.1, 63.3 + iy * 0.1
        point = pcbnew.VECTOR2I(round(x * 1e6), round(y * 1e6))
        covered = any(zone.HitTestFilledArea(pcbnew.B_Cu, point) for zone in ground_zones)
        reference_samples.append({"x_mm": x, "y_mm": y, "covered": covered})

ground_vias = []
signal_vias = []
for track in board.GetTracks():
    if track.Type() != pcbnew.PCB_VIA_T:
        continue
    position = track.GetPosition()
    item = {"net": normalized(track.GetNetname()), "xy_mm": [position.x / 1e6, position.y / 1e6]}
    (ground_vias if item["net"] == "GND" else signal_vias).append(item)
for via in signal_vias:
    via["nearest_ground_via_mm"] = min((math.dist(via["xy_mm"], other["xy_mm"])
                                        for other in ground_vias), default=None)

result = {
    "status": "passed" if not errors else "failed",
    "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                      for name in ("ch340-usb-ttl.kicad_sch", "ch340-usb-ttl.net", "ch340-usb-ttl.kicad_pcb")},
    "native_xml_component_count": len(xml.findall("./components/comp")),
    "pcb_footprint_count": len(footprints),
    "per_component": per_component,
    "pin_net_errors": errors,
    "decoupling_pad_distances": distances,
    "usb_geometry": usb,
    "uniform_trunk_bottom_ground_sampling": {
        "step_mm": 0.1, "samples": len(reference_samples),
        "uncovered_samples": [point for point in reference_samples if not point["covered"]],
        "scope": "5mm uniform vertical trunk at x64.18/65.08; discrete samples under copper and intervening gap"
    },
    "signal_via_ground_distances": signal_vias,
    "limits": ["XML-to-pad consistency does not independently validate connector manufacturer dimensions.",
               "Pad distances are straight-line placement distances, not complete routed loop geometry.",
               "USB total copper includes Type-C duplicate-pin branches and is not one end-to-end path.",
               "A 0.75mm segment width alone does not verify pair gap, return plane or impedance."]
}
output = ROOT / "analysis/review/layout-manual.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k not in ("per_component", "usb_geometry")},
                 ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
