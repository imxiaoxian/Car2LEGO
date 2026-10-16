"""Layered SUV chassis with fitted bonnet and native curved roof shoulders."""
import numpy as np

from .surfaces import place_shell, place_roof_bows
from .glazing import place_side_windows, place_split_headlamps, place_tail_light_bar


def design_sculpted_suv(fit):
    from .carfit import Car, IDENTITY, HALF, QUARTER, BACK_QUARTER
    car = Car(fit)
    length,width,paint = (fit[k] for k in ("length_studs","width_studs","body_color"))
    center=(width-1)/2
    start,end=fit["roof_start_stud"],fit["roof_end_stud"]
    roof=fit["roof_top_plates"]
    glass=roof-3
    deck=glass-fit["windscreen_height_plates"]
    fit["deck_top_plates"]=deck
    cabin_width=fit["cabin_width_studs"]
    left=(width-cabin_width)//2
    cabin=range(left,left+cabin_width)
    sides=(left,left+cabin_width-1)
    inner=range(left+1,left+cabin_width-1)
    edges=(0,1,width-2,width-1)
    car.fill(range(1,length),range(2,width-2),range(2,4),0)
    car.fill(range(length),range(width),range(4,deck-2),paint)
    car.fill(range(start-2,end+2),range(width),[3],0)
    car.fill(range(start-3,end+4),range(1,width-1),range(deck-2,deck),paint)
    car.clear(range(start-2,end+3),inner,range(5,deck))
    car.fill(range(start-2,end+3),inner,[4],0)

    # Curved shoulders rise inward to the narrow cabin instead of full-width walls.
    occupied=set()
    features=" ".join(fit.get("reference_appearance",{}).get("distinctive_features",[])).lower()
    rim_color=0 if "dark alloy" in features or "black wheels" in features else 72
    for axle,wheel in zip(fit["axles_studs"],fit["wheel_families"]):
        first=int(axle-2.5)
        occupied.update(range(first,first+6))
        car.clear(range(first,first+6),edges,range(2,deck+2))
        arch_height=int(np.ceil(4.75+wheel["diameter_mm"]/6.4+1))
        car.fill([first,first+5],edges,range(4,arch_height-3),paint)
        x0=int(axle-.5)
        car.clear([x0,x0+1],range(width),[3,4,5])
        for side in (-1,1):
            y=center+side*(center-2)
            car.place("3700",0,axle,y,6,"axle mounting",6)
            car.fill([x0,x0+1],[int(y)], [2],0)
            car.place("62361",0,axle,center+side*center,arch_height,"wheel arches",12,
                      BACK_QUARTER if side==-1 else QUARTER)
            outside,inside=(0,1) if side==-1 else (width-1,width-2)
            car.fill([x0,x0+1],[inside],[arch_height-1],paint)
            car.place("3068b",paint,axle,(outside+inside)/2,arch_height+1,"smooth arch crowns",14)
            for x,rotation in ((first+.5,QUARTER),(first+4.5,BACK_QUARTER)):
                car.place("11477",paint,x,outside,arch_height-2,"rounded arch shoulders",14,rotation)
            wheel_y=center+side*wheel["track_studs"]/2
            car.place(wheel["tyre"],0,axle,wheel_y,4.75,"tyres",18)
            car.place(wheel["rim"],rim_color,axle,wheel_y,4.75,"wheel rims",18,IDENTITY if side==1 else HALF)
        car.place({8:"3707",10:"3737",12:"3708"}[width],0,axle,center,4.75,"axles",7,QUARTER)
    # With an eight-stud cabin there is only one stud between glass and body
    # edge. Long tiles leave that space clear and cap the SNOT door mounts.
    belt=[x for x in range(length) if x not in occupied and x != start-1]
    for outside in (0,width-1):
        car.clear(belt,[outside],range(deck-2,deck+2))
        car.fill(belt,[outside],range(4,deck-2),paint)
        car.tiles(belt,[outside],deck-1,paint,"modular beltline",14)

    bonnet=list(range(1,start-3))
    source=np.asarray(fit["height_profile_studs"])
    target=source[bonnet]/source.max()*roof
    target += deck-float(target[-1])
    plan=place_shell(car,bonnet,range(2,width-2),target,paint,"modular bonnet",14)
    fit["surface_fitting"]={"method":"native shell modules; area error + seam and small-part penalties", "bonnet":plan}
    car.fill([start-3,start-2],cabin,range(4,deck),paint)
    car.place(fit["windscreen_part"],40,start-1,center,glass,"front windscreen",16,QUARTER)
    car.place(fit["windscreen_part"],40,end+1,center,glass,"rear windscreen",16,BACK_QUARTER)
    car.fill(range(end+2,end+4),cabin,range(4,deck),paint)
    inset=2 if fit["windscreen_part"] == "62576" else 0
    place_side_windows(car,start+inset,end-inset,sides,glass,deck,four_doors=True)
    car.fill(range(start-1,end+2),cabin,[glass],0)
    roof_color=fit.get("roof_color",0)
    roof_x=range(start-1,end-1)
    car.fill(roof_x,inner,[glass+1],roof_color)
    place_roof_bows(car,roof_x,left,cabin_width,glass+1,roof_color)
    fit["surface_fitting"]["roof"]=place_shell(car,roof_x,range(left+2,left+cabin_width-2),
                                               [roof]*len(roof_x),roof_color,"modular roof center",18,
                                               floor=glass+1,flat_only=True)
    car.clear(roof_x,[left+1,left+cabin_width-2],[glass+1])
    rear_roof=range(end-1,end+3)
    fall=np.array([-.0768424,-.3718063,-.9758047,-1.9244237])
    source=np.asarray(fit["height_profile_studs"])
    drop=(source[end-1]-source[min(end+4,length-1)])/source.max()*roof
    fall=fall*float(np.clip(drop/1.85,0,1))
    fit["surface_fitting"]["rear_roof"]=place_shell(car,rear_roof,cabin,roof+fall,roof_color,
                                                      "raked roof modules",18,floor=glass)

    for side in (-1,1):
        outside=0 if side==-1 else width-1
        facing=IDENTITY if side==-1 else HALF
        panel=(1,0,0,0,0,side,0,-side,0)
        door_first=int(fit["axles_studs"][0]+3.5)
        door_last=int(fit["axles_studs"][1]-3.5)
        door_span=door_last-door_first+1
        front_span=6 if door_span >= 10 else 4
        rear_span=4 if door_span >= 8 else 2
        fit["native_module_dimensions_mm"]={"door_length":front_span*8,"door_panel_height":16}
        for door_start,span in ((door_first,front_span),(door_last-rear_span+1,rear_span)):
            for x in (door_start,door_start+span-1):
                car.clear([x],[outside],range(deck-5,deck-2))
                car.place("87087",paint,x,outside,deck-2,"door mounts",9,facing)
            car.place({6:"69729",4:"87079",2:"3068b"}[span],paint,door_start+(span-1)/2,
                      center+side*(center+.9),deck-4.5,"door skin",18,panel)
        x=start-1
        car.fill([x],[outside],range(4,deck-2),paint)
        car.place("4070",paint,x,outside,deck+1,"mirror mounts",13,facing)
        car.place("24246",0,x,center+side*(center+.7),deck-.25,"mirrors",18,panel)
        car.place("3070b",paint,x,outside,deck+2,"mirror caps",18)

    nose=max(7,round(float(target[0])))
    car.clear([0],range(width),range(nose,40))
    car.fill([0],range(width),range(4,nose),paint)
    car.fill([0],range(width),[3],0)
    place_split_headlamps(car,nose,width)
    car.tiles([0],[3,4,5,6] if width==10 else range(3,width-3),nose+1,paint,"nose center",18)
    front=(0,1,0,0,0,1,1,0,0)
    intake_edge=3 if "rectangular projector" in fit["lamp_layout"]["front"] else 2
    for y in range(intake_edge,width-intake_edge):
        car.clear([0],[y],range(nose-4,nose-1))
        car.place("87087",0,0,y,nose-1,"fascia mounts",9,QUARTER)
    for y in np.arange(intake_edge+.5,width-intake_edge,2):
        car.place("3069b",0,-.9,y,nose-2.25,"front intake",18,front)
    car.fill(range(end+4,length),range(1,width-1),range(deck-2,deck),paint)
    place_shell(car,range(end+4,length-1),range(2,width-2),np.linspace(deck+2,deck+1,length-end-5),
                paint,"modular tailgate",14)
    # Surface supports must not refill the reserved shafts or native mounting volumes.
    for axle in fit["axles_studs"]:
        first=int(axle-2.5)
        wheel=fit["wheel_families"][fit["axles_studs"].index(axle)]
        arch_height=int(np.ceil(4.75+wheel["diameter_mm"]/6.4+1))
        car.clear(range(first,first+6),edges,range(2,arch_height-1))
        car.fill([first,first+5],edges,range(4,arch_height-3),paint)
        x0=int(axle-.5)
        car.clear([x0,x0+1],edges,[arch_height])
        car.clear([x0,x0+1],range(width),[4,5])
        car.clear([x0,x0+1],[2,width-3],[3,4,5])
    place_tail_light_bar(car,deck,width,length)
    rear=(0,-1,0,0,0,1,-1,0,0)
    for y in range(1,width-1,4):
        span=min(4,width-1-y)
        part="87079" if span == 4 else "3068b"
        for yy in (y,y+span-1):
            car.clear([length-1],[yy],range(deck-4,deck-1))
            car.place("87087",paint,length-1,yy,deck-1,"tailgate panel mounts",9,BACK_QUARTER)
        car.place(part,paint,length-1+.9,y+(span-1)/2,deck-3.5,"smooth tailgate fascia",18,rear)
    # A transverse layer ties the otherwise side-by-side floor bricks together.
    car.fill([end-1],range(2,width-2),[4],72)
    car.fill(range(end-2,end),range(width),[5],0)
    car.fill([end],range(2,width-2),[5],0)
    car.pack()
    for y in (center-1,center+1):
        car.place("4079",0,start+1.5,y,6,"front seats",15,QUARTER)
        car.place("4079",0,end-.5,y,7,"rear seats",15,QUARTER)
    return car
