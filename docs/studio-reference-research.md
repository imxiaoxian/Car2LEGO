# 官方车辆参考与 Studio 工具核查

核查日期：2026-10-13。当前 F40 仍是实验草稿；资料、渲染工具和文件编辑工具都不能代替装配验收。

六个外部项目的统一能力矩阵、许可证边界和接入顺序见 [external-project-research.md](external-project-research.md)。本文件保留官方车辆资料、PartDesigner、LDraw MCP 和当前机器上的实际安装/验证记录。

## 已取得的官方参考

| 参考 | 用途 | 当前核查程度 |
| --- | --- | --- |
| [Ferrari F40 10248](https://www.lego.com/en-us/product/ferrari-f40-10248) | 同车型的车门、座椅、V8 发动机、后盖、车身拼接 | 已下载官方 140 页说明书，检查模块页面 |
| [Porsche 911 10295](https://www.lego.com/en-us/product/porsche-911-10295) | System 车身中的转向、座椅及发动机空间布置 | 已下载 268 页 PDF，初看底盘与后置发动机页面；完整模块尚未重建 |
| [Ferrari Daytona SP3 42143](https://www.lego.com/en-us/product/ferrari-daytona-sp3-42143) | Technic 承重骨架、前轮转向、避震器与悬挂布置 | 已下载第一本 404 页 PDF，初看承重框架页面；不把蝶翼门移植为 F40 车门 |

F40 官方 PDF：[6205518.pdf](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6205518.pdf)，本地 `backend/storage/official_references/10248-6205518.pdf`。文件 21,768,444 字节，共 140 页；SHA256 为 `0f89d8a703749448da79510800cf8a61e2f271889f25d0b5e21a4e8e37496b9a`。

按 PDF 页码（从 1 开始）整理：

- 座椅：47–50 页；48 页可见 Technic 座椅框架与销连接，50 页可见整车安装。
- 车门：55–58、61–64 页；55 页可见竖直铰接件与门板层次，58/64 页可见两侧车门安装。
- 发动机：66–75 页；72 页可见 V8 外观、进气与周边细节，75 页可见发动机安装位置。
- 后盖：80–96、101 页；95 页可见轴及安装耳，96/101 页显示后部模块装配。

代表页面已另存为图片并登记 SHA256。`official_guides.py` 将这些真实搭建页面传给视觉规划，标明官方来源、页码、模块与未完成目标比例验收。其余车型只能作为机构技术参考。图片不能直接提供无误的三维坐标；下一步仍需逐件重建、合法连接求解和机构扫掠。

官方网页在本机浏览器和普通 HTTP 请求中返回 Cloudflare 拦截；官方 CDN 的三个 PDF 下载成功。Daytona 第一本为 [6590123.pdf](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6590123.pdf)，164,501,642 字节；Porsche 为 [6590143.pdf](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6590143.pdf)，90,595,170 字节。两者已打开并检查初期搭建页面，转向/悬挂全部步骤尚未逐页审查；未把未审查的页面注册为已验证模块。

## Studio、MCP 与 skill

| 工具 | 有用能力 | 已核实的限制 | 本项目适用位置 |
| --- | --- | --- | --- |
| [官方 PartDesigner](https://studiohelp.bricklink.com/hc/en-us/articles/5872512112663-What-is-PartDesigner) | 编辑零件形状、连接数据并供 Studio 使用 | 自定义零件不等于实际可购买的乐高零件；没有发现官方 Studio MCP | 已安装 2.26.3_1，供核查缺失的连接数据，不能借自制零件通过真实零件验收 |
| [datakurre/brick-mcp](https://github.com/datakurre/brick-mcp) | 读写 `.io/.ldr/.mpd`、移动/旋转/改色、零件与步骤查询 | 文档要求 Python ≥3.14；本项目解释器为 3.11；工具列表未提供完整连接与机构验收 | 文件编辑与人工修复接口，适合独立环境试验 |
| [musharna/ldraw-mcp](https://github.com/musharna/ldraw-mcp) | Blender + ImportLDraw 渲染真实几何、清单、颜色、零件查询 | 已配置 Blender 4.5.14 与 ImportLDraw 1.3.0；不是机构求解器；MCP 相机仰角固定 22° | 已安装并通过 stdio 实测；提升真实渲染与独立清单检查，读取同一份装配数据 |
| [jonx/BrickBuilderMCP](https://github.com/jonx/BrickBuilderMCP) | 合法放置候选、连接查询、碰撞及问题渲染、子模型 | 作者明确当前连接模型仅凸点/接收孔，销、夹杆、支架及复杂曲面尚未覆盖 | 借鉴候选令牌和诊断方式，不能替代本项目 Technic 检查 |
| [hbmartin/pyldraw3 的 lego-model-builder skill](https://skills.sh/hbmartin/pyldraw3/lego-model-builder) | 参数化 LDraw 代码与渲染迭代流程 | 搜索时 2 次安装、仓库 2 stars；说明面向 Linux/macOS、Python ≥3.12 | 流程参考，尚未验证 Windows 环境适配 |
| [hbmartin/legolization 的 render-ldraw skill](https://skills.sh/hbmartin/legolization/render-ldraw) | 多角度渲染与视觉复核 | 搜索时 3 次安装、仓库 9 stars；渲染依赖需要另行确认 | 小样本评估候选，不能仅因存在 skill 就视为可靠 |

GitHub 星数与安装量为核查时的快照。当前插件目录搜索没有得到相关 Studio/LEGO 插件；目录搜索并不保证覆盖所有插件。用户随后明确授权按需安装，下列工具已经安装，其余候选保持研究状态。

## 安装与实际验证（2026-10-13）

### 官方 PartDesigner

官方下载页：[PartDesigner](https://www.bricklink.com/v3/studio/partdesigner.page)。从页面的官方前端下载链接取得 [Windows 安装包](https://studio.download.bricklink.info/PartDesigner/PartDesigner.exe)。

- 安装包：`D:/lego/backend/storage/tool_research/PartDesigner.exe`，48,013,256 字节。
- SHA256：`91e55fd4a86ca074157acc8d77a2554bf6ff175a73cb18275dbb10f0fa511df6`。
- Authenticode：`Valid`，发布者 `LEGO Juris A/S`。
- 已安装：`D:/lego/backend/storage/tool_research/PartDesignerApp/PartDesigner.exe`，版本 `2.26.3_1`。
- 安装器退出 0，安装日志确认成功、无需重启。尚未用 GUI 创建、导出并在 Studio 验证自定义零件。
- `installation-manifest.json` 保存来源、大小、哈希及安装位置。独立目录避免覆盖现有 Studio 应用。

### LDraw MCP 与 Blender

- LDraw MCP `0.3.1`，源码提交 `71cf1e2c9dc0057857ba7d3b88b0830942f5b269`。
- 独立环境：`D:/lego/backend/storage/tool_research/ldraw-venv`，未向后端 Conda 环境安装 MCP 依赖。
- Blender `4.5.14 LTS` 官方便携版，下载经官方镜像；SHA256 与官方发布的 `.sha256` 文件一致：`b9533d2397ac1984db4466fb23a7a4649391cca93f6e84209f9bcc60d071c8b9`。
- ImportLDraw `1.3.0` 来自作者 GitHub release，安装到独立 `blender-scripts/addons`。Windows 原生自动检测不兼容，配置 `BLENDER_USER_SCRIPTS` 解决。
- 复用 `D:/lego/Studio 2.0/ldraw` 零件库。
- 已通过 Codex CLI 注册 `ldraw` 到 `C:/Users/19337/.codex/config.toml`，不修改其他 MCP 配置；参考 [OpenAI Docs 的 MCP 配置说明](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。当前回合用直接 stdio 客户端验证，注册不等于当前回合的原生工具目录已重新加载。
- `backend/tasks/check_ldraw_tools.py` 实测 initialize/list_tools、颜色与铰链查询、MPD 清单、透明件小样双视图。清单分别计数 610 / 1,234 / 2,120，逐项零件号、颜色、数量与三个场景一致；库中无缺失零件及未知颜色。颜色名称已知不等于零件/颜色组合有库存。
- 测试结果：`backend/storage/tool_research/validation/mcp-check.json`，小样图 `renderer-smoke.png`。
- F40 1:24 真实几何双视图：`validation/f40-1-24-blender.png`，已打开检查，仍有明显盒状外形、简化风挡及轮拱。该渲染不标为外观通过，也不替代机构扫掠。

复核命令（在 `D:/lego`）：

```powershell
& backend/storage/tool_research/ldraw-venv/Scripts/python.exe backend/tasks/check_ldraw_tools.py --render
```

### 装配诊断 skill

通过 `skill-installer` 安装 `hbmartin/legolization` 的 `analyze-lego-assembly` 到 `C:/Users/19337/.codex/skills/analyze-lego-assembly`，下个回合可用。该 skill 要求 `legolization >=0.6.0`；PyPI 当前提供的 0.5.0 缺少所需命令，已在独立 Python 3.12 环境从源码提交 `03c30458f4e238c589d47a9bd506433184de6415` 安装 0.6.0，依赖 `pyldraw3` 固定提交 `465f783723ebd4f0a234b826b22b32f2c1d18b73`。`--version` 与 `analyze --help` 已验证。

首次诊断返回 `INDETERMINATE`：其独立 pyldraw 零件索引尚未初始化。下载官方 LDraw 库后，索引写入遭遇 Windows 默认 GBK 无法编码的问题，完整索引还需慢速打开两万多文件。保留原下载与错误日志，停止失败的全库准备；用 `backend/tasks/analyze_f40_external.py` 构建当前模型所需的局部索引，UTF-8 写入并在进程内配置，不改用户全局 pyldraw 配置。索引涵盖 F40 1:24 的 16 个零件号、83 个递归几何依赖，来源和文件哈希保存在 `scoped-analysis-library/source-manifest.json`。这不是全库支持。

实际 `--no-repair` 诊断识别 610/610 个实例，结果 `DISCONNECTED`，JSON 状态 `unbuildable`、退出码 2；报告、连接图、断开组件 MPD、悬空件 MPD 和 HTML 已生成。路径：`backend/storage/tool_research/scoped-analysis-library/e08894ce-7909-48f2-a3cf-16292d0a4e3e-analysis/analysis.html`。组件范围为 16–221，说明其连接证据覆盖仍有不确定性；报告中质量与受力推测不能代替实物验证，也不能覆盖本项目检查或 Studio 检查结果。

复核命令（使用上述已安装的 `analyze-lego-assembly` 工作流）：

```powershell
$env:PYTHONUTF8='1'
$env:LEGOLIZATION_RENDERER='none'
& backend/storage/tool_research/legolization-venv/Scripts/python.exe backend/tasks/analyze_f40_external.py
```

## 已落实到流程

1. 六张基础外观参考之外，加入发动机、座舱、座椅、车门和前后盖状态；按比例增加转向或悬挂。
2. 规划可以提出最多四项定向细节需求，记录关注点、相机角度、原因和对应模块。追加角度包括仪表台、门铰链、盖铰链、底盘、后排或检修空间。
3. 修正相关视图时保留旧图历史，采用请求与文件哈希复用；只生成指定视图。调用预算用尽时保留图和装配草稿、明确尚缺视图。
4. 官方搭建参考与 AI 实车参考分别输入；不把官方清单直接当装配，不缩放零件变换。
5. Studio 文件回读核对步骤成员、颜色、变换和数量。1:24/1:16 当前文件分别通过 60/110 个步骤成员核对。

优先级应是：依据官方 F40 页面重建合法的车门/后盖小模块，独立检查挂载和运动，再接回整车；随后为 1:16/1:12 设计转向/悬挂。渲染 MCP 和文件编辑 MCP 可辅助，无法自动补齐这些工程工作。
