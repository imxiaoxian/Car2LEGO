# 品牌选择与页面实跑记录

验证日期：2026-10-14。独立目录 `D:\Car2LEGO_3D`；原项目 `D:\lego` 没有修改。按用户要求只交付桌面端。

## 复用与目录

品牌组件、搜索逻辑、396 条目录及中文映射与原文件哈希一致。396 个品牌 ID 唯一，全部 Logo 文件存在且 SHA-256 与目录一致。同步脚本只调整根目录和运行说明。

## 本地验证

- `npm run build`：TypeScript 检查和 Vite 生产构建通过。
- `.venv/Scripts/python.exe -m pytest -q`：93 项通过，14 条既有 matplotlib/pyparsing 弃用警告。任务层测试使用模拟进程；下面的完整流程另行实际运行。
- `.venv/Scripts/python.exe scripts/verify_examples.py`：59 个已有样例哈希及 LDraw/BOM 数量通过。
- agent-browser 实际页面：中文“奔驰”检索、英文“BMW”检索、全部目录 396 条、无匹配结果时选择“其他”、自定义输入“星河汽车”、切回宝马移除自定义输入、唯一匹配回车选择、焦点恢复、Esc 关闭。
- 1440×900、1264×625 桌面视口：品牌名称与 Logo 正常显示，列表内部滚动，“其他”始终可见。
- 1:16 选中后生成按钮禁用；该比例未实现的配方不会启动模型。品牌选择不会自动补造物理规格。
- 浏览器无页面错误；页面刷新后恢复最近任务与下载链接。

![品牌目录](assets/brands-desktop.png)

## 实际完整流程

从页面提交 Ferrari / F40 / 红色 / 1:24 / seed 42，调用真实 SD-Turbo、TripoSR、物理规格校准、LEGO 转换与 Studio 导出。

- 任务 ID：`9418fbd9ec484614a56bb826c7151503`。
- 总耗时：106.136 秒，包含网络检查与本地缓存回退。
- 输出：`runs/web/9418fbd9ec484614a56bb826c7151503/artifacts/04-studio/model.io`。
- 234 件真实零件引用、27 个步骤。
- HTTP 下载字节与本地 `.io` 一致；ZIP 完整性检查通过，LDraw 归档回读通过。
- `.io` SHA-256：`657316fd9088900e79d2f0714aeabebc315fecd7b63fbe29028091b0235d0783`。
- `request.json` 保存标准品牌 `Ferrari`、中文名 `法拉利`、目录 ID `ferrari` 及实际生图提示词。

![页面完成状态](assets/web-completed.png)

这次验证确认品牌选择进入生成流程和下载有效，不代表外观、Studio GUI、机构或实物拼装验收通过。保留 `appearance_accepted=false`、`delivery_accepted=false`、`buildability=unverified`。

## 动态规格实跑

之后将 F40 从本地固定物理规格改为在页面调用 `vehicle-spec-search` skill 联网检索。车型未填写年款时，官方 F40（1987）双座公路版页面提供适用范围；车门和风挡的未公开工程尺寸保持 unknown。

- 规格检索 ID：`e8e8bf93231c418bb32204ce36eb78ff`；来源：[Ferrari F40 (1987)](https://www.ferrari.com/en-EN/auto/f40)。返回长/宽/高 `4358/1970/1124 mm`、轴距 `2450 mm`、轮距 `1594/1606 mm`、原厂轮胎规格 `245/40 ZR 17` 和 `335/35 ZR 17`。
- 官方页面未注明宽度基准，规格记录和页面提示保留了这一点。第三方资料报告了冲突数据，未混入官方值。
- 页面以该规格规划 `1:24`，核心 `23×10 studs`，生成请求含检索 ID、resolved variant 和车辆规格指纹；任务保存独立规格快照。
- 任务 ID：`24599660e50a49968fc324412d08d359`；真实 SD-Turbo、TripoSR、车辆尺寸校准、LEGO 生成和 Studio 导出总计 `91.67 s`。
- LDraw：234 件、27 步；归档回读通过。`.io` SHA-256：`cde91fc2c441633f3de0dd9494a7f4dc52a939276b855ab90eb01642039b1679`。HTTP 下载与本地文件逐字节一致，ZIP 完整性检查通过。
- 新规格下的 Studio GUI、外观交付标准、原生碰撞、机构和实体拼装仍未验收，继续保留 `appearance_accepted=false`、`delivery_accepted=false`、`buildability=unverified`。

页面验证：默认车型点击“搜索规格”得到带来源的尺寸表；已生成结果可下载 Studio `.io` 和本次物理规格。服务重载后恢复这次完成任务。页面筛选并发搜索期间仍只允许一个生成任务。

年款选填回归：HTTP 规格检索与比例规划接口均接受省略年款、空字符串和纯空格，按品牌及车型解析。上述真实 F40 生成请求的 `variant` 同样为空；来源解析出的适用版本单独保存在 `resolved_variant`。
