# Car2LEGO 产品优化与完善方案

> **文档版本**: v1.0  
> **编写日期**: 2026-07-04  
> **作者**: 产品经理  
> **状态**: Draft for Review  

---

## 目录

1. [现状评估](#1-现状评估)
2. [产品愿景与战略](#2-产品愿景与战略)
3. [优化路线图总览](#3-优化路线图总览)
4. [Phase 1: 稳定性与基础修复](#4-phase-1-稳定性与基础修复)
5. [Phase 2: 核心体验升级](#5-phase-2-核心体验升级)
6. [Phase 3: 社区与社交](#6-phase-3-社区与社交)
7. [Phase 4: 商业化与规模化](#7-phase-4-商业化与规模化)
8. [Phase 5: 高级功能与生态](#8-phase-5-高级功能与生态)
9. [技术债务清理](#9-技术债务清理)
10. [度量指标](#10-度量指标)

---

## 1. 现状评估

### 1.1 产品优势

| 维度 | 评估 | 说明 |
|------|------|------|
| 核心技术架构 | ⭐⭐⭐⭐ | L1→L4 四级匹配策略清晰，从官方套装到 AI 生成的降级路径设计合理 |
| 车辆识别能力 | ⭐⭐⭐⭐⭐ | 52 种子风格、80+ 特征、50 种颜色的分类体系业内领先 |
| AI 集成深度 | ⭐⭐⭐⭐ | Claude Vision 图像分析 + Claude 文本生成双管线，结构化输出稳定 |
| Studio 兼容性 | ⭐⭐⭐⭐ | .io 文件格式读写完整，支持 LDraw 标准，与 BrickLink Studio 2.0 无缝对接 |
| 3D 预览 | ⭐⭐⭐ | Three.js 浏览器内渲染可用，支持分步展示和修改前后对比 |
| 改装系统 | ⭐⭐⭐⭐ | MOD_SPEC v1.0 规范完善，社区改装仓库设计合理 |

### 1.2 关键问题

| 严重度 | 问题 | 影响 |
|--------|------|------|
| 🔴 Critical | `features.primary_color` vs `primary_color_name` 属性名不匹配导致运行时崩溃 | 图片上传功能完全不可用 |
| 🔴 Critical | L1 匹配返回单个占位砖块，而非真实零件清单 | 官方套装匹配结果无意义 |
| 🔴 Critical | 无用户系统，所有设计匿名 | 无法保存、分享、追溯设计历史 |
| 🔴 Critical | 零测试覆盖 | 任何改动都可能引入线上故障 |
| 🟠 High | Celery 异步任务仅在 REDIS_URL 存在时才启动，配置缺失时设计永久 pending | 开发/无 Redis 环境无法使用 AI 生成 |
| 🟠 High | StudioDesignGenerator 同步阻塞事件循环 | 并发性能瓶颈 |
| 🟠 High | 定价全部为估算，无实时 BrickLink API 集成 | 价格不准确，失去购物引导价值 |
| 🟠 High | 前端缺少图片上传入口 | 核心 Vision 分析功能对用户不可见 |
| 🟡 Medium | 3D 查看器零件尺寸估算粗糙（40 个硬编码零件映射） | 大部分零件显示错误 |
| 🟡 Medium | 无数据库迁移（Alembic 配置但无迁移文件） | 生产部署不可持续 |
| 🟡 Medium | 定制化时完整基础 LDraw 发送给 Claude，截断风险 | 大设计定制可能失败 |
| 🟡 Medium | 汽车网络研究缺少实际 HTTP 请求实现 | 未知汽车查询无法工作 |

### 1.3 技术债务量化

| 类别 | 项目数 | 预估工时 |
|------|--------|----------|
| 运行时 Bug | 2 | 2d |
| 缺失测试 | 全量 (~60 文件) | 15d |
| 缺失迁移 | 全量 (8 个模型) | 3d |
| 同步阻塞代码 | 3 个服务 | 5d |
| 硬编码配置 | 10+ 处 | 2d |
| **合计** | | **27d** |

---

## 2. 产品愿景与战略

### 2.1 产品定位

**一句话定位**: 为全球汽车爱好者提供从"真车 → LEGO 设计 → 零件购买"的一站式平台。

**目标用户画像**:
- **汽车爱好者** (核心): 想为自己或朋友的爱车搭建 LEGO 版本
- **LEGO 玩家**: 寻找独特 MOC 设计灵感，扩展搭建范围
- **改装车迷**: 希望虚拟化改装方案，预览 LEGO 改装效果
- **礼品购买者**: 为汽车爱好者朋友定制个性化礼物

### 2.2 核心价值主张

```
拍照/输入 → [AI 识别分析] → [LEGO 设计生成] → [3D 预览] → [零件清单+价格] → [一键购买]
                                                                     ↓
                                                              [社区分享/改装]
```

### 2.3 竞争格局

| 竞品 | 模式 | 我们的优势 |
|------|------|-----------|
| Rebrickable | MOC 数据库 | AI 自动生成，无需手动设计 |
| BrickLink Studio | 手动设计工具 | 零门槛，无需 LEGO 设计技能 |
| 手工 MOC 设计师 | 人工服务 | 即时、低成本、可规模化 |
| LEGO Builder App | 官方搭建说明 | 支持任意车型，而非仅官方套装 |

---

## 3. 优化路线图总览

```
Phase 1 (Week 1-3)          Phase 2 (Week 4-7)          Phase 3 (Week 8-11)
稳定性 & 基础修复            核心体验升级                社区 & 社交
─────────────────────      ─────────────────────      ─────────────────────
🔧 Bug 修复                 👤 用户系统                 🌐 公开作品画廊
🧪 测试覆盖                 📸 图片上传前端             ❤️ 点赞/收藏/评论
🗄️ 数据库迁移               📡 SSE 实时进度             👥 用户主页
📦 零件清单导入              🎨 3D 查看器升级            ⭐ 评分系统
🔄 异步重构                  💰 实时定价 API            🔗 改装依赖管理
                             🔄 设计版本管理            📤 MOD 上传流程
                             🔍 搜索 & 筛选              🏆 精选作品

Phase 4 (Week 12-16)       Phase 5 (Week 17-24)
商业化 & 规模化             高级功能 & 生态
─────────────────────      ─────────────────────
💳 购物车 & 购买             🎬 视频帧分析
⭐ 会员体系                  📐 3D 模型导入
⚡ 优先级队列                🏗️ 自动搭建说明
📊 管理后台                  📱 移动端适配
🌐 CDN & 性能                🤖 零件颜色优化
🛡️ 安全加固                  🎮 Studio 深度集成
```

---

## 4. Phase 1: 稳定性与基础修复

> **优先级**: P0 - 必须完成才能进入后续阶段  
> **周期**: 3 周  
> **目标**: 消除已知 Bug，建立质量基础，让核心流程可运行

### 4.1 Bug 修复 (Week 1)

#### 4.1.1 [Critical] 修复 Vision 分析颜色字段属性名错误

- **文件**: `backend/app/api/v1/designs.py:443`
- **问题**: `features.primary_color` 应为 `features.primary_color_name`
- **影响**: 图片上传 API 运行时 AttributeError
- **修复**: 全局搜索 `primary_color` 引用，统一更正为 `primary_color_name`
- **验收**: 上传汽车图片后 API 正常返回设计结果

#### 4.1.2 [High] 修复 analysis_text 字段未填充

- **文件**: `backend/app/services/vision_analyzer.py:439`
- **问题**: `analysis_text` 赋值为 `design_guidance` 而非原始分析文本
- **修复**: 新增 `raw_analysis` 字段存储完整 Claude 响应，`analysis_text` 存储摘要
- **验收**: API 返回的分析文本包含有意义的车辆描述

#### 4.1.3 [High] 修复 L1 匹配占位零件

- **文件**: `backend/app/api/v1/designs.py` create_design 函数
- **问题**: L1 匹配仅创建单个白色 2x4 砖块占位
- **方案**:
  1. 集成 Rebrickable API 获取已知套装的完整零件清单
  2. 本地缓存热门套装零件数据（避免重复 API 调用）
  3. 若 Rebrickable 不可用，回退到 `LegoSet.parts` 关联数据
- **验收**: 查询 Porsche 911 返回完整 Speed Champions 套装零件清单

#### 4.1.4 [Medium] 修复 Celery 任务在无 Redis 环境下的行为

- **文件**: `backend/app/api/v1/designs.py`, `backend/tasks/generation.py`
- **问题**: REDIS_URL 缺失时 AI 生成任务无法调度，设计永久 pending
- **方案**:
  1. 新增同步回退模式：`run_generation_sync()` 直接在当前进程执行
  2. 前端轮询兼容（同步模式 status 直接更新为 completed）
  3. 环境变量 `GENERATION_MODE=sync|async` 控制
- **验收**: 无 Redis 环境下 AI 生成正常工作

### 4.2 测试体系 (Week 1-2)

#### 4.2.1 单元测试覆盖

```
tests/
├── unit/
│   ├── services/
│   │   ├── test_matching_engine.py      # L1-L4 匹配逻辑
│   │   ├── test_pricing_service.py      # 价格估算
│   │   ├── test_color_service.py        # 颜色匹配
│   │   ├── test_ldraw_service.py        # LDraw 格式
│   │   ├── test_vehicle_taxonomy.py     # 分类系统
│   │   └── test_studio_service.py       # .io 文件读写
│   ├── integrations/
│   │   └── test_nhtsa.py                # NHTSA API (mock)
│   └── models/
│       └── test_design.py               # 模型关系
├── integration/
│   ├── test_api_designs.py              # 设计 API 端到端
│   ├── test_api_export.py               # 导出 API
│   └── test_vision_analyzer.py          # Vision (mock Claude)
└── conftest.py                          # Fixtures, mock 工厂
```

- **目标覆盖率**: 核心服务 > 80%，API 端点 > 60%
- **工具**: pytest + pytest-asyncio + pytest-cov + httpx (async test client)
- **Mock 策略**: Claude API / NHTSA / Rebrickable 全部 mock，数据库使用 SQLite in-memory

#### 4.2.2 CI 流水线

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Backend tests
        run: cd backend && pip install -r requirements.txt && pytest --cov
      - name: Frontend tests  
        run: cd frontend && npm ci && npm run test
      - name: Lint
        run: |
          cd backend && ruff check .
          cd frontend && npx next lint
```

### 4.3 数据库迁移 (Week 2)

#### 4.3.1 Alembic 初始化

- 为所有 8 个模型生成 Initial migration
- 添加 `alembic/versions/001_initial.py`
- 修复 `Base.metadata.create_all` → 改为 `alembic upgrade head`
- docker-compose 添加自动迁移启动命令

#### 4.3.2 Schema 修正

| 变更 | 说明 |
|------|------|
| `designs` 表添加 `scale` 列 | API 接受但模型未存储 |
| `designs` 表添加 `user_id` 列 | 为 Phase 2 用户系统预留 |
| `designs` 表添加 `visibility` 列 | public/private/unlisted |
| `designs` 表添加 `updated_at` 列 | 修改时间追踪 |
| `design_parts.price_guide` 填充逻辑 | 从定价服务写入 |

### 4.4 异步重构 (Week 2-3)

#### 4.4.1 异步化核心服务

```python
# 当前 (同步阻塞)
class StudioDesignGenerator:
    def generate(self, design_id, make, model, year, ...):
        response = self.llm.client.messages.create(...)  # 阻塞 20-60s
        
# 目标 (异步)
class StudioDesignGenerator:
    async def generate(self, design_id, make, model, year, ...):
        response = await self.llm.client.messages.create(...)
```

需改造的服务:
- `StudioDesignGenerator.generate()` → async
- `VisionAnalyzer.analyze_image()` → async
- `VisionAnalyzer.analyze_multiple_views()` → async

#### 4.4.2 图片预处理

- 上传图片自动压缩到 2048px 以内
- JPEG quality 85% 平衡质量与体积
- 自动检测并纠正旋转方向（EXIF orientation）
- 支持 WebP 输入格式

### 4.5 Phase 1 交付清单

- [ ] Bug: `primary_color` → `primary_color_name` 修复并测试
- [ ] Bug: `analysis_text` 正确填充
- [ ] Bug: L1 零件清单从 Rebrickable 导入
- [ ] Feature: 无 Redis 环境同步生成回退
- [ ] Feature: 单元测试覆盖核心服务 (target > 80%)
- [ ] Feature: 集成测试覆盖关键 API
- [ ] Feature: CI 流水线 (GitHub Actions)
- [ ] Feature: Alembic 初始迁移
- [ ] Feature: Schema 修正 (scale, user_id, visibility, updated_at)
- [ ] Refactor: 核心服务异步化
- [ ] Refactor: 图片上传预处理管线

---

## 5. Phase 2: 核心体验升级

> **优先级**: P1 - 核心用户价值  
> **周期**: 4 周  
> **目标**: 完成端到端核心流程，用户可以拍照→获得LEGO设计→查看价格→导出

### 5.1 用户系统 (Week 4)

#### 5.1.1 认证模块

```
POST   /api/v1/auth/register          # 邮箱注册
POST   /api/v1/auth/login              # 登录 (返回 JWT)
POST   /api/v1/auth/refresh            # 刷新 Token
POST   /api/v1/auth/logout             # 登出
GET    /api/v1/auth/me                 # 当前用户信息
POST   /api/v1/auth/oauth/google       # Google OAuth
POST   /api/v1/auth/oauth/github       # GitHub OAuth
```

- JWT access token (15min) + refresh token (7d)
- 密码 bcrypt 哈希
- 邮箱验证流程（可选，通过配置开关）

#### 5.1.2 用户模型

```python
class User(Base):
    id: UUID (PK)
    email: str (unique)
    username: str (unique)
    password_hash: str
    avatar_url: str?
    oauth_provider: str?        # google / github
    oauth_id: str?
    email_verified: bool
    created_at: datetime
    last_login_at: datetime
    
    # Relations
    designs: list[Design]
    community_mods: list[CommunityMod]
```

#### 5.1.3 权限控制

- 未登录: 仅可浏览公开设计
- 已登录: 创建设计、保存、自定义
- 管理员: 管理后台访问
- API 限流: 免费用户 10 req/min，Pro 用户 60 req/min

### 5.2 前端图片上传 (Week 4-5)

#### 5.2.1 上传交互

```
┌──────────────────────────────────────────┐
│          Create Your LEGO Car              │
│                                            │
│  ┌─────────────────────┐  ┌────────────┐ │
│  │                     │  │            │ │
│  │   📷 Drop photo or   │  │  OR        │ │
│  │   click to upload    │  │            │ │
│  │                     │  │  Text input │ │
│  │  Supports: JPG,PNG, │  │            │ │
│  │  WEBP, HEIC         │  │  Make: ___ │ │
│  │                     │  │  Model: __ │ │
│  │  Front/Side/Rear/   │  │  Year: ___ │ │
│  │  3/4 views accepted │  │            │ │
│  └─────────────────────┘  └────────────┘ │
│                                            │
│  [Advanced: Multi-angle upload]           │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │Front │ │Side  │ │Rear  │ │3/4   │    │
│  │  📷  │ │  📷  │ │  📷  │ │  📷  │    │
│  └──────┘ └──────┘ └──────┘ └──────┘    │
│                                            │
│  [ Generate LEGO Design ]                  │
└──────────────────────────────────────────┘
```

- 拖拽上传 + 点击选择
- 图片预览 + 裁剪（可选）
- 多角度上传（最多 4 张）
- 上传进度条
- 自动压缩（前端 Canvas resize）

### 5.3 实时生成进度 (Week 5)

#### 5.3.1 SSE (Server-Sent Events) 替代轮询

```
GET /api/v1/designs/{id}/stream

event: progress
data: {"stage": "analyzing", "message": "识别车辆特征...", "percent": 15}

event: progress  
data: {"stage": "matching", "message": "匹配 LEGO 零件库...", "percent": 40}

event: progress
data: {"stage": "generating", "message": "Claude 正在设计...", "percent": 70}

event: progress
data: {"stage": "packaging", "message": "生成 Studio 文件...", "percent": 90}

event: complete
data: {"design_id": "xxx", "parts_count": 87}
```

#### 5.3.2 前端进度展示

```
┌────────────────────────────────────────┐
│        Generating Your LEGO Car         │
│                                         │
│  🚗 → 🔍 → 🧱 → 📦                     │
│  Analyzing → Matching → Building → Done │
│                                         │
│  ████████████░░░░░░░░  60%             │
│                                         │
│  Matching LEGO parts to your Porsche   │
│  911's body lines...                    │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Estimated time remaining: ~15s  │   │
│  └─────────────────────────────────┘   │
└────────────────────────────────────────┘
```

### 5.4 3D 查看器升级 (Week 5-6)

#### 5.4.1 零件库精度提升

当前问题: 仅 40 个硬编码零件尺寸 → 需要映射 ≥ 1000 个常见零件。

解决方案:
- 解析 Studio 自带的 `StudioPartDefinition2.txt` (33K 零件映射)
- 提取每个零件的包围盒 (bounding box) 数据
- 构建 LDraw part_num → {width, length, height} 查找表
- 无法获取实际尺寸的零件，使用类别默认值

#### 5.4.2 渲染改进

| 改进项 | 方案 |
|--------|------|
| 零件纹理 | 螺柱 (stud) 顶面几何体 + 侧面凹槽 |
| 透明零件 | `material.transparent = true`, `opacity = 0.6` (挡风玻璃/车灯) |
| 颜色精度 | 从 `LDConfig.ldr` 加载 180 种 LEGO 颜色 |
| 阴影 | `receiveShadow: true` + `castShadow: true` |
| 线框模式 | 可选切换，展示零件边界 |
| 爆炸视图 | 零件沿 Y 轴分层展开 |

#### 5.4.3 交互改进

- 点击零件 → 侧边栏显示零件编号、颜色、数量
- 零件清单高亮联动（点击清单项 → 3D 视图高亮该零件）
- 步骤导航（Previous Step / Next Step 按钮 + 键盘快捷键）
- 自动旋转模式 (Turntable)
- 截图按钮（导出 PNG，含透明背景选项）

### 5.5 设计版本管理 (Week 6)

#### 5.5.1 版本模型

```python
class DesignVersion(Base):
    id: UUID (PK)
    design_id: UUID (FK → designs.id)
    version_number: int           # 1, 2, 3...
    change_summary: str           # "添加了尾翼，更换了轮毂"
    parts_snapshot: JSON          # 该版本的零件清单快照
    ldr_snapshot: Text            # 该版本的 LDraw 文本
    io_file_path: str
    created_at: datetime
```

#### 5.5.2 版本操作

- **Fork**: 基于任意公开设计创建副本
- **Branch**: 从任意版本开始自定义
- **Compare**: 两个版本并排对比（3D 分屏 + 零件差异表）
- **Revert**: 回退到历史版本

### 5.6 实时定价 (Week 6-7)

#### 5.6.1 BrickLink API 集成

```python
class BrickLinkPricingService:
    async def get_part_price(part_num: str, color_id: int) -> PriceInfo:
        """获取零件在 BrickLink 的实时价格"""
        
    async def price_parts_list(parts: list[DesignPart]) -> PricedPartsResult:
        """批量定价，含缓存"""
        
    async def get_price_history(part_num: str, color_id: int) -> list[PricePoint]:
        """价格趋势（6 个月）"""
```

- 使用 BrickLink API v3 (需注册开发者账号)
- Redis 缓存 (TTL: 现货价格 1h，历史价格 24h)
- API 失败时回退到估算价格
- Rate limit 保护

#### 5.6.2 价格展示

```
┌────────────────────────────────────────────────────┐
│  Parts Cost Breakdown                               │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Total Estimated Cost:  $47.32 - $63.18      │   │
│  │ (based on BrickLink 6-month average)        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Top 5 Most Expensive Parts:                       │
│  1. Wheel 18974 (x4) ............ $3.20/ea  $12.80 │
│  2. Windscreen 87752 ............. $2.45     $2.45 │
│  3. Wedge Plate 43723 (x2) ...... $1.80/ea   $3.60 │
│  ...                                                │
│                                                     │
│  💡 Cost-saving tip: Replace 18974 with 55976      │
│     to save ~$6. (color may vary slightly)         │
│                                                     │
│  [Buy Parts on BrickLink]  [Export Wanted List]    │
└────────────────────────────────────────────────────┘
```

### 5.7 搜索与发现 (Week 7)

#### 5.7.1 设计搜索

```
GET /api/v1/designs/search?q=porsche+911&body_style=sports_car&era=modern&sort=newest
```

- 全文搜索 (PostgreSQL `tsvector` 或 SQLite FTS5)
- 筛选器: 品牌、车身风格、年代、性能等级、难度
- 排序: 最新、最热门、零件数最少/最多
- 分页: cursor-based (更稳定)

#### 5.7.2 前端搜索体验

- 搜索栏 (全局，支持 ⌘K 快捷键)
- 筛选面板 (侧边栏或顶部水平 filter bar)
- 搜索结果卡片 (缩略图 + 基本信息 + 零件数 + 难度)
- 无限滚动加载

### 5.8 Phase 2 交付清单

- [ ] 用户注册/登录/认证 (JWT + OAuth)
- [ ] 前端图片上传 (拖拽 + 多角度)
- [ ] SSE 实时生成进度
- [ ] 3D 查看器: 零件精度提升至 1000+ 零件
- [ ] 3D 查看器: 透明零件 + 阴影 + 零件点击
- [ ] 设计版本管理 (Fork/Branch/Compare/Revert)
- [ ] BrickLink 实时定价 API 集成
- [ ] 价格趋势 + 省钱建议
- [ ] 设计搜索与筛选
- [ ] 用户仪表板 (我的设计, 收藏)

---

## 6. Phase 3: 社区与社交

> **优先级**: P2 - 用户留存与增长  
> **周期**: 4 周  
> **目标**: 建立活跃的创作者社区，UGC 驱动内容增长

### 6.1 公开画廊 (Week 8)

#### 6.1.1 作品展示

```
┌──────────────────────────────────────────────────────┐
│  Community Gallery                    [Search] [Filter]│
│                                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │ 🏎️       │ │ 🚙       │ │ 🚐       │ │ 🏎️       ││
│  │ Porsche  │ │ Tesla    │ │ VW Bus   │ │ Supra    ││
│  │ 911 GT3  │ │ Cybertruck│ │ 1965     │ │ MK4      ││
│  │          │ │          │ │          │ │          ││
│  │ ❤️ 234  │ │ ❤️ 189  │ │ ❤️ 421  │ │ ❤️ 567  ││
│  │ 💬 45   │ │ 💬 23   │ │ 💬 67   │ │ 💬 89   ││
│  │ @builder │ │ @carfan  │ │ @vintage │ │ @jdm_fan ││
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘│
│                                                       │
│  Trending | Newest | Most Liked | Staff Picks         │
└──────────────────────────────────────────────────────┘
```

#### 6.1.2 作品详情页（公开版）

- 3D 查看器 (iframe embeddable)
- 零件清单 + 价格
- 来自其他社区成员的 Remix / Fork 版本
- 评论区
- 分享按钮 (Twitter, Reddit, Discord, LEGO forums)
- Embed 代码 (Markdown/HTML)
- 导出选项 (和私有设计一致)

### 6.2 社交互动 (Week 9)

#### 6.2.1 互动功能

| 功能 | 实现 |
|------|------|
| 点赞 (Like) | 简单 toggle，计数缓存 |
| 收藏 (Bookmark) | 私人收藏夹，可分类管理 |
| 评论 | Markdown 支持，嵌套回复（1 层） |
| 分享 | 生成短链接 + Open Graph meta 标签 |
| 关注 (Follow) | 关注作者，动态 feed |
| @提及 | 评论中 @用户名 通知 |

#### 6.2.2 通知系统

```
通知类型:
├── 🔔 有人点赞了你的设计
├── 💬 有人评论了你的设计  
├── 🔄 有人 Fork 了你的设计
├── ⭐ 你的设计入选了精选
├── 👤 有人关注了你
└── 📦 你关注的作者发布了新设计
```

- UI: 铃铛图标 + 未读计数徽章
- 通知中心: 下拉面板，支持标记已读
- 可选邮件通知（每日/每周摘要）

### 6.3 用户主页 (Week 9-10)

```
┌──────────────────────────────────────────────┐
│  ┌────┐                                      │
│  │头像│  @builder_pro                         │
│  └────┘  LEGO Car Designer                    │
│           Joined March 2026                    │
│                                               │
│  ┌──────┐ ┌──────┐ ┌──────┐                 │
│  │  42  │ │ 1.2K │ │  15  │                 │
│  │Designs│ │ Likes│ │Follow│                 │
│  └──────┘ └──────┘ └──────┘                 │
│                                               │
│  [Designs] [Likes] [Collections] [About]      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ Design 1 │ │ Design 2 │ │ Design 3 │     │
│  └──────────┘ └──────────┘ └──────────┘     │
└──────────────────────────────────────────────┘
```

### 6.4 社区 MOD 完善 (Week 10)

#### 6.4.1 MOD 上传流程

```
创作者 → 本地 Studio 测试 → 导出 .ldr → 填写 MOD_SPEC manifest → 上传 → 审核 → 发布
```

- Web 端上传表单 (manifest 编辑器 + 预览图 + LDraw 附加)
- MOD 验证器 (自动检查 manifest 完整性、LDraw 格式、零件引用有效性)
- 审核队列 (管理员审批或自动发布 with 举报机制)

#### 6.4.2 MOD 依赖管理

- `depends_on: ["mod_id_1", "mod_id_2"]` 自动安装依赖
- `incompatible_with: ["mod_id_3"]` 冲突检测并提示
- MOD 版本锁定 (`"base_chassis_v2": ">=2.1.0,<3.0.0"`)

#### 6.4.3 MOD 评价

- 评分 (1-5 星)
- 搭建体验报告 (零件配合度、说明清晰度)
- "我也搭建了" 功能 (展示社区成员使用该 MOD 的作品)

### 6.5 挑战与活动 (Week 11)

#### 6.5.1 主题挑战

```
本月挑战: "80年代经典车"
🏆 奖品: BrickLink 礼品卡 $50
📅 截止: 2026-07-31
提交: 42 个作品

[查看挑战] [提交作品]
```

#### 6.5.2 精选集

- 编辑精选 (Staff Picks)
- 按主题策划 (JDM 合集、美式肌肉车、未来概念车)
- 按难度策划 (新手友好、大师作品)

### 6.6 Phase 3 交付清单

- [ ] 公开画廊 (浏览/搜索/筛选)
- [ ] 作品详情公开页 + 嵌入支持
- [ ] 点赞/收藏/评论
- [ ] 关注 + 动态 Feed
- [ ] 通知系统
- [ ] 用户主页
- [ ] MOD 上传 Web 流程
- [ ] MOD 依赖/冲突管理
- [ ] MOD 评分系统
- [ ] 主题挑战
- [ ] 精选集

---

## 7. Phase 4: 商业化与规模化

> **优先级**: P3 - 商业可持续性  
> **周期**: 5 周  
> **目标**: 建立可持续的商业模式，支持规模化运营

### 7.1 会员体系 (Week 12)

#### 7.1.1 定价方案

| 特性 | Free | Pro ($4.99/mo) | Studio ($12.99/mo) |
|------|------|----------------|---------------------|
| 月度 AI 生成次数 | 5 | 50 | 200 |
| 图片识别 | ✅ | ✅ | ✅ |
| 3D 查看器 | Basic | Advanced | Advanced |
| 零件定价 | 估算 | BrickLink 实时 | BrickLink 实时 + 省钱建议 |
| 导出格式 | .ldr, .csv | 全部 | 全部 + PDF 说明 |
| 设计版本管理 | 3 版本 | 20 版本 | 无限 |
| 优先队列 | ❌ | ✅ | ✅ |
| 批量生成 | ❌ | ❌ | ✅ (一次 5 辆) |
| Studio 一键打开 | ❌ | ✅ | ✅ |
| MOD 创建 | 只读 | ✅ | ✅ |
| 去广告 | ❌ | ✅ | ✅ |
| API 访问 | ❌ | ❌ | ✅ (1000 req/day) |

#### 7.1.2 支付集成

- Stripe Checkout (信用卡 + Apple Pay + Google Pay)
- PayPal
- 优惠码系统
- 年付 20% 折扣
- 7 天免费试用 (Pro)

### 7.2 购物转化 (Week 12-13)

#### 7.2.1 一键购买

```
[Buy Parts] → 生成 BrickLink Wanted List → 
  ├── 方案 A: 自动导入到用户 BrickLink 账号
  ├── 方案 B: 自动搜索最优卖家组合
  └── 方案 C: 导出 XML 供手动导入
```

#### 7.2.2 智能采购

- **卖家优化**: 最少包裹数量、最低总价、最快送达
- **零件替换建议**: "零件 X 在您所在地区稀缺，Y 可替代（99% 相似度）"
- **颜色优化**: "将深灰色替换为浅灰色可节省 $3.20"

### 7.3 管理后台 (Week 13-14)

#### 7.3.1 管理仪表板

```
/admin/
├── Dashboard          # DAU, 生成量, 收入, 转化率
├── Users              # 用户管理, 封禁/解封
├── Designs            # 设计审核, 精选管理
├── MODs               # MOD 审核队列
├── Challenges         # 挑战管理
├── Reports            # 举报处理
├── Settings           # 系统配置
└── Analytics          # 详细分析
```

#### 7.3.2 运营工具

- 精选内容管理
- 推送通知
- 邮件营销 (Mailchimp/SendGrid 集成)
- A/B 测试框架
- Feature flags (LaunchDarkly 风格)

### 7.4 性能与规模 (Week 14-15)

#### 7.4.1 性能优化

| 目标 | 方案 |
|------|------|
| API 响应 < 200ms (P95) | 数据库查询优化 + Redis 缓存 |
| 首页 LCP < 2.5s | 图片懒加载 + CDN + SSG |
| 3D 查看器 FPS > 30 | InstancedMesh + LOD + 遮挡剔除 |
| AI 生成 P95 < 60s | 优先队列 + 模型缓存 + Prompt caching |

#### 7.4.2 基础设施

```
Cloudflare (CDN + DNS)
    ↓
Load Balancer (Nginx / Cloud Load Balancer)
    ↓
┌──────────────┬──────────────┬──────────────┐
│  Frontend    │  Backend × N │  Celery × M  │
│  (Vercel/    │  (Fly.io/    │  (dedicated  │
│   Cloudflare)│   K8s)       │   workers)   │
└──────────────┴──────────────┴──────────────┘
                      │
          ┌───────────┼───────────┐
          ↓           ↓           ↓
     PostgreSQL    Redis      S3/R2 Storage
     (Primary+     (Cache+     (generated .io
      Read Replica) Queue)      files + images)
```

#### 7.4.3 监控与告警

- **APM**: Sentry (错误追踪) + OpenTelemetry (链路追踪)
- **日志**: 结构化 JSON 日志 → Loki/Grafana
- **指标**: Prometheus (API 延迟、错误率、生成队列长度)
- **告警**: PagerDuty (严重故障), Slack (警告)
- **Synthetic monitoring**: 每 5 分钟的 health check + 核心流程测试

### 7.5 安全加固 (Week 15-16)

#### 7.5.1 安全清单

| 项目 | 措施 |
|------|------|
| API 认证 | JWT + refresh token rotation |
| 文件上传 | MIME 类型检查 + 文件大小限制 + 病毒扫描 |
| SQL 注入 | SQLAlchemy 参数化查询 (已有) |
| XSS | CSP headers + React 默认转义 |
| CSRF | SameSite cookies + CSRF token |
| Rate Limit | 按 IP/User/API Key 限流 |
| 路径遍历 | 拒绝含 `..` 的路径参数 |
| 密钥管理 | 环境变量 (生产用 Vault/Secrets Manager) |
| 依赖扫描 | Dependabot + `pip-audit` + `npm audit` |
| 隐私 | 图片存储 30 天自动清理策略 (可配置) |

### 7.6 Phase 4 交付清单

- [ ] 三级会员体系 (Free/Pro/Studio)
- [ ] Stripe 支付集成
- [ ] 一键购买流程 (BrickLink Wanted List)
- [ ] 智能采购建议
- [ ] 管理后台 (Dashboard + User/Design/MOD 管理)
- [ ] 性能优化 (CDN, 缓存, 查询优化)
- [ ] 生产环境基础设施
- [ ] 监控与告警
- [ ] 安全加固

---

## 8. Phase 5: 高级功能与生态

> **优先级**: P4 - 差异化竞争力  
> **周期**: 8 周  
> **目标**: 建立技术壁垒，拓展使用场景

### 8.1 多模态输入 (Week 17-18)

#### 8.1.1 视频分析

```
上传汽车视频 (10-60s) → 关键帧提取 → 多角度分析 → 3D 重建参考
```

- 使用 FFmpeg 提取关键帧（每 2 秒一帧，场景变化检测）
- 多帧特征融合（投票机制消除单帧误差）
- 运动推断结构 (Structure from Motion) 估算车身比例

#### 8.1.2 3D 模型导入

- 支持格式: `.obj`, `.stl`, `.fbx`, `.glb`
- 自动缩放至 6 格宽 Speed Champions 比例
- 体素化预处理（`ai/voxelizer/` 目录现有占位）
- 从体素模型提取 LEGO 零件布局

#### 8.1.3 URL 导入

- 输入汽车网站 URL → 自动抓取图片 + 规格参数
- 支持: 制造商官网, Wikipedia, Car and Driver, Motor Trend

### 8.2 智能设计优化 (Week 18-20)

#### 8.2.1 零件颜色成本优化

```
Input: 设计 (180 零件, 15 种颜色)
Algorithm: 对于每种颜色，查找最便宜的相似色
Constraint: ΔE < 5.0 (颜色差异不可感知)
Output: 优化后价格 −18%
```

#### 8.2.2 结构强度检查

- 基于物理的稳定性模拟（简化版，检查连接点）
- 标记 "脆弱连接"（单螺柱连接、悬臂过长）
- 建议加固方案

#### 8.2.3 零件稀缺性优化

- 标记停产零件 → 建议替换
- 标记稀有颜色零件 → 建议常见颜色替代
- 稀缺性评分 (1-5)，帮助用户判断可搭建性

### 8.3 Studio 深度集成 (Week 20-21)

#### 8.3.1 一键发送到 Studio

```
Web 端 [Open in Studio] → 
  1. 下载 .io 文件到本地
  2. 通过自定义协议 car2lego:// 唤醒 Studio
  3. Studio 自动打开文件
  4. 自动执行渲染 (通过 Studio Automation)
  5. 渲染图自动回传 Web 端
```

#### 8.3.2 渲染农场

- 服务器端 Studio Headless 渲染（通过 `wine` + Studio 在 Linux 运行）
- 或使用 LDView/POV-Ray 命令行渲染
- 生成: 缩略图、多角度、高清渲染图 (4K)
- 会员专享: 渲染图无水印

#### 8.3.3 自动搭建说明

- 从 LDraw STEP 序列 → PDF 搭建说明
- 使用 LPub3D 或自定义布局引擎
- 输出: A4 打印版、移动端竖版、Studio 内交互式

### 8.4 AI 能力增强 (Week 21-22)

#### 8.4.1 Prompt 缓存优化

```python
# 当前：每次请求发送完整 prompt (~8K tokens)
# 优化：系统提示 + 零件目录使用 Anthropic prompt caching
response = client.messages.create(
    system=[{
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}  # 5-min TTL
    }],
    ...
)
# 节省：~70% 输入 token 成本，延迟降低 ~40%
```

#### 8.4.2 设计质量评分

- Claude 自我评审：生成后自动评估
  - 比例准确性 (1-10)
  - 颜色匹配度 (1-10)
  - 细节还原度 (1-10)
  - 结构合理性 (1-10)
- 低分设计自动重新生成（最多 3 次）

#### 8.4.3 多样式生成

- 同一辆车，生成 3 种风格: Stock (原厂) / Modified (改装) / Racing (赛车)
- 用户可选择喜欢的版本，或混合元素

### 8.5 移动端适配 (Week 22-23)

#### 8.5.1 响应式 Web

- 移动端: 优化触控交互的 3D 查看器（手势旋转/缩放）
- PWA: 离线缓存、添加到主屏幕
- 移动端拍照 → 直接上传流程优化

#### 8.5.2 原生 App (React Native)

```
核心功能 (MVP):
- 📸 拍照识别
- 🔍 浏览设计
- 👀 3D 预览
- 📋 零件清单

后续迭代:
- 🔔 推送通知
- 📱 AR 预览 (ARKit/ARCore 在真实桌面上放置 LEGO 模型)
```

### 8.6 生态系统扩展 (Week 23-24)

#### 8.6.1 公开 API

```
POST /api/v2/designs/generate     # 设计生成
GET  /api/v2/designs/{id}         # 设计查询
GET  /api/v2/parts/catalog        # 零件目录
POST /api/v2/images/analyze       # 图片分析
```

- API Key 管理
- 使用量仪表板
- Webhook 回调 (生成完成通知)
- OpenAPI 3.1 文档 + SDK (Python/JS)

#### 8.6.2 第三方集成

- **Discord Bot**: `/lego Porsche 911` → 生成设计并回复
- **Home Assistant**: 展示收藏设计作为数字装饰
- **BrickLink Store 集成**: 卖家可直接上架完整套装零件包

#### 8.6.3 数据飞轮

```
用户生成设计 → 零件使用数据 → 热门零件推荐 → 更好的设计生成
              → 汽车识别数据 → 分类系统优化 → 更准的图片分析
              → MOD 使用数据  → MOD 推荐        → 更个性化的体验
```

### 8.7 Phase 5 交付清单

- [ ] 视频帧分析输入
- [ ] 3D 模型导入 (.obj/.stl/.fbx/.glb)
- [ ] URL 自动抓取导入
- [ ] 零件颜色成本优化算法
- [ ] 结构强度检查 + 建议
- [ ] 零件稀缺性标记
- [ ] Studio 一键打开 + 渲染回传
- [ ] 自动搭建说明 PDF 生成
- [ ] Prompt caching (降低 70% token 成本)
- [ ] 设计质量自动评分
- [ ] 多样式生成 (Stock/Modified/Racing)
- [ ] 移动端 PWA + React Native MVP
- [ ] 公开 API + Webhook
- [ ] Discord Bot

---

## 9. 技术债务清理

### 9.1 代码质量

| 项目 | 当前状态 | 目标 |
|------|---------|------|
| Type Hints 覆盖率 | ~60% | 100% (mypy strict) |
| Docstring 覆盖率 | ~10% | 80% (公共 API) |
| 重复代码 | `studio_design_generator.py` 与 `customization_service.py` 有重叠的 LDraw 构建逻辑 | 抽到 `ldraw_service.py` |
| 魔法数字 | 大量硬编码值 (score 阈值, token 限制, 图片尺寸) | 提到 config |
| 过时代码 | `design_generator.py` 标记为 DEPRECATED 但仍在代码库中 | 删除 |

### 9.2 依赖管理

| 项目 | 操作 |
|------|------|
| Python 版本 | 锁定 3.12 (当前支持 3.11+) |
| 依赖锁定 | 添加 `requirements.lock` (pip-tools) |
| 前端依赖 | audit + 更新到最新稳定版 |
| Docker 镜像 | 固定 SHA256 digest，不用 `:latest` tag |

### 9.3 错误处理标准化

```python
# 当前：各处模式不一致
raise HTTPException(status_code=500, detail="Something went wrong")

# 目标：统一异常层次
class Car2LEGOError(Exception): ...
class MatchingError(Car2LEGOError): ...
class GenerationError(Car2LEGOError): ...
class ExternalAPIError(Car2LEGOError): ...

# 全局异常处理器 → 统一错误响应格式
{
  "error": {
    "code": "GENERATION_FAILED",
    "message": "AI generation failed after 3 retries",
    "request_id": "req_abc123"
  }
}
```

---

## 10. 度量指标

### 10.1 北极星指标

**月度活跃设计者** (Monthly Active Designers): 每月至少完成 1 次 LEGO 设计生成的注册用户数。

### 10.2 关键指标 (KPI)

| 指标 | 当前基准 | Phase 1 目标 | Phase 2 目标 | Phase 3 目标 |
|------|---------|-------------|-------------|-------------|
| 生成成功率 | ~70% (bug 影响) | > 95% | > 97% | > 98% |
| 生成 P95 耗时 | N/A (无监控) | < 90s | < 60s | < 45s |
| API 错误率 | N/A | < 1% | < 0.5% | < 0.1% |
| 用户注册数 | 0 (无用户系统) | 100 | 1,000 | 10,000 |
| 日活跃用户 (DAU) | 0 | 20 | 200 | 2,000 |
| 设计公开率 | 0% | N/A | 30% | 40% |
| 月付费转化率 | 0% | N/A | N/A | 5% |
| 零件点击购买率 | 0% | N/A | 5% | 10% |
| NPS | N/A | N/A | 40 | 50 |

### 10.3 健康指标

| 指标 | 目标 |
|------|------|
| 测试覆盖率 | > 80% (核心服务) |
| CI 通过率 | > 95% |
| 部署频率 | 每周 2 次 |
| 变更失败率 | < 5% |
| 故障恢复时间 (MTTR) | < 30 min |

---

## 附录 A: 技术架构远景

```
                          ┌─────────────────────────────┐
                          │        CDN + WAF             │
                          │    (Cloudflare / Fastly)     │
                          └─────────────┬───────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ↓                   ↓                   ↓
          ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
          │  Next.js     │     │  FastAPI    │     │  WebSocket  │
          │  (Vercel)    │     │  (K8s × 3)  │     │  Server     │
          └──────┬───────┘     └──────┬──────┘     └──────┬──────┘
                 │                    │                    │
          ┌──────┴───────┐     ┌──────┴──────┐     ┌──────┴──────┐
          │  Static      │     │  Services   │     │  Real-time  │
          │  Assets      │     │  - Matching │     │  - Progress │
          │  (S3 + CDN)  │     │  - Design   │     │  - Chat     │
          └──────────────┘     │  - Export   │     │  - Presence │
                               │  - Pricing  │     └─────────────┘
                               └──────┬──────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                   ↓
          ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
          │  PostgreSQL  │   │    Redis     │   │  S3/R2      │
          │  (RDS, 2AZ)  │   │  (ElastiCache)│   │  (.io/img)  │
          └─────────────┘   └─────────────┘   └─────────────┘
                    │
          ┌─────────┴─────────┐
          ↓                   ↓
┌─────────────┐     ┌─────────────┐
│   Celery    │     │  External   │
│   Workers   │     │  APIs       │
│   (H100 GPU │     │  - Claude   │
│    optional)│     │  - BrickLink│
└─────────────┘     │  - Rebrick  │
                    │  - NHTSA    │
                    └─────────────┘
```

## 附录 B: 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Claude API 成本过高 | 中 | 高 | Prompt caching, 本地模型兜底, 生成队列节流 |
| BrickLink API 限流 | 高 | 中 | 多层缓存, 回退估算价格, 批量请求合并 |
| 版权问题 (汽车设计) | 低 | 高 | 仅生成 LEGO 解释性设计, 不复制商标标志 |
| 用户上传侵权图片 | 低 | 中 | DMCA 投诉流程, 内容审核, 举报系统 |
| LEGO 集团法律行动 | 低 | 极高 | 明确声明非官方, 使用 "兼容" 措辞, 不侵犯 LEGO 商标 |
| 规模化成本失控 | 中 | 中 | 免费层严格限制, 生成队列优先级, 合理 CDN 策略 |

---

> **下一步**: 评审并确定 Phase 1 优先级，分配开发资源，启动 Sprint 1。
