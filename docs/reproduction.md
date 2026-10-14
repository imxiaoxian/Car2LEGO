# 实际复现记录

日期：2026-10-14。所有下列图片、网格、模型和 JSON 均由本机运行生成，不是替代模型或论文演示结果。

## 环境与版本

- Windows 11（系统版本 10.0.26200）、16GB 内存。
- NVIDIA GeForce RTX 4060 Laptop GPU，8,188 MiB 显存；驱动 560.76。
- Python 3.11.5；PyTorch 2.5.1+cu124；torchvision 0.20.1+cu124。
- TripoSR 源码：`107cefdc244c39106fa830359024f6a2f1c78871`。
- TripoSR 权重：`5b521936b01fbe1890f6f9baed0254ab6351c04a`。
- SD-Turbo 权重：`b261bac6fd2cf515557d5d0707481eafa0485ec2`。
- DINO 配置、其余依赖见 `models.lock.json`、`requirements.lock.txt` 与产物 JSON。

## 汽车完整流程

```powershell
.venv/Scripts/python.exe -m car2lego3d run `
  --prompt "a red Ferrari F40 sports car, realistic proportions, black tires, transparent windows" `
  --seed 42 --resolution 128 --length-studs 32 `
  --output runs/f40-release --device cuda:0
```

最终完整命令退出码为 0，`pipeline.json` 为 `completed`；带缓存模型权重的整条命令记录耗时 **54.277 秒**。
阶段计时与整条命令不同：整条命令还包含各独立进程的解释器启动、模块导入与退出等开销。
这是单机样例实测，不是严格多次平均性能基准。

| 阶段 | 最终样例记录 |
| --- | --- |
| SD-Turbo | 512×512，4 步，种子 42；8.763 秒；PyTorch 分配显存峰值 3,096.28 MiB |
| TripoSR | 去背景，float32 CUDA 推理，128 marching-cubes 分辨率，4,096 查询分块；19.729 秒；显存峰值 1,866.54 MiB |
| 网格 | 9,548 顶点、19,088 三角面，`watertight=true`，2 个网格组件 |
| 乐高转换 | 32×18 studs、25 板层；8,345 个占用体素；2,683 个真实板件编号；4.317 秒 |
| 占用检查 | 0 重叠、0 遗漏、0 多余体素 |
| Stud 连接 | 6 个组件，大小为 2,666 / 6 / 6 / 3 / 1 / 1；149 个非地面板件没有下层直接支撑 |
| 外部零件库 | 全部 2,683 个零件识别成功，缺失零件 0，未知颜色 0 |
| 真实零件渲染 | Blender 4.5.14 + ldraw-mcp；45° / 135°，每视图 640px，24 samples；已查看渲染结果 |

显存峰值指 PyTorch 分配内存，不包含桌面程序、CUDA 驱动及其他进程。
第一次生图阶段包含模型下载，耗时 341.478 秒；不能当作推理性能。最终记录使用缓存权重。

![SD-Turbo 生成图片](../examples/f40/01-image/reference.png)

![TripoSR 重建](../examples/f40/03-lego/mesh-preview.png)

![标准板件真实 LDraw 渲染](../examples/f40/03-lego/native-ldraw.png)

图片提示词没有完全约束背景，去背景后汽车边缘仍需要检查。单图重建可以辨认汽车形状，但纹理中的高光、阴影和背面推断降低了颜色与车型细节的准确性。网格中的轮胎被转换为板件雕塑，没有实际可转车轮。

## 单色对照

对同一份 `mesh.glb`，强制 `--color 4`：

```powershell
.venv/Scripts/python.exe -m car2lego3d lego `
  --mesh examples/f40/02-mesh/mesh.glb --color 4 --length-studs 32 `
  --output runs/f40-uniform-control
```

实测 813 个板件、1 个 stud 组件、61 个非地面板件没有下层直接支撑；转换计时 2.154 秒。
这说明当前颜色硬分区影响了板件合并和连接，但一次对照不能证明整体方法更优。
统一红色会丢失玻璃、车轮等信息，不作为默认质量修复。

## 上游样例复现

```powershell
.venv/Scripts/python.exe -m car2lego3d reconstruct `
  --image external/TripoSR/examples/chair.png --resolution 64 `
  --device cpu --output runs/upstream-chair
```

成功退出，19.252 秒，2,407 顶点 / 4,814 面，封闭网格。
该样例验证 CPU 路径与 Windows 网格适配可以运行；低分辨率结果不代表上游完整质量。

## 代码和产物验证

- 本机 10 项测试通过：非等距网格比例、对角长轴对齐、逐体素颜色覆盖、stud 连接、重叠报告、LDraw 旋转和层高、marching-cubes 轴约定、透明预处理、原模型导入、彩色 GLB 到完整导出。
- `scripts/verify_examples.py` 校验 13 个记录中的文件 SHA256，以及 LDraw / BOM / 装配 JSON 的数量一致性。
- 使用真实 LDraw 渲染发现并修正了长方形板件的轴映射：长轴在 LDraw X 方向；当前零件表与本机标准 `.dat` 文件的外框尺寸一致。
- GitHub Actions 配置 CPU 几何与导出测试。它不运行生图或神经网络重建；不以 CI 通过声称模型质量。

## 当前结论

**生图 → 真实开源图片重建 → 乐高板件模型的技术流程已跑通。**
当前彩色样例仍有断连、下层支撑、颜色噪声及细节损失问题，不能标记为可搭建成品。
`buildability=unverified`、`studio_verified=false`、`physical_verified=false` 保留在所有报告中。
没有进行 Studio GUI 碰撞审查、实物搭建、承重、机构或严格车型相似度评测。

下一阶段应先解决网格部件分割与颜色去光照，再联合优化板件覆盖和跨层连接，最后引入真实轮组、底盘和曲面零件。
