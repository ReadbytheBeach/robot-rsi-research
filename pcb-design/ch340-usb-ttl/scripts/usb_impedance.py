#!/usr/bin/env python3
"""Quasi-static coupled-microstrip estimate for this USB differential pair.

SPDX-License-Identifier: GPL-2.0-or-later
Equations adapted from KiCad 9's GPL-2.0-or-later transline implementation:
Copyright (C) 2002 Claudio Girardi; (C) 2005, 2006 Stefan Jahn;
Copyright The KiCad Developers. Python adaptation for this design, 2026.

Model: Kirschning/Jansen static odd mode, with Jansen/Atwater finite copper
thickness correction and the Hammerstad/Jensen single-line reference.
Zdiff = 2 * Zodd. There is NO soldermask, coplanar side copper, roughness,
connector/pad discontinuity, fabrication-tolerance or field-solver model here.
The result is a design estimate, not a certified or measured impedance.

All geometry arguments use mm; results are in ohms. Python standard library.
Source SHA: ce707d0a6c8736cbf4689560be4fee3d6a7f7f5e (KiCad 9.0 branch).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FREE_SPACE_OHMS = 376.730313668
SOURCE_BASE = "https://github.com/KiCad/kicad-source-mirror/blob/ce707d0a6c8736cbf4689560be4fee3d6a7f7f5e/pcb_calculator/transline/"


def single_line_zero_thickness(u: float, er: float) -> tuple[float, float]:
    """Return zero-thickness single-line Z and effective permittivity."""
    a = (1 + math.log((u**4 + u*u/2704)/(u**4 + 0.432))/49
         + math.log(1 + u**3/5929.741)/18.7)
    b = 0.564 * ((er - 0.9)/(er + 3))**0.053
    filling = (1 + 10/u)**(-a*b)
    eps = (er + 1)/2 + (er - 1)/2*filling
    f = 6 + (2*math.pi - 6)*math.exp(-(30.666/u)**0.7528)
    z_homogeneous = FREE_SPACE_OHMS/(2*math.pi) * math.log(
        f/u + math.sqrt(1 + 4/u**2))
    return z_homogeneous/math.sqrt(eps), eps


def differential_ohms(width: float, gap: float, height: float,
                       copper: float, er: float) -> float:
    """Static edge-coupled microstrip over an infinite unbroken ground plane.

    gap is the EDGE-to-EDGE separation, not the centre-line pitch.
    height is dielectric separation from bottom of top copper to ground top.
    """
    if not all(math.isfinite(x) for x in (width, gap, height, copper, er)):
        raise ValueError("All inputs must be finite")
    if min(width, gap, height) <= 0 or copper < 0 or er <= 1:
        raise ValueError("Positive geometry, nonnegative copper and er > 1 required")
    u, g, th = width/height, gap/height, copper/height
    z_single, eps_single = single_line_zero_thickness(u, er)

    # Normalized even/odd effective widths including finite conductor thickness.
    if th:
        du = (1.25*th/math.pi) * (1 + math.log(
            (2 + (4*math.pi*u - 2)/(1 + math.exp(-100*(u - 1/(2*math.pi)))))/th))
        dt = th/(g*er)
        ue = u + du*(1 - 0.5*math.exp(-0.69*du/dt))
        uo = ue + dt
    else:
        ue = uo = u

    b_odd = 0.747*er/(0.15 + er)
    c_odd = b_odd - (b_odd - 0.207)*math.exp(-0.414*uo)
    d_odd = 0.593 + 0.694*math.exp(-0.562*uo)
    filling_odd = math.exp(-c_odd*g**d_odd)
    filling_odd -= 2*math.log(2)/math.pi * th/math.sqrt(uo)
    a_odd = 0.7287*(eps_single - (er + 1)/2)*(1 - math.exp(-0.179*uo))
    eps_odd = ((er + 1)/2 + a_odd - eps_single)*filling_odd + eps_single

    q1 = 0.8695*ue**0.194
    q2 = 1 + 0.7519*g + 0.189*g**2.31
    q3 = (0.1975 + (16.6 + (8.4/g)**6)**(-0.387)
          + math.log(g**10/(1 + (g/3.4)**10))/241)
    q4 = 2*q1/(q2*(math.exp(-g)*ue**q3 + (2 - math.exp(-g))*ue**(-q3)))
    q5 = 1.794 + 1.14*math.log(1 + 0.638/(g + 0.517*g**2.43))
    q6 = (0.2305 + math.log(g**10/(1 + (g/5.8)**10))/281.3
          + math.log(1 + 0.598*g**1.154)/5.1)
    q7 = (10 + 190*g*g)/(1 + 82.3*g**3)
    q8 = math.exp(-6.5 - 0.95*math.log(g) - (g/0.15)**5)
    q9 = math.log(q7)*(q8 + 1/16.5)
    q10 = (q2*q4 - q5*math.exp(math.log(uo)*q6*uo**(-q9)))/q2
    odd = (z_single*math.sqrt(eps_single/eps_odd)
           / (1 - math.sqrt(eps_single)*q10*z_single/FREE_SPACE_OHMS))
    return 2*odd


def solve_width(target: float, gap: float, height: float,
                copper: float, er: float) -> float:
    if not math.isfinite(target) or target <= 0:
        raise ValueError("Target must be a positive finite impedance")
    lo, hi = 0.1*height, 3.0*height
    if not differential_ohms(lo, gap, height, copper, er) > target > differential_ohms(hi, gap, height, copper, er):
        raise ValueError("Target is outside this solver's width bracket")
    for _ in range(70):
        middle = (lo + hi)/2
        if differential_ohms(middle, gap, height, copper, er) > target:
            lo = middle
        else:
            hi = middle
    return (lo + hi)/2


def self_test() -> None:
    base = differential_ohms(0.75, 0.15, 0.93, 0.035, 4.2)
    assert 89 < base < 91
    assert differential_ohms(0.85, 0.15, 0.93, 0.035, 4.2) < base
    assert differential_ohms(0.75, 0.20, 0.93, 0.035, 4.2) > base
    assert differential_ohms(0.75, 0.15, 0.93, 0.035, 4.6) < base
    assert abs(differential_ohms(7.5, 1.5, 9.3, 0.35, 4.2) - base) < 1e-9
    wide_gap = differential_ohms(0.75, 93, 0.93, 0, 4.2)
    single, _ = single_line_zero_thickness(0.75/0.93, 4.2)
    assert abs(wide_gap - 2*single)/(2*single) < 0.01
    w = solve_width(90, 0.15, 0.93, 0.035, 4.2)
    assert abs(differential_ohms(w, 0.15, 0.93, 0.035, 4.2) - 90) < 1e-8
    try:
        differential_ohms(0.75, 0.15, 0, 0.035, 4.2)
    except ValueError:
        pass
    else:
        raise AssertionError("Zero dielectric height must be rejected")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width-mm", type=float, default=0.75)
    parser.add_argument("--gap-mm", type=float, default=0.15)
    parser.add_argument("--height-mm", type=float, default=0.91)
    parser.add_argument("--copper-mm", type=float, default=0.035)
    parser.add_argument("--er", type=float, default=4.2)
    parser.add_argument("--target-ohms", type=float, default=90)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
    values = dict(width=args.width_mm, gap=args.gap_mm, height=args.height_mm,
                  copper=args.copper_mm, er=args.er)
    sensitivity = []
    for key, test_values in [("er", [3.8, 4.6]), ("height", [0.88, 0.98]),
                             ("width", [0.70, 0.80]), ("gap", [0.125, 0.175])]:
        for value in test_values:
            case = dict(values, **{key: value})
            sensitivity.append({"changed_parameter": key, "value": value,
                                "estimated_ohms": differential_ohms(**case)})
    report = {
        "model": "KiCad9 Kirschning/Jansen static coupled microstrip; finite copper",
        "source_commit": "ce707d0a6c8736cbf4689560be4fee3d6a7f7f5e",
        "sources": [SOURCE_BASE + "c_microstrip.cpp", SOURCE_BASE + "microstrip.cpp"],
        "inputs_mm_except_er": values,
        "estimated_differential_ohms": differential_ohms(**values),
        "target_ohms": args.target_ohms,
        "solved_width_mm": solve_width(args.target_ohms, args.gap_mm, args.height_mm,
                                       args.copper_mm, args.er),
        "centre_spacing_mm": args.width_mm + args.gap_mm,
        "self_test": "passed" if args.self_test else "not requested",
        "one_parameter_sensitivity_only": sensitivity,
        "limitations": ["No soldermask or coplanar side ground model",
                        "Infinite unbroken bottom ground plane assumed",
                        "No pad/connector/neckdown, roughness or dispersion model",
                        "Not measured, field-solved or fabrication-certified impedance"],
        "fabrication_requirement": "90 ohm differential controlled impedance, nominal tolerance +/-10%; fabricator must confirm actual stack and geometry before production",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
