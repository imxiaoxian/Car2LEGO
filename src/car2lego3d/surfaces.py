"""Discrete strip fitting using measured native curved-part cross sections."""
from functools import lru_cache

import numpy as np


# Heights are plate units relative to the native LDraw origin. Cross sections
# were ray-sampled from local LDraw triangles; supports are real socket planes.
PROFILES = (
    ("3069b", (0.,), (-1,)),
    ("15068", (1.2098918, 1.9092852), (0, 1)),
    ("93606", (-1.9244237, -.9758047, -.3718063, -.0768424), (-3, -3, -2, -1)),
)

# (part, length, width, height samples, socket planes). All dimensions are
# native; the wider bow has the same section as 15068, not a scaled mesh.
SHELL_PARTS = (
    ("3068b", 2, 2, (0.,)*2, (-1,)*2),
    ("87079", 4, 2, (0.,)*4, (-1,)*4),
    ("69729", 6, 2, (0.,)*6, (-1,)*6),
    ("6881b", 6, 6, (0.,)*6, (-1,)*6),
    ("87079", 2, 4, (0.,)*2, (-1,)*2),
    ("69729", 2, 6, (0.,)*2, (-1,)*2),
    ("2431", 1, 4, (0.,), (-1,)),
    ("6636", 1, 6, (0.,), (-1,)),
    ("15068", 2, 2, PROFILES[1][1], (0, 1)),
    ("88930", 2, 4, PROFILES[1][1], (0, 1)),
    ("52031", 4, 6, (-.625, -.125, 0., 1.), (-2,)*4),
    ("93606", 4, 2, PROFILES[2][1], (-3, -3, -2, -1)),
    ("3069b", 1, 2, (0.,), (-1,)),
)


def fit_shell(target, width, flat_only=False):
    """Fit a rectangular shell with native modules and an explicit seam cost."""
    target = np.asarray(target, dtype=float)
    if target.ndim != 1 or not len(target) or not np.isfinite(target).all() or width < 2 or width % 2:
        raise ValueError("Shell fitting needs finite heights and an even width of at least two studs.")

    @lru_cache(None)
    def strip(index, band, previous):
        if index == len(target):
            return 0., ()
        best = (float("inf"), ())
        for part, size, breadth, profile, sockets in SHELL_PARTS:
            if breadth != band or index+size > len(target):
                continue
            if flat_only and len(set(profile)) > 1:
                continue
            for reverse in (False, True) if len(set(profile)) > 1 else (False,):
                offsets = np.array(profile[::-1] if reverse else profile)
                estimate = int(round(float(np.mean(target[index:index+size]-offsets))))
                for origin in range(estimate-1, estimate+2):
                    actual = offsets+origin
                    if float(np.max(np.abs(actual-target[index:index+size]))) > 1.0:
                        continue
                    error = float(np.sum((actual-target[index:index+size])**2))*band
                    jump = 0 if previous is None else (actual[0]-previous/100)**2*band
                    # Pay per seam and discourage tiny visible fillers. This is
                    # deliberately independent of hidden chassis brick packing.
                    cost = error+jump+2.5+(4 if size*breadth < 4 else 0)+(2.5 if part == "52031" else 0)
                    rest, tail = strip(index+size, band, round(float(actual[-1])*100))
                    if cost+rest < best[0]:
                        best = cost+rest, ((part, index, size, band, origin, reverse),)+tail
        return best

    @lru_cache(None)
    def bands(remaining):
        if not remaining:
            return 0., ()
        best = (float("inf"), ())
        if remaining in (2, 4, 6):
            cost, pieces = strip(0, remaining, None)
            best = cost, ((remaining, pieces),)
        for band in (4, 2):
            if 2*band > remaining:
                continue
            cost, pieces = strip(0, band, None)
            rest, middle = bands(remaining-2*band)
            if 2*cost+rest < best[0]:
                best = 2*cost+rest, ((band, pieces),)+middle+((band, pieces),)
        return best

    cost, rows = bands(width)
    return dict(cost=cost, bands=rows, target_plates=target.tolist(), width_studs=width)


def place_shell(car, xs, ys, target, color, module, step, floor=4, flat_only=False):
    from .carfit import IDENTITY, QUARTER, BACK_QUARTER
    xs, ys = list(xs), list(ys)
    if not xs or xs != list(range(xs[0], xs[-1]+1)) or ys != list(range(ys[0], ys[-1]+1)):
        raise ValueError("Shell bounds must be contiguous.")
    if len(xs) != len(target):
        raise ValueError("One target height is required per longitudinal stud.")
    plan = fit_shell(target, len(ys), flat_only)
    catalog = {(p, size, breadth): (profile, sockets) for p, size, breadth, profile, sockets in SHELL_PARTS}
    native_x = {"3069b": 2, "3068b": 2, "87079": 4, "69729": 6, "6881b": 6, "2431": 4, "6636": 6}
    offset = 0
    for band, pieces in plan["bands"]:
        lateral = ys[offset:offset+band]
        for part, index, size, _, origin, reverse in pieces:
            profile, sockets = catalog[part, size, band]
            footprint = xs[index:index+size]
            for x, socket in zip(footprint, sockets[::-1] if reverse else sockets):
                height = origin+socket
                car.clear([x], lateral, range(height, 40))
                car.fill([x], lateral, range(floor, height), color)
            flat = len(set(profile)) == 1
            x_origin=float(np.mean(footprint))
            if part == "52031":
                x_origin += -1.5 if reverse else 1.5
            car.place(part, color, x_origin, float(np.mean(lateral)), origin,
                      module, step, (IDENTITY if size == native_x[part] else QUARTER) if flat else
                      BACK_QUARTER if reverse else QUARTER)
            if part == "52031":
                car.place("2431", color, footprint[0] if reverse else footprint[-1], float(np.mean(lateral)),
                          origin+1, module, step, QUARTER)
        offset += band
    plan["part_count"] = sum(1+(piece[0] == "52031") for _, pieces in plan["bands"] for piece in pieces)
    return plan


def place_roof_bows(car, xs, left, cabin_width, base, color, step=18):
    """Use four-stud-wide bows along each roof edge instead of one per stud."""
    from .carfit import IDENTITY, HALF
    xs = list(xs)
    for side, y in ((-1, left+.5), (1, left+cabin_width-1.5)):
        index = 0
        while index < len(xs):
            span = 4 if len(xs)-index >= 4 else 2 if len(xs)-index >= 2 else 1
            part = {4: "88930", 2: "15068", 1: "11477"}[span]
            car.place(part, color, float(np.mean(xs[index:index+span])), y, base,
                      "modular roof shoulders", step, IDENTITY if side == -1 else HALF)
            index += span


def fit_strip(target):
    """Minimize silhouette error, seams and endpoint jumps over native parts."""
    target = np.asarray(target, dtype=float)
    if target.ndim != 1 or not len(target) or not np.isfinite(target).all():
        raise ValueError("A finite, nonempty height strip is required.")

    @lru_cache(None)
    def solve(index, previous):
        if index == len(target):
            return 0., ()
        best = (float("inf"), ())
        for part, profile, supports in PROFILES:
            size = len(profile)
            if index+size > len(target):
                continue
            for reverse in (False, True) if size > 1 else (False,):
                offsets = np.array(profile[::-1] if reverse else profile)
                estimated = int(round(float(np.mean(target[index:index+size]-offsets))))
                for origin in range(estimated-1, estimated+2):
                    actual = offsets+origin
                    junction = 0 if previous is None else 1.3*(actual[0]-previous/100)**2
                    cost = float(np.sum((actual-target[index:index+size])**2)) + junction + .16
                    tail_cost, tail = solve(index+size, round(float(actual[-1])*100))
                    if cost+tail_cost < best[0]:
                        best = (cost+tail_cost, ((part,index,origin,reverse),)+tail)
        return best

    cost, pieces = solve(0, None)
    return {"cost": cost, "pieces": pieces, "target_plates": target.tolist()}


def place_strip(car, xs, ys, target, color, module, step):
    from .carfit import QUARTER, BACK_QUARTER
    xs, ys = list(xs), list(ys)
    if len(ys) != 2 or len(xs) != len(target) or xs != list(range(xs[0], xs[-1]+1)):
        raise ValueError("Surface strips require a contiguous length and two-stud width.")
    plan = fit_strip(target)
    profiles = {part: (profile,supports) for part,profile,supports in PROFILES}
    for part,index,origin,reverse in plan["pieces"]:
        profile,supports = profiles[part]
        support = list(reversed(supports)) if reverse else supports
        footprint = xs[index:index+len(profile)]
        for x,offset in zip(footprint,support):
            height = origin+offset
            car.clear([x],ys,range(height,40))
            car.fill([x],ys,range(4,height),color)
        car.place(part,color,float(np.mean(footprint)),float(np.mean(ys)),origin,module,step,
                  BACK_QUARTER if reverse else QUARTER)
    return plan
