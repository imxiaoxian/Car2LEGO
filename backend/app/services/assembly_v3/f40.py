"""Stud-lattice F40 shell with separate scale planning and real-size covering pieces."""

from collections import defaultdict
import math
import networkx as nx

from .recipes import solve_grid, PROFILES, TURN, REVERSE, REAR_FACE
from .scene import AssemblyScene, PartInstance, Module, Joint, Transform, BuildStep, IDENTITY
from .specifications import F40_SPEC, target_dimensions, CAPABILITIES
from .requirements import requirements_for_scale
from .catalog import ports

RIGHT_WHEEL = (0.,0.,-1.,0.,1.,0.,1.,0.,0.)

# Native plate footprints, measured from the local LDraw library (X by Z studs).
PLATES = [(4,2,"3020.dat"), (2,4,"3020.dat"), (3,2,"3021.dat"), (2,3,"3021.dat"),
          (2,2,"3022.dat"), (2,1,"3023.dat"), (1,2,"3023.dat"), (1,1,"3024.dat")]


def cover(cells: set[tuple[int,int]], reverse=False):
    cells=set(cells)
    choices=sorted(PLATES,key=lambda p:(-p[0]*p[1],p[0] if reverse else -p[0]))
    while cells:
        x,z=min(cells,key=lambda p:(p[1],p[0]))
        for w,d,number in choices:
            footprint={(x+i,z+j) for i in range(w) for j in range(d)}
            if footprint <= cells:
                cells -= footprint
                yield x,z,w,d,number
                break


def build_scene(design_id,scale,intent=None,vehicle=None,spec=None,requirements=None):
    intent=intent or {};spec=spec or dict(F40_SPEC)
    policy = requirements or requirements_for_scale(scale)
    target=target_dimensions(spec,scale);grid=solve_grid(target,scale,policy)
    length,width,roof,wb=(grid[k] for k in ("length","width","height","wheelbase"))
    nx_cells,nz_cells=int(width/20),int(length/20)
    rim,tyre,radius,tyre_half=PROFILES[scale]
    red,black=int(intent.get("body_color_id",4)),int(intent.get("accent_color_id",0))
    front,rear=(length-wb)/2,(length+wb)/2
    # Technic bearing axis is 14 LDU above its bottom attachment plane.
    # Pick a plate lattice first, then derive the wheel axis without scaling.
    floor=max(8,round((radius-14)/8)*8)
    radius=floor+14
    deck=round(roof*.57/8)*8
    cabin_start=round(length*.38/20)*20
    cabin_end=round(length*.62/20)*20
    phase=(width/2-10)%20
    bearing_x=20+phase
    parts,modules,joints,steps=[],[],[],[]
    module_map={}
    def module(name,depends=(),structural=False):
        if name not in module_map:
            m=Module(id=name,depends_on=list(depends),structural=structural,recipe_version="f40-shell-3")
            modules.append(m);module_map[name]=m
    module("chassis",structural=True);module("wheel_mounts",["chassis"])
    module("cockpit",["chassis"]);module("engine",["chassis"])
    module("body_frame",["wheel_mounts","cockpit","engine"])
    module("front_hood",["body_frame"]);module("engine_cover",["body_frame"])
    module("doors",["body_frame"]);module("details",["front_hood","engine_cover","doors"])
    def add(name,number,color,x,h,z,rotation=IDENTITY,feature=""):
        p=PartInstance(id=f"{name}_{len(parts):05d}",part_num=number,color_id=color,module=name,
                       transform=Transform(position=(float(x),float(-h),float(z)),rotation=rotation),feature=feature)
        parts.append(p);return p
    def cell_position(x,z):return ((x+.5)*20-width/2,(z+.5)*20)
    def wheel_void(x,h,z):
        if abs(x)<width/2-2*tyre_half-4:return False
        return any((z-axle)**2+(h-radius)**2 < (radius+7)**2 for axle in (front,rear))
    def hood_height(z):return round((deck-16+min(1,z/max(20,cabin_start)) * 16)/8)*8
    occupancy=defaultdict(set)
    for h in range(int(floor),int(roof)+1,8):
        for zi in range(nz_cells):
            for xi in range(nx_cells):
                x,z=cell_position(xi,zi)
                side=abs(x)>width/2-21
                bearing=any(abs(z-az)<21 and abs(abs(x)-bearing_x)<1 for az in (front,rear))
                if bearing and floor<h<=floor+24:continue
                if any(abs(z-az)<=10 for az in (front,rear)) and abs(x)<width/2-tyre_half and abs(h-4-radius)<7:continue
                tail_mount=z>=length-20 and abs(abs(x)-(width/2-30))<1 or z>=length-20 and abs(abs(x)-(width/2-50))<1
                if tail_mount and deck-24<h<=deck:continue
                if wheel_void(x,h-4,z):continue
                if z<20 and abs(x)>width/2-21:continue
                if h<=floor+8:
                    occupancy[("chassis",h,black)].add((xi,zi));continue
                if h==floor+16 and abs(x)<11:
                    occupancy[("chassis",h,black)].add((xi,zi));continue
                # Wheel arch and sill side walls. Cabin glass is reserved separately.
                if side and h<=deck:
                    occupancy[("body_frame",h,black if h==floor+24 else red)].add((xi,zi));continue
                if z<cabin_start:
                    top=hood_height(z)
                    if h<=top and (h<=deck-16 or h>=top-8):
                        name="front_hood" if h>=top-8 and z>=40 and abs(x)<width/2-21 else "body_frame"
                        occupancy[(name,h,red if h>floor+16 else black)].add((xi,zi))
                elif z>=cabin_end:
                    engine_window=abs(x)<width/2-41 and cabin_end+20<z<length-40
                    window_rail=engine_window and abs(x)>width/2-61
                    if (not engine_window and h<=deck) or (engine_window and h==deck) or (window_rail and h<=deck-8):
                        name="engine_cover" if engine_window else "body_frame"
                        occupancy[(name,h,47 if engine_window else red)].add((xi,zi))
                else:
                    pillar=(z<cabin_start+20 or z>=cabin_end-20) and abs(x)>width/2-41
                    if pillar and h<=roof-8:
                        occupancy[("body_frame",h,red)].add((xi,zi))
                    elif h in (roof-8,roof) and cabin_start+10<=z<=cabin_end-10 and abs(x)<width/2-20:
                        occupancy[("cockpit",h,red)].add((xi,zi))
    tiles={"3020.dat":"87079.dat","3021.dat":"26603.dat","3022.dat":"3068b.dat","3023.dat":"3069b.dat","3024.dat":"3070b.dat"}
    all_cells=defaultdict(set)
    for (name,h,color),cells in occupancy.items():all_cells[h].update(cells)
    # Complete layers are tiled with real plates. Alternating long directions crosses seams.
    for (name,h,color),cells in sorted(occupancy.items(),key=lambda item:(item[0][1],item[0][0],item[0][2])):
        smooth={cell for cell in cells if cell not in all_cells[h+8] and name in ("front_hood","cockpit")
                and not (name=="front_hood" and cell[1]<=2)}
        for is_tile,subset in ((False,cells-smooth),(True,smooth)):
            for x,z,w,d,number in cover(subset,(h//8)%2==0):
                px=(x+w/2)*20-width/2;pz=(z+d/2)*20
                rotation=TURN if (number=="3020.dat" and w==2) or (number=="3021.dat" and w==2) or (number=="3023.dat" and w==1) else IDENTITY
                feature="transparent_engine_cover" if color==47 else "side_sill" if name=="body_frame" else name
                add(name,tiles[number] if is_tile else number,color,px,h,pz,rotation,feature)
    # Stepped windscreen follows the intended rake with transparent real-size plates.
    for zi,z in enumerate(range(int(cabin_start)+10,int(cabin_start)+50,20)):
        top=min(roof-8,deck+8+zi*16)
        for x in range(-int(width/2)+50,int(width/2)-40,20):
            for h in range(int(floor)+16,int(top)+1,8):
                cell=(round((x+width/2-10)/20),round((z-10)/20))
                if cell in all_cells[h]:continue
                add("cockpit","3024.dat",47 if h>deck else red,x,h,z,feature="windshield" if h>deck else "dashboard_support")
    for side in (-1,1):
        for z in range(int(cabin_start)+50,int(cabin_end)-20,20):
            x=side*(width/2-30)
            for h in range(int(floor)+16,int(roof)-8,8):
                add("doors","3024.dat",47 if h>deck else red,x,h,z,feature="side_glass" if h>deck else "door_inner")
        for z in (front,rear):
            name=f"wheel_{'left' if side<0 else 'right'}_{'front' if z==front else 'rear'}"
            module(name,["wheel_mounts"])
            centre=side*(width/2-tyre_half)
            wheel_rotation=TURN if side<0 else RIGHT_WHEEL
            add(name,rim,71,centre-side*(6 if rim in ("6014.dat","18976.dat") else 0),radius,z,wheel_rotation,"rim")
            add(name,tyre,0,centre,radius,z,wheel_rotation,"tyre")
            joints.append(Joint(id=name+"_spin",parent="wheel_mounts",child=name,pivot=(centre,-radius,z),axis=(1.,0.,0.),limits=(0.,360.),capability="rolling_wheels"))
        # Round F40 tail lamps on two SNOT mounts, held to the rear fascia.
        for distance in (width/2-30,width/2-50):
            # Side stud of the headlight brick faces the rear, with round lamp
            # underside aligned to that actual connector at Z = length - 4.
            add("details","4070.dat",black,side*distance,deck,length-10,REVERSE,"taillight_mount")
            add("details","6141.dat",36 if distance==width/2-30 else 46,side*distance,deck-10,length-4,REAR_FACE,"taillight")
        for x in (side*(width/2-30),side*(width/2-50)):
            add("details","3069b.dat",47,x,hood_height(30)+8,20,TURN,"headlight")
        wing_x=side*(width/2-30)
        for h in range(int(deck)+8,int(deck)+32,8):
            add("details","3024.dat",red,wing_x,h,length-30,feature="wing_support")
        # Seats stay below the canopy and use a scale-specific floor location.
        seat_z=round((cabin_start+cabin_end)/40)*20
        add("cockpit","4079.dat",red,side*(30+phase),floor+16,seat_z,IDENTITY,"seat")
    # Rear wing spans the measured body width in independent plates.
    # A staggered underlayer joins the outer supports and crosses the upper seams.
    lower={(x,0) for x in range(1,nx_cells-1)}
    for x,z,w,d,n in cover(lower):
        add("details",n,red,(x+w/2)*20-width/2,deck+32,length-30,IDENTITY,"rear_wing_beam")
    wing_cells={(x,0) for x in range(nx_cells)}
    for x,z,w,d,n in cover(wing_cells):
        add("details",n,red,(x+w/2)*20-width/2,deck+40,length-30,IDENTITY,"rear_wing")
    for z in range(int(cabin_end)+40,int(length)-40,40):
        for x in (-(30-phase),30-phase):
            add("engine","3022.dat",72,x,floor+16,z,feature="engine_support")
            add("engine","3022.dat",72,x,floor+24,z,feature="engine_block")
            add("engine","2412b.dat",71,x,floor+32,z+10,feature="engine_detail")
            add("engine_cover","2412b.dat",black,x,deck+8,z+10,feature="engine_louvres")
    axle_sizes=[(40,"32062.dat"),(80,"3705.dat"),(100,"32073.dat"),(120,"3706.dat"),
                (160,"3707.dat"),(200,"3737.dat"),(220,"23948.dat"),(240,"3708.dat")]
    # Independent half-shafts retain standard sizes at large scales.
    socket=next((p for p in ports(rim) if p.semantic=="axle_socket"),None)
    shaft_tip=width/2-tyre_half+(4 if socket and socket.start_capped else socket.length/2 if socket else 0)
    desired=shaft_tip-bearing_x+10
    shaft_length,axle=next(((size,n) for size,n in axle_sizes if size>=desired),(240,"3708.dat"))
    for z in (front,rear):
        for side in (-1,1):
            wheel_name=f"wheel_{'left' if side<0 else 'right'}_{'front' if z==front else 'rear'}"
            shaft=add(wheel_name,axle,black,side*(shaft_tip-shaft_length/2),radius,z,IDENTITY,"axle")
            bearing=add("wheel_mounts","3700.dat",black,side*bearing_x,radius+10,z,TURN,"axle_bearing")
            joint=next(j for j in joints if j.child==wheel_name)
            joint.mounting_parts=(bearing.id,shaft.id)
            joint.implemented=socket is not None
    for capability,name,pivotz in (("front_hood","front_hood",cabin_start-20),("engine_cover","engine_cover",cabin_end+20)):
        joints.append(Joint(id=capability,parent="body_frame",child=name,pivot=(0.,-deck,pivotz),axis=(1.,0.,0.),limits=(0.,65.),capability=capability))
    if scale in ("1:16","1:12"):
        joints.append(Joint(id="doors",parent="body_frame",child="doors",pivot=(width/2-20.,-deck,cabin_start),axis=(0.,1.,0.),limits=(0.,65.),capability="doors"))
        joints.append(Joint(id="steering",parent="chassis",child="wheel_mounts",pivot=(0.,-radius,front),axis=(0.,1.,0.),limits=(-25.,25.),capability="steering"))
    if scale=="1:12":
        joints.append(Joint(id="suspension",kind="prismatic",parent="chassis",child="wheel_mounts",pivot=(0.,-radius,front),axis=(0.,1.,0.),limits=(-8.,8.),capability="independent_suspension"))
    module_map["body_frame"].depends_on.extend(m.id for m in modules if m.id.startswith("wheel_") and m.id!="wheel_mounts")
    graph=nx.DiGraph();graph.add_nodes_from(m.id for m in modules)
    graph.add_edges_from((dep,m.id) for m in modules for dep in m.depends_on)
    by_module={name:[] for name in graph}
    for p in parts:by_module[p.module].append(p)
    for name in nx.topological_sort(graph):
        group=sorted(by_module[name],key=lambda p:(-p.transform.position[1],p.transform.position[2],p.transform.position[0]))
        for offset in range(0,len(group),policy["max_step_parts"]):steps.append(BuildStep(index=len(steps)+1,module=name,parts=[p.id for p in group[offset:offset+policy["max_step_parts"]]]))
    return AssemblyScene(design_id=design_id,vehicle=vehicle or dict(make="Ferrari",model="F40",year=1990),scale=scale,
        specifications=spec,target_ldu=target,parts=parts,modules=modules,joints=joints,steps=steps,
        planning={"solver":"OR-Tools CP-SAT","grid":grid,"required_capabilities":[m["id"] for m in policy["mechanisms"]], "scale_requirements":policy,
                  "wheel_centres_z":[front,rear],"recipe":"f40-shell-3","recipe_verified":False,"intent":intent})
