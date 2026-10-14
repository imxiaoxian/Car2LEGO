"""Concrete delivery requirements; feature tags are not appearance evidence."""

from .scene import AssemblyScene
from .requirements import scene_requirements, mechanism_checks


VISUAL_REQUIREMENTS = (
    ("silhouette", "车型轮廓与姿态", {"wedge_bonnet", "curved_nose_corner"}),
    ("arches", "轮拱与车身曲面", {"curved_wheel_arch", "rear_haunch_curve"}),
    ("lights", "前后灯组", {"recessed_headlight", "headlight", "taillight", "round_taillight"}),
    ("glazing", "风挡与透明件", {"raked_windshield", "transparent_engine_cover"}),
    ("intakes", "侧进气口与百叶", {"recessed_side_intake", "engine_louvres", "rear_louvres"}),
    ("wing", "尾翼与尾部结构", {"full_width_rear_wing", "rear_wing"}),
    ("engine", "发动机舱与发动机细节", {"v8_engine_block", "engine_block", "v8_intake_ribs"}),
    ("seats", "座椅与座舱布局", {"bucket_seat", "seat", "seat_back"}),
    ("interior", "仪表台、方向盘与内饰", {"dashboard", "steering_wheel", "console_mount"}),
    ("door_panels", "门板与门槛", {"door_panel", "side_sill", "door_inner_panel"}),
    ("engine_detail", "发动机细节", {"v8_intake_ribs", "engine_cylinder", "exhaust"}),
    ("underbody", "底盘与承重结构", {"floor", "load_bearing_spine", "spine_bridge"}),
    ("suspension_detail", "悬挂结构", {"suspension_arm", "spring", "hub"}),
)
MECHANISM_LABELS = {"rolling_wheels": "车轮滚动", "front_hood": "前盖开合", "engine_cover": "发动机盖开合",
                    "doors": "车门开合", "steering": "前轮转向", "independent_suspension": "独立悬挂"}


def delivery_requirements(scene: AssemblyScene, mechanisms: list[dict]) -> dict:
    f40 = scene.vehicle.get("make", "").lower() == "ferrari" and scene.vehicle.get("model", "").lower().replace(" ", "") == "f40"
    policy = scene_requirements(scene)
    feature_tags = {key: tags for key, _, tags in VISUAL_REQUIREMENTS}
    checks = []
    for requirement in policy["visual_requirements"]:
        id, tags = requirement["id"], feature_tags.get(requirement["id"], set())
        parts = [p for p in scene.parts if p.feature in tags]
        checks.append({**requirement, "status": "unverified",
                       "candidate_parts": [p.id for p in parts], "modules": sorted({p.module for p in parts}),
                       "evidence": None})
    checks.extend(mechanism_checks(policy, mechanisms))
    return {"version": "precision_delivery_v2", "status": "unverified", "scale": scene.scale,
            "requirements_version": policy["version"], "physical_checks": policy["physical_checks"],
            "target_image_url": "/delivery/f40-appearance-target.png" if f40 else None,
            "target_scope": "visual_finish" if f40 else "vehicle_specific_reference_required",
            "vehicle_recipe_scope": "f40_specialized" if f40 else "experimental_generic",
            "vehicle_recipe_verified": False,
            "checks": checks, "required_evidence": policy["required_evidence"]}
