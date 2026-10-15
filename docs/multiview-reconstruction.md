# GPT 多视图与 Hunyuan3D-2mv

## 选择依据

| 项目 | 已核对的接口与取舍 |
| --- | --- |
| [Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) | 官方 `examples/shape_gen_multiview.py` 直接传入视角字典；`MVImageProcessorV2` 支持 front/left/back/right；直接导出 trimesh。采用 2mv 权重。 |
| [InstantMesh](https://github.com/TencentARC/InstantMesh) | 官方流程先从单图通过 Zero123++ 生成多视图，再做 sparse-view reconstruction；要复用外部 GPT 视角需匹配其相机约定。当前没有实跑。 |
| [LGM](https://github.com/3DTopia/LGM) | 多视图高斯表示，官方 README 说明完整推理约 10 GB 显存，另需 mesh conversion 和 CUDA 组件。当前没有实跑。 |

以上仓库 README 和 Hunyuan3D 的模型代码已通过 GitHub API 实际读取。
Hunyuan3D 是公开代码/权重，采用带地域和其他条件的 Tencent Hunyuan Community License，并非 MIT/Apache。
使用时保留下载的 LICENSE 和 NOTICE；本仓库不重新分发模型权重。

## 固定版本与安装

代码和权重 revision、权重 SHA256 在 `models.lock.json`。源码通过 GitHub Git tree/blob 获取，逐文件验证 Git SHA1；
权重为 `tencent/Hunyuan3D-2mv/hunyuan3d-dit-v2-mv/model.fp16.safetensors`，约 4.93 GB，完成后验证 LFS SHA256。
下载支持分段续传。原始代码写入 `external/Hunyuan3D-2`，权重写入 `models/Hunyuan3D-2mv`，均不提交 Git。

```powershell
uv pip install --python .venv/Scripts/python.exe -e ".[multiview]"
.venv/Scripts/python.exe -m car2lego3d setup --backend hunyuan-mv
# 网络需要时，可为此进程设置 HF_ENDPOINT=https://hf-mirror.com
.venv/Scripts/python.exe -c "from car2lego3d.multiview import download_weights; print(download_weights())"
```

8 GB GPU 使用 fp16、按组件 CPU 卸载。适配层为上游补充缺失的 components 和执行设备字段，原始源码保持哈希不变。
几何阶段不启用纹理生成器，不需要纹理栅格化扩展；输出是无纹理网格。车身颜色在 LEGO 阶段显式选择。

## 生图契约

直接调用 `D:/lego/backend/app/services/reference_images.py` 的 `ReferenceImageService.generate()`，
复用 GPT 型号、high 质量、尺寸、车型描述、参考图 edit、缓存和失败处理。桥接脚本仅在独立进程内修改镜头要求。

overview 是同车外观锚点，后续 front/body/rear/wheels 复用它和实车源图，分别保存为 front/left/back/right。
每张图只包含一个完整正交视图；模型联合消费四张图，不使用 overview 做单图重建。
年份未提供时保持 null。记录模型名称和文件哈希；失败直接报告，不回退到 SD。

`views.json` 检查四个标签、不同图像及哈希。前景去背景后检查边界、与物理资料的宽高比及前后/左右的轮廓一致性。
这些检查可以阻止明显错误，但不能证明相机角度、品牌细节和遮挡区域真实一致；合成视图仍需人工外观检查。

```powershell
.venv/Scripts/python.exe -m car2lego3d image --prompt "Orange Lotus For Me SUV, black roof" `
  --reference-image path/to/official-side.png --vehicle-specs path/to/spec.json --output runs/for-me-image
.venv/Scripts/python.exe -m car2lego3d run --views runs/for-me-image/views.json `
  --vehicle-specs path/to/spec.json --scale 1:24 --color 25 --resolution 256 --output runs/for-me
```

物理校准仅对输出网格施加已知外包络约束，不代表恢复了真实 CAD。多视图重建、LEGO 外观、Studio GUI、实体拼装分别验收。

## 本机实跑记录

2026-10-15，Lotus For Me，原厂侧视图作为外观锚点，复用原项目配置的 `gpt-image-2.5-sunburst`。
四张独立视图的生成记录位于 `runs/lotus-for-me-gpt-20261015/01-image`。
Hunyuan3D-2mv 使用 50 步、256 网格分辨率、4096 查询分块，RTX 4060 Laptop 8 GB，CPU 卸载。
成功运行位于 `runs/lotus-for-me-mv-20261015/02-mesh-v2`，耗时 348.425 秒，
PyTorch 峰值已分配显存 3021.13 MB；这不是驱动报告的总显存。输出为无纹理网格。
前一次失败记录保留在 `02-mesh`，原因为上游 offload 方法缺少 components 属性；适配层已修复。

同一组视图、规格、模型和推理设置可以通过 `run --reconstruction-cache` 复用已完成网格，
复用前核对输入、版本和每个输出哈希。这样可以修改积木配方后重跑后半段，无须再次生图或重建。

后续完整导出位于 `runs/lotus-for-me-mv-20261015/artifacts-v2`：1:24、27×10 格，394 件原生零件。
从网格测得上车身宽度比例约 0.626，选择六格原生风挡和连续透明侧窗；保留四门与轮组。
生成了真实 LDraw 零件渲染及通过归档回读的 `.io`。前一版八格座舱结果保留在 `artifacts`。
目视检查发现车头、车肩和车顶仍过于方正，品牌特征不足，外观验收保持 false。
未完成 Studio GUI、碰撞、连接和实体拼装验收；本次结果是可复查草稿，不是已验收成品。
