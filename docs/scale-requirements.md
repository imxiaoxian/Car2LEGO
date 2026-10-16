# 自动尺寸与历史比例兼容

当前桌面流程以外观效果为优先，默认参考约 1:12 的体量与细节级别。
不提供比例选择，也不设固定成品毫米尺寸或百分比尺寸边界。
新任务、照片任务和定制副本统一保存 `scale=null, scale_mode="auto"`。
旧链接中的 `scale` 参数不参与创建；定制副本不继承父任务的比例。

## 当前规划

配置源为 `src/car2lego3d/requirements.py` 的 `automatic_requirements()`，
版本为 `car2lego3d-auto-size-v2`。`size_reference` 记录 `ratio="1:12", binding=false`。
不按尺寸降低细节要求，保留连续模块化车身、
车门与侧窗一体装配、分层灯组、完整座舱以及车头和车尾过渡。
四轮、车门、转向、前后盖及独立悬挂等要求仍须独立验证，声明要求不代表已实现。

车辆参数由模型对话获取，用于外形关系和结构规划；全部保留其估算状态。
实车尺寸除以 12 只产生初始参考体量，然后取邻近的整数 stud 车长和偶数 stud 车宽。
如 F40 初始核心网格为 46×20 studs，实车车长换算参考约 369 mm。
这些是规划估计，不能作为已测得的成品尺寸。零件适配可以调整体量，优先保留外观和完整细节。
规划中的换算分母用于将实车外形映射到网格，不作为交付尺寸约束。

当前配方仍只支持 23–32 studs 的核心车长及 8/10/12 studs 核心宽度。
自动规划不再把约 1:12 的模型压回这一容量范围。
大型风挡、轮组和底盘需要相应配方，不允许拉伸标准零件来填满空间。
若初始体量尚无对应配方，保存规划和缺失原因并在生图、重建前停止。
目前 F40 等常规车型的约 1:12 配方仍未实现，不能宣称默认流程已生成这种体量的 Studio 文件。

## 尺寸和质量报告

前端只展示从导出模型原生几何测得的实际尺寸，不显示比例偏差。
尺寸检查记录为 `measured` 或 `unverified`，不再因超出某个比例容差而失败。
碰撞、连接、机构运动、外观、导出回读、Studio 和实物检查继续独立记录。
自动尺寸不会将这些项目改为通过，也不会自动设置 `delivery_accepted=true`。

`00-requirements/requirements.json` 保存规划快照，
`03-lego/requirements.json` 和 `requirements-report.json` 保存本次使用的要求和检查结果。
自动模式中的物理尺寸条目为参考资料，不按固定比例打合格标签。
实际尺寸必须绑定相同装配哈希的原生几何检查结果。

## 命令

有车型规格时，不提供尺寸参数即为自动模式；配方不支持时输出规划后停止：

```powershell
.venv/Scripts/python.exe -m car2lego3d run `
  --views runs/image/views.json --vehicle-specs path/to/spec.json `
  --output runs/my-car --strategy car
```

也可显式设置 `--scale-mode auto`，但不能同时传入 `--scale`、
`--length-studs` 或 `--width-studs`。

CLI 中显式的 `--scale`、`--scale-mode exact` 和自定义网格接口仅保留给历史实验复现。
`requirements` 命令仍可导出历史四档策略，不代表当前桌面流程提供比例选择。
历史任务保持原产物和记录；取消比例不回写旧模型、不替旧模型补验收结论。
