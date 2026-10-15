# 车辆物理参数与生成约束

网页的物理先验由用户输入车型后直接通过配置的大模型对话获取。
每项数值标注为模型估算，并附依据和置信度；年款选填，缺省时记录代表版本假设，未知项保留为空。
运行方式、数据边界和实测记录见 [车辆参数获取](vehicle-spec-search.md)。

以下 F40 宣传册数据仅是此前 CLI 的历史复现实例。网页不会读取该静态文件或将其作为检索失败回退。
原始数据和推导数据分开；不同市场/版本的资料不能无说明混用。

## 历史静态样例数据

来源：[Ferrari 原厂宣传册存档](https://www.auto-brochures.com/makes/Ferrari/Ferrari_int%20F40_1987.pdf)，
PDF 第 5 页；2026-10-14 逐项查看。PDF SHA256 记录在规格 JSON，仓库不转存宣传册。

| 参数 | 原厂规格 |
| --- | --- |
| 长 / 宽 / 高 | 4430 / 1980 / 1130 mm |
| 轴距 | 2450 mm |
| 前 / 后轮距 | 1594 / 1610 mm |
| 前轮胎 | 245/40 R17 |
| 后轮胎 | 335/35 R17 |

轮胎规格另经 [Pirelli 官方资料](https://www.pirelli.com/tires/en-us/car/press-releases/ferrari-supercars) 核对。
名义轮胎外径按 `轮圈英寸 × 25.4 + 2 × 胎宽mm × 扁平比 / 100` 推导：前 627.8 mm、后 666.3 mm。
这是规格推导，不是受载滚动外径或实测值。

门长、门板高度、前风挡上/下宽、斜面高度、相对地面的倾角、前后悬目前均为 `null / unknown`。
宣传照片的透视不能直接作为精确几何测量；这些数据需要工程图、合法 CAD 或实车测量补充。

## 如何作用于流程

1. 生图：把长宽和高长比例加入提示词，保存完整规格与提示词。SD-Turbo 仅接受有限文本长度，
   会在模型加载后检查 token 数量。比例文字是软条件，不保证像素尺寸。
2. 3D：保留 TripoSR 原始 `mesh.glb / mesh.obj`，沿主轴校准包围盒得到指定长宽高。
   `calibrated.glb` 使用米，`calibrated-mm.obj` 使用毫米。独立 XYZ 缩放改变几何比例，不能证明恢复了真实 CAD。
3. 乐高：精确 `--scale 1:N` 使用 `s = 1/N`；自定义长度使用 `s = length_studs × 8 / 真实车长mm`。
   所有真实长度乘同一个 `s`；不能分别给轮胎、车门采用不同缩尺，角度保持不变。
   核心宽度先规划到最近偶数 stud，当前配方仅能实现 8 / 10 / 12；超出范围明确阻止生成。
   轴距用真实值约束，再量化到原生安装网格。
   前后悬未知时，前后轴的整体位置仍由网格证据确定；仅有轴距不能确定前后悬。
4. 评估：`dimensions.json` 输出目标与当前家族的差值、百分比，以及未执行的约束。
   轮胎、玻璃、车门仍是固定标准零件；现在没有根据未知或新测量值自动重建自由形状车门和玻璃。

以 24 studs 为例，统一缩尺约为 `1:23.073`，目标宽约 85.815 mm、轴距约 106.185 mm。
10-stud 核心宽 80 mm，误差约 -6.776%；13-stud 轴距 104 mm，误差约 -2.058%。
原 8-stud 核心宽 64 mm 对应误差约 -25.421%。核心宽度不包含轮拱、侧贴门板和后视镜。
当前轮胎外径 24 mm、宽度 11.2 mm；后胎宽度相对目标约 -22.861%，明确保留为未满足项。
前窗零件 65633 的中心表面角度从本机原生几何计算约 21.45°，这是零件角度，不是 F40 实车角度。

上述 24 studs 样例是自定义长度，不是精确 1:24。精确 1:24 的目标车长为 184.583 mm，
名义核心取 23 studs，即 184 mm，误差约 -0.316%。各档要求和容差见 [分比例说明](scale-requirements.md)。

## 正交侧视图标注

`measure` 命令接受原始图片和人工标注 JSON，不自动识别特征点。图中车头到车尾的轴向
由参考段确定，支持轻微图片整体旋转。参考段必须是轮心到轮心（`wheelbase`）或车头到车尾（`length`）。
任意透视图、渲染相机视图和拼图都不适合作为这个工具的正交输入。

下面只演示格式，坐标是构造示例，不是 F40 测量结果；需要在实际正交图上标点：

```json
{
  "title": "Source drawing title and edition",
  "view": "orthographic_side",
  "reference_measurement": "wheelbase",
  "reference_points": [[100, 400], [600, 400]],
  "endpoint_uncertainty_px": 2,
  "segments": {
    "door_length": [[300, 350], [500, 350]],
    "windscreen_angle_to_horizontal": [[300, 250], [400, 175]]
  }
}
```

```powershell
.venv/Scripts/python.exe -m car2lego3d measure `
  --vehicle-specs data/vehicles/ferrari_f40_1987.json `
  --reference-image path/to/orthographic-side.png --annotations path/to/points.json `
  --output runs/measured-f40
```

输出 `spec.json` 可作为下一次 `run --vehicle-specs` 输入。
支持水平投影：`door_length / door_front_x / windscreen_bottom_x / front_overhang / rear_overhang`；
竖直投影：`door_panel_height`；欧氏长度：`windscreen_slant_height`；倾角：`windscreen_angle_to_horizontal`。
坐标型字段的段落必须从车头起点量到目标点，车门高度不包含侧窗。
窗口斜面高度和倾角只是中心剖面线近似，不能表示完整曲面玻璃。

所有图纸标注结果标为 `estimated`，记录原始图片哈希、标注点、参考尺寸和端点误差。
误差估计不包括图纸本身误差、透视误差和参考尺寸不确定性。
正交声明来自标注者，程序不宣称自动验证了相机投影。
前视图的玻璃宽度或其他实测数据可以直接填入规格 JSON，并提供来源、单位和测量方法。

## 验收边界

`manufacturer` 表示来源是厂家发布的数据，不能替代对特定实车的测量。
`physical_measurement_verified=false`、`dimensions_verified=false`、`appearance_accepted=false`
保持独立于运行成功和归档回读。最终外框、碰撞、连接、外观和实物搭建还需要分别验证。
