# LEGO 外部项目调研与 Car2LEGO 接入边界

调研日期：2026-10-14

本文把用户指定的六个开源项目放在 `assembly_v3` 的实际流程中比较。结论只依据项目仓库、README、许可证文件和当前工作区已经完成的工具验证；第三方项目的演示结果不等于 F40 的 Studio、实物或外观验收。

## 结论摘要

| 项目 | 适合承担的工作 | 不应承担的工作 | 许可证/接入建议 |
| --- | --- | --- | --- |
| [BrickGPT](https://github.com/AvaLovelace1/BrickGPT) | 基础积木候选、碰撞拒绝、重生成策略、LDraw 初稿 | 精细车身曲面、Technic 转向、车门和悬挂闭环 | 代码主体 MIT；作为研究参考或隔离候选生成器，不直接替换 `assembly_v3` |
| [legolization](https://github.com/hbmartin/legolization) | 连接图、悬空件、承重路径、RBE 稳定性、局部修复、步骤审查 | 车辆曲面拟合、真实铰链运动、独立悬挂动力学 | GPL-3.0-or-later；以外部 CLI/子进程和结果文件接入，避免 GPL 代码进入核心服务 |
| [ldraw-mcp](https://github.com/musharna/ldraw-mcp) | 使用真实 LDraw 几何做多视图渲染、颜色/零件查询、视觉回归 | 连接求解、碰撞证明、机构规划 | MIT；可作为独立渲染 worker，读取同一份 MPD |
| [LTRON](https://github.com/aaronwalsman/ltron) | LDraw 场景表示、连接动作、Break-and-Make 数据和研究环境 | 当前生产生成器、Windows 无头渲染、车辆工程验收 | v1.0.0 源码 MIT；资产各有许可证；仅抽取表示和数据集思路 |
| [LPub3D](https://github.com/trevorsandy/lpub3d) | 从已有 MPD/步骤生成 PDF、图片、HTML 和 BOM | 自动设计模型、修复非法连接 | GPLv3；通过外部命令行导出，交付物保留来源和版本 |
| [LeoCAD](https://github.com/leozide/leocad) | 参考交互式编辑、LDraw 文件/步骤处理和人工复核 | 自动车辆复刻、连接求解、机构设计 | `docs/COPYING.txt` 为 GPLv2；不作为后端依赖，作为人工复核工具 |

优先级为：`ldraw-mcp` 视觉回归 → `legolization` 独立装配审查 → LPub3D 说明书导出 → BrickGPT 候选策略实验。LTRON 和 LeoCAD 保持资料参考，等连接数据契约稳定后再考虑局部借鉴。

## 逐项调研

### 1. BrickGPT

仓库定位是从文本生成物理稳定、可搭建的基础积木结构。README 记录了 Llama-3.2-1B-Instruct 微调、候选放置、碰撞拒绝和多轮重生成，并输出 `output.txt`、`output.ldr` 与渲染图；没有 Gurobi 时稳定性会退化为较弱的连接性方法。mesh-to-brick 也是体素/积木转换，不是车辆 CAD 求解器。

对本项目的价值：

1. 将候选零件加入场景时，可借鉴“尝试 → 碰撞拒绝 → 回滚 → 重生成”的策略。
2. 可在 `assembly_v3` 的基础模块内做小规模基线，比较候选数量、碰撞率、重生成次数和最终连通率。
3. 可将其 LDraw 初稿作为外部候选输入，但必须经过本项目的连接、碰撞、尺寸和机构检查。

边界：BrickGPT 输出的是基础积木结构，不能把论文或 README 的稳定性结果解释为 F40 车门、转向或悬挂已经可动。其模型、数据集和大部分代码为 MIT，ImportLDraw、FlashTex 等子模块遵循各自许可证；生产环境不应复制其权重或子模块而不保留许可证。

### 2. legolization

README 给出的主流程是 `voxelize → hollow → place bricks → stability → repair → export`，稳定性采用 Rigid-Block-Equilibrium 线性规划，并要求模型形成一个 stud-connected 组件且没有悬空件。0.6.0 的 skill 套件包含 `analyze-lego-assembly`、`repair-lego-assembly`、`publish-lego-instructions`、`inspect-instructions`、`render-ldraw` 和 `eval-corpus` 等。

对本项目的价值：

- 输入导出的 `.ldr/.mpd`，把断连组件、悬空件、承重路径和插入风险作为独立诊断结果。
- 在局部修复阶段比较候选方案，并保留原文件和被拒候选，不覆盖 `assembly_v3` 场景。
- 在步骤导出前做顺序、插入压力和 booklet readiness 检查。

边界：体素化会损失车身曲面；RBE 是数字假设，不是悬挂回弹、铰链摩擦、卡扣寿命或实物承重的证据。项目 GPL-3.0-or-later，并继承 `pyldraw3` 的许可证。因此建议使用固定版本的外部进程：输入只读 MPD，输出 JSON/HTML/诊断 MPD，核心服务不导入其 Python 模块。

当前工作区已经用隔离环境运行过 0.6.0 诊断；它识别了 F40 1:24 的零件，但返回 `DISCONNECTED / unbuildable`。该结果用于定位问题，不覆盖本项目质量门禁。

### 3. ldraw-mcp

这是 Blender + ImportLDraw 的真实零件渲染 MCP。README 的工具包括 `render_ldraw_file`、`render_ldraw_text`、`check_renderer`，并支持颜色、零件查询和多角度图。它的目标是暴露几何代理渲染隐藏的错误，例如错误旋转、悬空、沉入车窗、透明件和轮胎问题；相机仰角固定，属于一致性检查而非任意摄影机求解器。

推荐接法：

```text
assembly_v3 scene -> MPD/临时 LDR -> ldraw-mcp worker -> PNG + manifest -> visual regression
```

`manifest` 至少保存输入文件哈希、零件库版本、Blender/ImportLDraw 版本、视角、分辨率和缺失零件列表。前端 Three.js 和该 worker 都读取同一份场景导出，不能各自生成一套几何。

当前工作区已经完成 stdio、颜色/铰链查询、三个样板 BOM、透明零件和 F40 双视图验证；F40 渲染仍能看到盒状车身和简化轮拱，所以“能渲染”没有被标成“外观通过”。项目 MIT，可直接以独立 worker 使用。

### 4. LTRON

LTRON v1.0.0 是 ECCV 2022 对应的交互式装配研究环境，基于 LDraw、OMR 和 LDCad 数据，包含场景、连接表示、Break-and-Make 任务和 Gym 环境。README 明确说明 `master` 分支不稳定，并依赖非公开代码；渲染组件主要面向 Ubuntu、OpenGL 4.6 和 splendor-render。

可借鉴：

- 用连接类型、连接位置和装配动作表示训练数据。
- 将“拆开/重新连接”作为未来机构和局部修复的动作语义。
- 研究从完整场景到逐步装配轨迹的状态转换。

不建议当前安装到生产后端。v1.0.0 源码是 MIT，但 LDraw、OMR、LDCad 和渲染资产有独立许可证；Windows 机器上的渲染依赖也不满足当前生产假设。

### 5. LPub3D

LPub3D 是 LDraw 说明书编辑器，适合在 MPD、子模型和步骤已经正确的前提下生成真实 PDF、PNG/JPEG、HTML steps、BOM 等。源码 README 标明 GPLv3，并支持控制台/命令行处理；当前已确认的参数包括：

```text
--process-file
--process-export
--export-option pdf/png/jpeg/bmp/stl/3ds/pov/csv/htmlsteps/obj
--export-directory
--output-file
--preferred-renderer
--range
--no-console-redirect
```

建议在 `assembly_v3` 中增加 `lpub3d_export` 外部 worker：先导出带 `0 STEP` 和子模型的 MPD，再运行 LPub3D，最后回读 PDF/HTML 的页数、步骤数、BOM 和输入哈希。LPub3D 不能修复断连或自动设计车门；当前工作区尚未完成 LPub3D 二进制的无头冒烟测试，不能宣称导出链已通过。

### 6. LeoCAD

LeoCAD 是跨平台 C++ LDraw CAD 编辑器，源码中有模型、文件和 instruction 模块，适合人工查看零件变换、步骤和文件处理。`docs/COPYING.txt` 是 GNU GPL v2；仓库没有可直接当作后端 API 的稳定 CLI 合约。

它适合：

- 作为人工复核工具打开 MPD/LDR，检查子模型、步骤和变换。
- 参考交互编辑器中的选择、移动、旋转和步骤组织。
- 为未来人工修复界面提供交互设计参考。

它不适合：

- 替代 `scene.py` 的连接求解和 OR-Tools 规划。
- 在服务端以 GPL 组件嵌入自动生成链。
- 证明转向、车门或悬挂在全行程无干涉。

## 统一适配契约

所有外部工具都围绕版本化的 `assembly_v3` 导出，不直接读写数据库。每次调用保存：

```json
{
  "schema": "assembly_v3.external_check.v1",
  "scene_hash": "sha256:...",
  "input": "model.mpd",
  "tool": {"name": "ldraw-mcp", "version": "0.3.1"},
  "parts_library": "Studio 2.0/ldraw",
  "status": "pass|fail|indeterminate",
  "artifacts": [],
  "limitations": []
}
```

适配层必须遵守以下规则：

- 外部工具的 `pass` 只能更新对应辅助检查，不能改写 `precision_verified`。
- `indeterminate`、未知零件、缺失碰撞数据和未识别连接都不能算通过。
- 修复工具只产生 sibling bundle；候选必须回到 `scene.py`、连接检查、碰撞检查和 Studio 回读。
- 渲染、BOM、步骤和前端几何必须由同一个 `scene_hash` 派生。
- GPL 工具使用子进程和文件边界，记录版本、许可证和命令行，不复制 GPL 源码进核心包。

## 已接入与当前边界

`assembly_v3` 导出 MPD 后会运行可配置的外部检查：

- `ldraw-mcp` 在独立 Python/Blender 环境中生成六方位真实 LDraw 渲染，并为发动机、座舱、座椅、车门、前盖、后盖和细节模块生成局部视图；座椅视图从座舱中的座椅及安装件特征单独提取。其独立 BOM 与场景中的零件号、颜色、数量逐项比对，同时记录零件库缺项。
- `legolization` 通过独立进程和模型范围内的 UTF-8 零件库运行只读连接/稳定性分析，结果与诊断文件保存在该设计目录下。它不自动修复或覆盖场景。
- `ASSEMBLY_EXTERNAL_CHECKS_ENABLED=false` 可关闭检查；工具路径可通过 `ASSEMBLY_LDRAW_MCP_PYTHON`、`ASSEMBLY_LDRAW_MCP_COMMAND`、`ASSEMBLY_LDRAW_MCP_BLENDER`、`ASSEMBLY_LEGOLIZATION_PYTHON` 覆盖。缺少运行时、超时和不完整零件库均如实报告。
- LPub3D 尚未在当前机器完成无头实测，因此未替换已有真实步骤 PDF。BrickGPT、LTRON、LeoCAD 继续作为隔离实验/设计参考，不进入车辆自动生成主链。

任何外部工具失败只记录在 `quality_report.json.external_checks` 和 `external/` 工件，不中断已有草稿导出，也不覆盖 `precision_verified`、Studio 或实物状态。

## 推荐落地顺序

1. **视觉回归**：把现有 `ldraw-mcp` worker 固化为每个比例的六视图 + 发动机、座舱、座椅、车门、前后盖和底盘细节图，并保存 manifest。
2. **连接与稳定性审查**：把 legolization 的分析结果转成辅助质量报告，先定位断连和悬空模块，再由 `assembly_v3` 重新规划。
3. **说明书链**：完成 LPub3D 无头导出与 MPD 回读；在 PDF 失败时保留当前真实步骤 PDF，不生成空占位文件。
4. **候选策略实验**：在隔离任务中比较 BrickGPT 的候选拒绝/重生成与现有 OR-Tools 选择器，记录相同输入下的连接率、碰撞率、零件数和调用次数。
5. **研究资料**：将 LTRON 的连接动作和 LeoCAD 的人工编辑交互转成设计文档，不把不稳定依赖纳入生产镜像。

## 验收边界

| 检查 | 可由外部项目辅助 | 仍必须由本项目或人工完成 |
| --- | --- | --- |
| 几何外观 | ldraw-mcp 渲染、多视图对比 | 目标图对照、透明件/颜色审查、人工外观验收 |
| 连接/稳定 | legolization、BrickGPT 候选拒绝 | Studio Connectivity、合法连接定义、实物承重 |
| 机构 | LTRON 动作表示可参考 | SciPy/约束扫掠、全行程无干涉、实物开合/转向/悬挂 |
| 步骤/清单 | LPub3D、legolization、LeoCAD | MPD 回读、插入路径、真实 Studio 打开检查 |
| 生成设计 | BrickGPT 基础候选、legolization 体素基线 | F40 分模块配方、比例规划、真实零件和购买性 |

因此，当前 F40 的状态仍以 [assembly_v3-status.md](assembly_v3-status.md) 为准：工具接入和数字草稿不能把未完成的机构、Studio 或实物检查升级成精细复刻标签。
