"""Native glazing layouts with bounded seams and a descending rear quarter."""
from functools import lru_cache


def side_window_plan(start, end, four_doors=False):
    """Partition the window belt without crossing a pillar or the cabin bounds."""
    count = end-start+1
    if count < 2:
        return [{"kind": "pillar", "start": start, "span": count}]
    # Preserve a two-stud rear quarter for the raked C pillar on longer cabins.
    quarter = count >= 7
    main_end = end-2 if quarter else end
    pillar = min(main_end-2, max(start+2, round(start+(count-1)*(.46 if four_doors else .58))))
    if main_end-start < 4:
        pillar = None

    @lru_cache(None)
    def solve(x):
        if x > main_end:
            return 0., ()
        if x == pillar:
            cost, tail = solve(x+1)
            return cost, (("pillar", x, 1),)+tail
        best = (float("inf"), ())
        for span in (2, 1):
            if x+span-1 > main_end or (pillar is not None and x < pillar < x+span):
                continue
            cost, tail = solve(x+span)
            # One-stud opaque fillers are used only when a real pane cannot fit.
            candidate = (cost+(.15 if span == 2 else 2),
                         (("pane" if span == 2 else "pillar", x, span),)+tail)
            if candidate[0] < best[0]:
                best = candidate
        return best

    _, segments = solve(start)
    result = [dict(kind=kind, start=x, span=span) for kind, x, span in segments]
    if quarter:
        result.append(dict(kind="quarter", start=end-1, span=2))
    return result


def place_side_windows(car, start, end, sides, glass_top, deck, four_doors=False):
    from .carfit import IDENTITY, HALF, BACK_QUARTER
    plan = side_window_plan(start, end, four_doors)
    bottom = glass_top-6
    for side, y in zip((-1, 1), sides):
        car.fill(range(start, end+1), [y], range(deck, bottom), 0)
        # A dark continuous sill hides the underside of the native panels.
        car.fill(range(start, end+1), [y], [bottom-1], 0)
        for segment in plan:
            x, span = segment["start"], segment["span"]
            if segment["kind"] == "pillar":
                car.fill(range(x, x+span), [y], range(bottom, glass_top), 0)
            elif segment["kind"] == "pane":
                car.place("87552", 40, x+.5, y, glass_top, "continuous side glazing", 16,
                          HALF if side == -1 else IDENTITY)
            else:
                car.place("4865b", 40, x+.5, y, glass_top-3, "rear quarter glazing", 16,
                          HALF if side == -1 else IDENTITY)
                # Native 45-degree slope fits above the shorter quarter pane.
                car.place("3040b", 0, x, y, glass_top, "raked window surround", 16, BACK_QUARTER)
        car.fill(range(start-1, end+2), [y], [glass_top], 0)
    car.fit["glazing_layout"] = dict(version=2, side_segments=plan, tint_ldraw=40,
        panel_height_plates=6, quarter_height_plates=3,
        method="bounded pane partition; shared sill; native sloped rear surround",
        part_scaling=False, physical_verified=False)


def place_split_headlamps(car, nose, width):
    """Smooth DRL covers and separate recessed projectors on native side studs."""
    from .carfit import QUARTER
    front = (0, 1, 0, 0, 0, 1, 1, 0, 0)
    appearance = car.fit.get("reference_appearance", {})
    features = " ".join(appearance.get("distinctive_features", [])).lower()
    split = car.fit.get("styling_prior") == "lotus-for-me" or "split" in features or "分体" in features
    for side in (-1, 1):
        ys = (1, 2) if side == -1 else (width-3, width-2)
        car.clear([0], ys, [nose-1])
        car.place("3023", 0, 0, sum(ys)/2, nose, "headlamp housings", 14, QUARTER)
        car.place("3069b", 15, 0, sum(ys)/2, nose+1, "slim split headlamps", 18, QUARTER)
        if split:
            for y in ys:
                car.clear([0], [y], range(nose-4, nose-1))
                car.place("87087", 0, 0, y, nose-1, "projector mounts", 9, QUARTER)
            car.place("3069b", 47, -.9, sum(ys)/2, nose-2.25, "recessed main headlamps", 18, front)
    car.fit["lamp_layout"] = dict(version=3, front="split DRL and rectangular projector" if split else "paired slim lenses",
        lens_ldraw=47, drl_ldraw=15, housing_ldraw=0, lens_scaling=False,
        method="continuous two-stud lenses on black plates; paired side-stud projector sockets")


def place_tail_light_bar(car, deck, width, length):
    from .carfit import QUARTER
    rows = range(1, width-1)
    # View the one-plate edge of each lens. Its underside sockets are concealed
    # below the belt rather than facing outwards through a vertical clear tile.
    car.fill([length-1], rows, range(4, deck-1), car.fit["body_color"])
    car.fill([length-1], rows, [deck-1], 0)
    y = 1
    while y < width-1:
        span = min(4, width-1-y)
        car.place("2431" if span == 4 else "3069b", 36, length-1, y+(span-1)/2,
                  deck+1, "continuous SUV tail lights", 18, QUARTER)
        y += span
    car.fit.setdefault("lamp_layout", {}).update(rear="edge-on one-plate light bar",
        rear_lens_ldraw=36, rear_lens_height_mm=3.2, rear_lens_lengths_studs=[4, 2])
