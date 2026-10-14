"""Curated vehicle identities and appearance goals, independent from set inventory."""

from .assembly_v3.specifications import scale_capabilities, F40_SPEC
from .assembly_v3.official_guides import GUIDES

VEHICLES = [
    ("ferrari-f40", "Ferrari", "F40", 1990, "sports_car", "V8 双涡轮 · 中置后驱", "楔形车头、NACA 进气口、透明发动机盖、固定尾翼", "76934-1", "/images/ferrari-f40.webp"),
    ("ferrari-enzo", "Ferrari", "Enzo", 2002, "sports_car", "V12 · 中置后驱", "F1 风格车鼻、蝶翼门、分体前灯", None, None),
    ("ferrari-daytona", "Ferrari", "Daytona SP3", 2022, "sports_car", "V12 · 中置后驱", "横向尾部百叶、环绕风挡、弧形翼子板", "42143-1", None),
    ("porsche-911", "Porsche", "911", 1989, "sports_car", "水平对置六缸 · 后置后驱", "圆形灯组、溜背、后置发动机舱", "10295-1", "/images/porsche-911.webp"),
    ("porsche-gt3rs", "Porsche", "911 GT3 RS", 2023, "sports_car", "水平对置六缸 · 后置后驱", "鹅颈尾翼、前翼子板散热口、宽体轮拱", None, None),
    ("mclaren-p1", "McLaren", "P1", 2015, "sports_car", "V8 混合动力 · 中置后驱", "曲面车身、蝶翼门、细长尾灯", "42172-1", "/images/mclaren-p1.webp"),
    ("mclaren-senna", "McLaren", "Senna GTR", 2020, "sports_car", "V8 双涡轮 · 中置后驱", "大尺寸尾翼、分层前部空气动力结构、赛道空气动力套件", "42123-1", None),
    ("lamborghini-countach", "Lamborghini", "Countach", 1988, "sports_car", "V12 · 中置后驱", "低矮楔形轮廓、剪刀门、梯形轮拱", "10337-1", None),
    ("lamborghini-sian", "Lamborghini", "Sián FKP 37", 2020, "sports_car", "V12 混合动力 · 四驱", "Y 形车灯、六边形尾部、剪刀门", "42115-1", None),
    ("bugatti-chiron", "Bugatti", "Chiron", 2018, "sports_car", "W16 四涡轮 · 四驱", "C 形侧线、马蹄形格栅、贯穿尾灯", "42083-1", None),
    ("ford-mustang", "Ford", "Mustang", 1967, "sports_car", "V8 · 前置后驱", "长车头、三段尾灯、侧面折线", "10265-1", None),
    ("chevrolet-camaro", "Chevrolet", "Camaro Z28", 1969, "sports_car", "V8 · 前置后驱", "双圆前灯、宽格栅、肌肉车轮廓", "10304-1", None),
    ("nissan-gtr", "Nissan", "Skyline GT-R R34", 1999, "sports_car", "直列六缸双涡轮 · 四驱", "四圆尾灯、方正座舱、尾翼", None, None),
    ("toyota-supra", "Toyota", "Supra A80", 1994, "sports_car", "直列六缸 · 前置后驱", "圆润车头、弧形尾翼、三组尾灯", None, None),
    ("bmw-m3", "BMW", "M3 E30", 1988, "sedan", "直列四缸 · 前置后驱", "双肾格栅、四圆灯、外扩轮拱", None, None),
    ("mercedes-190e", "Mercedes-Benz", "190E Evolution II", 1990, "sedan", "直列四缸 · 前置后驱", "方形灯组、宽体、标志性高尾翼", None, None),
    ("land-rover-defender", "Land Rover", "Defender 90", 2019, "suv", "前置发动机 · 四驱", "方正车身、外挂备胎、直立风挡", "42110-1", None),
    ("jeep-wrangler", "Jeep", "Wrangler Rubicon", 2021, "suv", "前置发动机 · 四驱", "七孔格栅、外露轮拱、短轴距", "42122-1", None),
    ("ford-raptor", "Ford", "F-150 Raptor", 2021, "pickup", "V6 双涡轮 · 四驱", "宽体货厢、越野轮胎、FORD 格栅", "42126-1", None),
    ("mini-cooper", "MINI", "Cooper", 1967, "hatchback", "直列四缸 · 前置前驱", "圆形前灯、短车身、对比色车顶", "10242-1", None),
    ("vw-golf", "Volkswagen", "Golf GTI Mk1", 1983, "hatchback", "直列四缸 · 前置前驱", "红线格栅、直立尾部、小型两厢车身", None, None),
    ("aston-martin-db5", "Aston Martin", "DB5", 1964, "sports_car", "直列六缸 · 前置后驱", "椭圆格栅、圆灯、流线形车尾", "10262-1", None),
]


def vehicle_catalog() -> list[dict]:
    return [dict(id=id, make=make, model=model, year=year, body_style=body, powertrain=power,
                 visual_targets=targets.split("、"), set_num=set_num, image_url=image or (f"https://cdn.rebrickable.com/media/sets/{set_num}.jpg" if set_num else None),
                 image_kind="official_set_showcase" if image or set_num else "unavailable",
                 specifications=dict(F40_SPEC) if id == "ferrari-f40" else None,
                 scale_capabilities=scale_capabilities(make, model),
                 official_build_references=[dict(set_num=g["set_num"], name=g["name"], instructions_url=g["instructions_url"],
                    product_url=g["product_url"]) for g in GUIDES if g["make"]==make and g["model"]==model],
                 status="experimental", precision_verified=False, recipe_available=id == "ferrari-f40")
            for id, make, model, year, body, power, targets, set_num, image in VEHICLES]
