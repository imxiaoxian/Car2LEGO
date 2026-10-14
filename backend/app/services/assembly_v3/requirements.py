"""Versioned acceptance policies shared by planning, checks and the public API."""

from copy import deepcopy


POLICY_VERSION = "scale_requirements_v1"
SCALES = ("1:38", "1:24", "1:16", "1:12")
MECHANISMS = {
    "rolling_wheels": ("车轮滚动", 4), "front_hood": ("前盖开合", 1),
    "engine_cover": ("发动机盖开合", 1), "doors": ("车门开合", 2),
    "steering": ("前轮联动转向", 1), "independent_suspension": ("四轮独立悬挂", 4),
}
VISUALS = {
    "silhouette": "车型轮廓与姿态", "arches": "轮拱与车身曲面", "lights": "前后灯组",
    "glazing": "风挡与透明件", "intakes": "原车进气口与百叶", "wing": "原车尾翼与尾部结构",
    "engine": "发动机舱布局", "seats": "座椅与座舱布局", "interior": "仪表台、方向盘与内饰",
    "door_panels": "门板、门槛与开启边界", "engine_detail": "发动机管路与分层细节",
    "underbody": "底盘、排气与承重结构", "suspension_detail": "悬挂、轮毂与轮拱间隙",
}
OVERALL = ["length", "width", "height", "wheelbase"]
TYRES = ["front_tyre_diameter", "rear_tyre_diameter"]
TYRE_WIDTHS = ["front_tyre_width", "rear_tyre_width"]
GLASS = ["windshield_width", "windshield_height", "windshield_rake"]
DOORS = ["door_length", "door_height", "door_opening_angle"]
TRACKS = ["front_track", "rear_track"]
ENGINE = ["engine_length", "engine_width", "engine_height"]
EXTERIOR = ["overview", "chassis", "front", "body", "rear", "wheels"]
EVIDENCE = ["real_parts_renders", "appearance_comparison", "digital_validation",
            "export_roundtrip", "studio_open_check", "physical_build_check"]


def _policy(scale, label, description, capabilities, visual, detail_views, measurements,
            recommended, physical_checks, tyre_tolerance, width_tolerance, max_step_parts):
    return {
        "version": POLICY_VERSION, "scale": scale, "label": label, "description": description,
        "visual_requirements": [{"id": key, "label": VISUALS[key], "detail": detail} for key, detail in visual],
        "mechanisms": [{"id": key, "label": MECHANISMS[key][0], "minimum_instances": MECHANISMS[key][1]}
                       for key in capabilities],
        "reference_views": EXTERIOR + detail_views,
        "required_measurements": measurements, "recommended_measurements": recommended,
        "dimension_tolerances_percent": {"length": 5, "wheelbase": 5, "width": 10, "height": 8}
            if scale == "1:38" else {"length": 3, "wheelbase": 3, "width": 5, "height": 5},
        "component_tolerances_percent": {"tyre_diameter": tyre_tolerance, "tyre_width": width_tolerance},
        "physical_checks": physical_checks, "motion_sample_count": 9, "max_step_parts": max_step_parts,
        "required_evidence": list(EVIDENCE),
        "applicability": "Match the exact vehicle. Engine, intake and wing details apply where fitted; unknown applicability requires review.",
        "excluded_mechanisms": ["gearbox", "powered_drivetrain", "motor"],
    }


_COMPACT = [
    ("silhouette", "保留车长、轴距、车顶线和前后悬的辨识度"),
    ("arches", "轮拱位置准确，允许以少量原生曲面件概括"),
    ("lights", "保留灯组位置、形状与主色"),
    ("glazing", "保留风挡轮廓和透明座舱"),
    ("intakes", "保留原车最具辨识度的开口"),
    ("wing", "保留原车尾翼或尾部特征"),
]
_STANDARD = [
    ("silhouette", "完整车身轮廓、车头楔形与前后姿态"),
    ("arches", "连续轮拱、翼子板与侧面轮廓"),
    ("lights", "灯组、格栅与周围车身分区"),
    ("glazing", "透明风挡，核对宽度、斜高与倾角"),
    ("intakes", "原车进气口、格栅和百叶可辨识"),
    ("wing", "尾翼、尾灯与尾部层次符合原车"),
    ("engine", "可打开盖板下有简化发动机舱布局"),
    ("seats", "简化座椅、靠背与座舱布局"),
    ("interior", "简化仪表台与方向盘"),
]
_ADVANCED = [
    (key, detail) for key, detail in _STANDARD if key not in ("engine", "seats", "interior")
] + [
    ("engine", "发动机位置、缸体与可见进气结构"),
    ("seats", "分体座椅、靠背、头枕与座舱间距"),
    ("interior", "仪表台、方向盘、中控与脚部空间"),
    ("door_panels", "左右门板、门槛和开门间隙"),
]
_PRECISION = [(key, detail) for key, detail in _ADVANCED if key != "interior"] + [
    ("interior", "精细仪表、中控、踏板与分层内饰"),
    ("engine_detail", "发动机舱管路、进排气与分层结构"),
    ("underbody", "底盘、承重路径与分层覆盖件"),
    ("suspension_detail", "四轮悬挂结构及压缩、回弹、转向空间"),
]
_POLICIES = {
    "1:38": _policy("1:38", "紧凑外观", "辨识轮廓与滚动车轮，内饰和开合机构不作为必需项。",
        ["rolling_wheels"], _COMPACT, [], OVERALL + TYRES,
        TYRE_WIDTHS + ["windshield_rake"], ["结构承重", "四轮滚动"], 15, 20, 12),
    "1:24": _policy("1:24", "完整外观", "完整车身、简化座舱与发动机舱，前后盖可开合。",
        ["rolling_wheels", "front_hood", "engine_cover"], _STANDARD,
        ["engine_bay", "cockpit", "seats", "hood_opening", "hood_hinges", "engine_details", "lights", "side_intakes"],
        OVERALL + TYRES + TYRE_WIDTHS + GLASS, TRACKS + DOORS + ["seat_width"] + ENGINE,
        ["结构承重", "四轮滚动", "前盖与发动机盖开合"], 5, 10, 12),
    "1:16": _policy("1:16", "精细座舱", "精细轮拱、内饰和发动机布局，增加双门开合与前轮转向。",
        ["rolling_wheels", "front_hood", "engine_cover", "doors", "steering"], _ADVANCED,
        ["engine_bay", "cockpit", "seats", "hood_opening", "hood_hinges", "engine_details", "lights", "side_intakes",
         "doors", "door_hinges", "dashboard", "steering"],
        OVERALL + TYRES + TYRE_WIDTHS + GLASS + TRACKS + DOORS + ["seat_width"], ENGINE,
        ["结构承重", "四轮滚动", "前后盖与双门开合", "左右转向极限及中间位置"], 5, 7.5, 10),
    "1:12": _policy("1:12", "结构与机构", "分层车身、精细发动机和底盘，增加四轮独立悬挂。",
        list(MECHANISMS), _PRECISION,
        ["engine_bay", "cockpit", "seats", "hood_opening", "hood_hinges", "engine_details", "lights", "side_intakes",
         "doors", "door_hinges", "dashboard", "steering", "suspension", "underbody"],
        OVERALL + TYRES + TYRE_WIDTHS + GLASS + TRACKS + DOORS + ["seat_width"] + ENGINE
            + ["front_rim_diameter", "rear_rim_diameter"], [],
        ["结构承重", "四轮滚动", "前后盖与双门开合", "转向全行程", "四轮悬挂压缩与回弹", "悬挂承重与耐用性"], 3, 5, 8),
}


def requirements_for_scale(scale: str) -> dict:
    if scale not in _POLICIES:
        raise ValueError("Scale is not available for assembly_v3")
    return deepcopy(_POLICIES[scale])


def scene_requirements(scene) -> dict:
    policy = scene.planning.get("scale_requirements")
    if policy is None:
        return requirements_for_scale(scene.scale)
    if policy.get("scale") != scene.scale or policy.get("version") != POLICY_VERSION:
        raise ValueError("Scene scale requirements snapshot is incompatible")
    return deepcopy(policy)


def mechanism_checks(policy: dict, reports: list[dict]) -> list[dict]:
    checks = []
    for requirement in policy["mechanisms"]:
        candidates = [m for m in reports if m["capability"] == requirement["id"]]
        # Multiple reports of one joint/module must not stand in for four wheels.
        instances = {m.get("child") or m["id"] for m in candidates}
        passed = len(instances) >= requirement["minimum_instances"] and all(m["status"] == "passed" for m in candidates)
        checks.append(requirement | {"status": "passed" if passed else "failed", "reported_instances": len(instances),
            "evidence": "digital_motion_sweep" if candidates else None})
    return checks
