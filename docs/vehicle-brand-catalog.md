# 汽车品牌目录

本项目直接复用 `D:\lego`（Car2LEGO）的品牌选择器、搜索逻辑、中文名映射、目录、Logo 和同步脚本。创建页展示本地 Logo、中文名称与英文名称。中文、英文和名称别名均可检索；“其他”固定在列表底部，选择后显示自定义品牌输入框。已知品牌以标准英文名称提交，自定义品牌使用用户输入，均保存到本次任务的 `request.json` 并进入生图提示词。

## 数据范围与来源

目前收录 396 个品牌记录，包含现存、历史、商用车品牌及部分汽车改装厂。这是可持续补充的全球品牌目录，不保证涵盖全球全部品牌。没有通行中文译名的品牌使用音译或原名加“汽车”；中文名称可在本地映射文件中修订。

- 基础来源：[car-logos-dataset](https://github.com/filippofilip95/car-logos-dataset)，固定版本 `bb2d661f28ce617dba8a51bdfc2069a3381a23b0`。
- 补充来源：Carlogos.org、品牌官网和 Seeklogo，具体页面、Logo 地址及文件 SHA-256 均记录在生成的 JSON 中。
- 车型系列、部分性能部门和纯摩托车品牌从基础数据中排除。小米、问界、乐道、萤火虫、智界、享界、尊界等单独补充。
- Logo 缓存于 `frontend/public/brands/`。用户浏览和选择品牌时不会请求第三方图片网站。

上游 README 声明项目使用 MIT，但其固定版本未包含独立 LICENSE 文件；同时明确 Logo 归各自权利人所有，受各自许可条款约束。项目本身的许可不代表 Logo 的再分发许可，各来源许可情况仍需逐项核实。

## 更新

在本项目根目录运行（不会写入 `D:\lego`）：

```powershell
uv pip install --python .venv/Scripts/python.exe httpx==0.28.1 beautifulsoup4==4.14.2
.venv/Scripts/python.exe scripts/sync_vehicle_brands.py
cd frontend
npm run build
```

`data/vehicle-brand-names.tsv` 维护基础品牌的中文名和检索别名；`data/vehicle-brand-extras.tsv` 维护补充品牌的中文名、来源页面及可选图片地址。生成结果写入 `frontend/lib/data/vehicle-brands.json`。同步会验证 Logo，缺失译名、无效图片或重复 ID 会中止更新，不会发布不完整的目录 JSON。

已有 Logo 会复用。更换某个品牌的图片来源后，应移走该品牌的旧 Logo 再同步。可用 `--revision <commit>` 升级基础数据源，但必须同步补齐新增品牌的中文名。

## 前端行为

热门与全部品牌可切换；搜索涵盖整个目录，空结果时仍可选择“其他”。搜索框按回车不会提交生成表单，唯一匹配时直接选中。支持 Esc、背景点击关闭及焦点恢复。切回目录品牌后，自定义输入会移除。

品牌目录与物理规格获取独立。输入任意目录或自定义品牌的车型后，直接通过配置的大模型对话获取参数，按车型和可选年款/版本保存估算依据与置信度；生成需先获得该身份的基础尺寸。自定义车长同样采用该次参数快照。当前仅 1:24 要求对应的 23–32 studs、8/10/12 studs 车辆配方可生成，其他比例仍仅有要求与规划。选中品牌不代表已有尺寸、独立配方或外观验收。

## 复用来源

- `frontend/components/BrandSelector.tsx`、`frontend/lib/vehicle-brands.ts`：原样复用；样式来自原项目 `globals.css` 的品牌选择器部分。
- `scripts/sync_vehicle_brands.py`：复用原 `backend/tasks/sync_vehicle_brands.py`，只调整本项目根路径和启动说明。
- 原 Car2LEGO MIT 版权全文保存在 `frontend/LICENSE.Car2LEGO`。
