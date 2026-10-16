"""Camera and dependency contracts for a consistent, modular vehicle reference set."""
from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class Shot:
    id: str
    camera: str
    modules: tuple
    state: str = "closed; wheels straight"
    parents: tuple = ("overview",)
    category: str = "detail"
    focus: str = ""

    def record(self):
        return asdict(self)

    def instructions(self):
        framing = ("Show the complete car with a 15 percent margin. "
                   if self.category in {"anchor", "whole"} else
                   "Show this single detail with enough surrounding bodywork to establish its attachment. ")
        return (f"ONE image, ONE camera: {self.camera}. State: {self.state}. {framing}"
                f"Focus: {self.focus}. Use the exact identity, trim, paint, wheels and interior of the "
                "supplied identity anchor and parent reference images. Preserve asymmetric features. "
                "Use a white studio background and uniform sharp lighting. No contact sheet, extra views, "
                "captions, dimensions, diagrams or duplicated cars. This is a real vehicle appearance "
                "reference; LEGO construction is designed separately. Hidden mechanisms are uncertain "
                "design inferences, never measured evidence. Keep adjacent panel edges visible.")


def reference_plan(identity=""):
    shots = [Shot("overview", "front-left three-quarter, elevation 15 degrees, long focal length",
                  ("identity",), category="anchor", parents=(), focus="exact vehicle and variant")]
    for name, camera in [("front", "orthographic front at hub height"),
                         ("back", "orthographic rear at hub height"),
                         ("left", "orthographic left side, nose points image LEFT"),
                         ("right", "orthographic right side, nose points image RIGHT"),
                         ("top", "orthographic top, nose points image TOP"),
                         ("front_left", "front-left three-quarter, elevation 25 degrees"),
                         ("front_right", "front-right three-quarter, elevation 25 degrees"),
                         ("rear_left", "rear-left three-quarter, elevation 25 degrees"),
                         ("rear_right", "rear-right three-quarter, elevation 25 degrees")]:
        shots.append(Shot(name, camera, ("body", "cabin", "front", "rear"), category="whole"))
    details = [
        ("windscreen", "front-left oblique close-up", ("glazing", "cabin"), ("front_left", "top"), "closed", "windscreen thickness, A pillars, cowl and roof header"),
        ("door_left_closed", "left door exterior at beltline", ("doors", "glazing"), ("left",), "left door closed", "door panel, glass, frame, seals and fixed quarter glass ownership"),
        ("door_right_closed", "right door exterior at beltline", ("doors", "glazing"), ("right",), "right door closed", "door panel, glass, frame, seals and fixed quarter glass ownership"),
        ("door_left_open", "left front oblique door jamb", ("doors", "hinges", "cabin"), ("left", "front_left"), "left door fully open in its real opening direction", "glass stays attached to moving door; hinge, sill, latch and fixed body context"),
        ("door_right_open", "right front oblique door jamb", ("doors", "hinges", "cabin"), ("right", "front_right"), "right door fully open in its real opening direction", "glass stays attached to moving door; hinge, sill, latch and fixed body context"),
        ("headlamps", "low front-left close-up", ("lights", "front"), ("front", "front_left"), "closed; lamps off", "lens outline, housing depth, reflectors, segment dividers and bumper mounting"),
        ("taillamps", "rear-left close-up", ("lights", "rear"), ("back", "rear_left"), "closed; lamps off", "tail lamp lenses, recesses, dividers, fascia and hatch edge"),
        ("front_cabin_join", "front-left oblique cowl and fender close-up", ("front", "cabin"), ("left", "front_left"), "closed", "continuous hood-fender-cowl-A pillar boundary and intentional crease lines"),
        ("rear_cabin_join", "rear-left oblique buttress close-up", ("rear", "cabin"), ("left", "rear_left"), "closed", "rear glass seating, buttress, rear deck and continuous quarter panel boundary"),
        ("dashboard", "through open driver door toward dashboard", ("interior", "cabin"), ("front_left", "left"), "driver door open", "dashboard, gauges, steering wheel, console and interior colours"),
        ("seats_pedals", "through open passenger door toward seats and footwell", ("interior", "cabin"), ("front_right", "right"), "passenger door open", "both front seats, pedals, seat rails and cabin floor"),
        ("front_running_gear", "low left front wheel and wheelwell close-up", ("wheels", "steering", "suspension"), ("left", "front_left"), "front wheel steered 20 degrees, normal ride height", "tyre and rim dimensions, hub, visible suspension and arch clearance; hidden parts uncertain"),
        ("rear_running_gear", "low left rear wheel and wheelwell close-up", ("wheels", "suspension"), ("left", "rear_left"), "normal ride height", "tyre, rim, hub, visible suspension and rear arch clearance"),
        ("front_cover_open", "front-left oblique open bonnet", ("front", "hinges"), ("front_left", "top"), "front cover fully open", "moving cover perimeter, hinge region, compartment and stationary cowl"),
        ("rear_cover_open", "rear-left oblique open rear cover", ("rear", "hinges"), ("rear_left", "top"), "rear cover fully open", "exact moving panel grouping, hinges and stationary cabin; preserve full clamshell where applicable"),
        ("powertrain_cargo", "overhead close-up into open rear service compartment", ("rear", "powertrain"), ("rear_left", "top"), "service cover open", "correct powertrain or storage layout for this variant; no invented ICE for an electric car"),
    ]
    shots += [Shot(name, camera, modules, state, ("overview", *parents), focus=focus)
              for name, camera, modules, parents, state, focus in details]
    name = identity.lower().replace(" ", "")
    if "countach" in name:
        shots += [Shot("scissor_hinge", "left door hinge exterior oblique close-up", ("doors", "hinges"),
                       "left scissor door halfway open", ("overview", "door_left_open"), focus="pivot axis, door glass moving with door and sill clearance"),
                  Shot("side_intake", "left rear-quarter side intake close-up", ("body", "rear"),
                       parents=("overview", "rear_left"), focus="Countach intake mouth, scoops and adjacent buttress"),
                  Shot("popup_lamps", "front-left close-up", ("front", "lights", "hinges"),
                       "both pop-up headlamps raised", ("overview", "headlamps"), focus="headlamp pods and pivots with front bonnet context")]
    elif "f40" in name:
        shots.append(Shot("rear_clamshell", "rear-left wide oblique", ("rear", "hinges"),
                          "entire rear clamshell raised", ("overview", "rear_cover_open"),
                          focus="wing, rear glass and rear fenders move together; fixed cockpit stays stationary"))
    elif "forme" in name or "for-me" in name:
        shots.append(Shot("rear_doors", "left rear door exterior oblique", ("doors", "interior"),
                          "rear passenger door fully open", ("overview", "left"),
                          focus="four-door SUV rear door glass belongs to rear door; rear seats and fixed C pillar"))
    validate_plan(shots)
    return shots


def validate_plan(shots):
    table = {shot.id: shot for shot in shots}
    if len(table) != len(shots) or "overview" not in table:
        raise ValueError("Duplicate shots or missing identity anchor")
    visited, active = set(), set()

    def visit(name):
        if name not in table or name in active:
            raise ValueError("Missing or cyclic reference parent")
        if name in visited:
            return
        active.add(name)
        for parent in table[name].parents:
            visit(parent)
        active.remove(name)
        visited.add(name)
    for name in table:
        visit(name)


def shot_fingerprint(shot, parents):
    payload = dict(version=2, shot=shot.record(), parents=parents)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
