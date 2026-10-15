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
