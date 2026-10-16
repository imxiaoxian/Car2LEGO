"""Compact wedge architecture with native door and window subassemblies."""
import numpy as np

from .vehicle import constraint_targets


def applies(spec):
    return "countach" in str((spec or {}).get("model", "")).lower()


def fit_wedge(fit, spec, brief=None):
    length, width = fit["length_studs"], fit["width_studs"]
    targets = constraint_targets(spec, length, fit["target_scale_denominator"])["target_model_mm"]
    profile = np.asarray(fit["height_profile_studs"])
    cabin_region = np.arange(round(length*.38), round(length*.65))
    peak = int(cabin_region[np.argmax(profile[cabin_region])])
    start = int(np.clip(peak-1, 11, length-11))
    ground = 4.75*3.2-12
    roof = int(np.clip(round((targets["height"]+ground)/3.2), 14, 16))
    wheels = []
    for axle, tyre, rim, breadth in (("front", "18977", "18976", 11.2),
                                     ("rear", "89201", "55982", 14.0)):
        wheels.append(dict(tyre=tyre, rim=rim, diameter_mm=24., width_mm=breadth,
            track_studs=round(targets.get(axle+"_track", (width-2)*8)/4)/2,
            center_height_plates=4.75, arch="62361", arch_span_studs=6))
    fit.update(recipe="wedge-v3", body_family="sports_car", family_builder="wedge",
        styling_prior="lamborghini-countach", roof_start_stud=start, roof_end_stud=start+3,
        roof_top_plates=roof, deck_top_plates=10, ground_y_mm=ground,
        cabin_width_studs=8, wheel_families=wheels, windscreen_part="92583",
        fitted_windscreen_angle_degrees=45., reference_appearance=brief or {},
        layout=dict(engine_position="rear", rear_wing_default=True,
            roof_interval_studs=[start-1, start+3], bonnet_interval_studs=[0, start-4]),
        architecture_reference=dict(set="76908", official_replica=False,
            instruction_url="https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6409498.pdf",
            reviewed_pages=[46, 56, 66, 76, 78, 79],
            adapted_modules=["sloped nose", "two-seat cabin", "rear intake towers", "two-pylon wing"]),
        design_prior="compact Countach wedge; native connected door/window assemblies")
    return fit


def design_wedge(fit, rear_wing=True):
    from .carfit import Car, IDENTITY, QUARTER, HALF, BACK_QUARTER
    car = Car(fit)
    length, width, paint = (fit[k] for k in ("length_studs", "width_studs", "body_color"))
    center = (width-1)/2
    start, end, roof = (fit[k] for k in ("roof_start_stud", "roof_end_stud", "roof_top_plates"))
    inner, edges = range(2, width-2), (0, 1, width-2, width-1)
    car.fill(range(1, length), inner, range(2, 4), 0)
    car.fill(range(length), range(width), range(4, 7), paint)
    occupied = set()
    for axle, wheel in zip(fit["axles_studs"], fit["wheel_families"]):
        first, x0 = int(axle-2.5), int(axle-.5)
        occupied.update(range(first, first+6))
        car.clear(range(first, first+6), edges, range(2, 12))
        car.fill([first, first+5], edges, range(4, 7), paint)
        for side in (-1, 1):
            outside, inside = (0,1) if side == -1 else (width-1,width-2)
            car.place("3700", 0, axle, center+side*(center-2), 6, "axle mounting", 6)
            car.fill([x0,x0+1], [inside], [9], paint)
            car.place("62361", paint, axle, outside, 10, "wheel arches", 12,
                      BACK_QUARTER if side == -1 else QUARTER)
            car.place("3068b", paint, axle, (outside+inside)/2, 11, "smooth arch crowns", 14)
            for x, rotation in ((first+.5,QUARTER), (first+4.5,BACK_QUARTER)):
                car.place("11477", paint, x, outside, 8, "angular fender edges", 14, rotation)
            wheel_y = center+side*wheel["track_studs"]/2
            car.place(wheel["tyre"], 0, axle, wheel_y, 4.75, "tyres", 18)
            car.place(wheel["rim"], 71, axle, wheel_y, 4.75, "wheel rims", 18,
                      IDENTITY if side == 1 else HALF)
        car.place({8:"3707",10:"3737",12:"3708"}[width], 0, axle, center, 4.75, "axles", 7, QUARTER)
    for first, height in ((0, 7), (4, 10)):
        for y in np.arange(2.5, width-2, 2):
            ys = [int(y-.5), int(y+.5)]
            car.clear(range(first,first+4), ys, range(4,20))
            car.fill(range(first,first+4), ys, range(4,height-3), paint)
            car.place("30363", paint, first+3, y, height, "modular wedge bonnet", 13, QUARTER)
            car.tiles([first+3], ys, height+1, paint, "bonnet rear seam", 14)
    front_lens_rotation = (0,1,0,0,0,1,1,0,0)
    for y in (.5, width-1.5):
        ys = [int(y-.5),int(y+.5)]
        car.clear(range(2),ys,range(4,20))
        car.fill([0],ys,[3],0)
        for lamp_y in ys:
            car.place("87087",0,0,lamp_y,7,"front lamp housings",13,QUARTER)
            car.place("3070b",47,-.9,lamp_y,5.75,"paired front lamp lenses",14,front_lens_rotation)
        car.fill([1],ys,range(4,6),paint)
        car.tiles([1],ys,7,paint,"headlamp upper surrounds",14)
    car.fill([0],range(width),[3],0)

    # Glass sockets sit directly on the door's studs. Both remain in the same
    # module when the assembly is selected or subsequently given a door hinge.
    door_start = start-1
    car.clear(range(door_start,end+2),range(width),range(4,20))
    car.fill(range(door_start,end+2),range(1,width-1),[3],0)
    assemblies = []
    for side, side_name in ((-1,"left"),(1,"right")):
        y = 1 if side == -1 else width-2
        rotation = HALF if side == -1 else IDENTITY
        module = side_name+" scissor door"
        x = door_start+1.5
        car.place("14718",paint,x,y,10,module,15,rotation)
        car.place("15207",40,x,y,13,module,16,rotation)
        assemblies.append(dict(module=module, door_part="14718", glass_part="15207",
            connection="glass underside sockets on opaque door top studs", joint_height_plates=10,
            opening_verified=False))
        car.fill([end], [y], range(4,roof-2),paint)
        car.fill([end+1],[y],range(4,roof-3),paint)
        car.place("4286",paint,end+1,y,roof,"rear buttresses",16,BACK_QUARTER)
        car.fill([door_start-1],[y],range(4,roof-6),paint)
        car.place("4286",paint,door_start-1,y,roof-3,"raked A pillars",16,QUARTER)
        car.place("3070b",0,door_start-1,y,roof-2,"black wing mirrors",17)
    car.fill(range(8,door_start),inner,range(4,roof-7),0)
    # Its underside sockets lie 44 LDU below the origin; a half plate offset
    # seats the mould on the support grid without resizing it.
    car.place("92583",40,start-1,center,roof-.5,"raked front windscreen",16,QUARTER)
    car.fill(range(start-1,end+1),range(1,width-1),[roof-2],paint)
    car.tiles(range(start-1,end+1),range(1,width-1),roof,paint,"modular roof",18)
    car.fill([end],inner,range(4,roof-2),paint)
    for y in (center-1,center+1):
        car.place("4079",4,start+.5,y,6,"red seats",15,QUARTER)
    car.place("3829c01",0,start-2,center-1,5,"steering wheel",15,QUARTER)
    car.fill(range(end+2,length),inner,range(5,8),paint)
    for side in (-1,1):
        y = 1 if side == -1 else width-2
        car.fill(range(end+2,end+4),[y],range(8,10),paint)
        car.place("3298",paint,end+3,y,13,"rear intake towers",16,BACK_QUARTER)
        car.tiles([end+2],[y],11,0,"black side intakes",18)
    for x in range(end+3,length-2):
        for y in (center-1,center+1):
            car.place("2412b",0,x,y,9,"engine louvers",16,QUARTER)
    car.tiles([length-2,length-1],inner,9,paint,"smooth rear deck",18)
    rear_rotation = (0,-1,0,0,0,-1,1,0,0)
    for ys in ((1,2),(width-3,width-2)):
        car.clear([length-1],ys,range(5,9))
        car.fill([length-1],ys,[4],0)
        for y in ys:
            car.place("87087",0,length-1,y,8,"rear lamp housings",16,BACK_QUARTER)
            color = 57 if y in (1,width-2) else 36
            car.place("3070b",color,length-.1,y,6.75,"segmented tail lamp lenses",18,rear_rotation)
    if rear_wing:
        for y in (2,width-3):
            car.fill([length-3],[y],range(8,roof),paint)
        car.fill([length-3,length-2],range(width),[roof-1],paint)
        car.tiles([length-3,length-2],range(width),roof+1,paint,"smooth rear wing",20)

    # Restore the shaft and mount reservations after all surface supports.
    for axle in fit["axles_studs"]:
        first,x0 = int(axle-2.5),int(axle-.5)
        car.clear(range(first,first+6),edges,range(2,9))
        car.fill([first,first+5],edges,range(4,7),paint)
        car.clear([x0,x0+1],range(width),[4,5])
        car.clear([x0,x0+1],[2,width-3],[3,4,5])
        car.fill([x0,x0+1],[2,width-3],[2],0)
    for outside in (0,width-1):
        belt = [x for x in range(length) if x not in occupied and not door_start <= x <= end+1]
        car.tiles(belt,[outside],8,paint,"smooth sill shoulders",14)
    car.pack()
    fit["door_assemblies"] = assemblies
    fit["native_module_dimensions_mm"] = dict(door_length=32.,door_panel_height=19.2)
    fit["lamp_layout"] = dict(version=4, lens_scaling=False,
        front="four clear 1x1 lenses on side studs in black housings",
        rear="red and amber 1x1 lenses on side studs in black housings",
        mounts="87087", lens="3070b", physically_verified=False)
    return car
