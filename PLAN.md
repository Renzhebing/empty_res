# P01_fapiao_helper 实施计划

> 本文件是计划阶段产出的最终方案，留档备查。实施过程中如需改动请同步更新本文件 + `memory.md` 决策记录。

## 1. Summary
本地优先的发票识别整理工具：Flask + 原生 HTML/JS 前端 + Python 后端，PaddleOCR + 正则做主识别，多供应商云端 LLM（OpenAI 兼容为主）兜底；SQLite 存元数据，发票原件按 `YYYY-MM/项目/` 物理归类；`CHANGELOG.md` + `memory.md` 双轨日志用于跨工具/跨机器续接；v1 覆盖导入→识别→分类→状态→XLSX 导出→PDF 合并打印的闭环，并附带 `/debug` 页和前端实时金额合计。

## 2. 目录与模块
```
P01_fapiao_helper/
├── start.bat / start.sh            # 双击启动，自动开浏览器到 http://127.0.0.1:5000
├── requirements.txt                # 依赖锁定（paddleocr, paddlepaddle, openpyxl, watchdog, pyyaml, reportlab, openai）
├── .gitignore                      # 忽略 config.yaml / invoices/ / data/ / .venv/ / __pycache__/
├── README.md                       # 用户使用说明（启动 / 配置 / 上传 / 导出）
├── CHANGELOG.md                    # 手动维护的代码变更日志（按版本/日期）
├── Agent.markdown                  # 三大节：通用原则 / 项目架构 / 接口约定
├── memory.md                       # 跨工具会话状态：项目状态 / 近期决策 / 开放问题
├── PLAN.md                         # 本文件
├── config.default.yaml             # 脱敏示例（提交）
├── config.yaml                     # 真实配置（含 api_key，被 gitignore）
├── invoices/                       # 发票原件库（gitignore）
│   ├── inbox/                      # 拖入暂存
│   ├── library/YYYY-MM/项目/       # 整理后
│   └── exports/                    # XLSX / 合并 PDF
├── data/
│   ├── fapiao.db                   # SQLite
│   ├── models/                     # PaddleOCR 模型缓存（首次启动下载）
│   └── logs/YYYY-MM-DD.log         # 每日运行日志
├── fapiao_helper/                  # 主包
│   ├── __main__.py                 # python -m fapiao_helper 入口
│   ├── app.py / config.py / db.py / paths.py / logging_setup.py
│   ├── ocr/        engine.py / preprocess.py
│   ├── parser/     vat_invoice.py / classify.py / llm_fallback.py
│   ├── llm/        base.py / openai_compat.py / router.py
│   ├── jobs/       manager.py / worker.py
│   ├── library/    organizer.py / watcher.py
│   ├── export/     xlsx.py / pdf_merge.py / cover.py
│   └── web/        routes/(api_invoices, api_jobs, api_export, api_projects, debug) / static/ / templates/
└── tests/        test_parser_vat.py / test_classify.py / test_db.py / test_export_xlsx.py / test_pdf_merge.py
```

## 3. 关键实现
- **配置加载**：`config.py` 读 `config.yaml`（无则从 `config.default.yaml` 复制提示用户）；YAML 含 `server.port`、`paths.{inbox,library,exports,db,logs}`、`projects[].name`、`llm.providers[].{name,base_url,api_key,model,vision}`、`ocr.lang`。`paths.py` 把相对路径解析为相对项目根的绝对路径。
- **OCR**：`ocr/engine.py` 懒加载 PaddleOCR（中文 v4 模型），首次启动下载到 `data/models/` 并支持手工放置离线模型。`preprocess.py` 负责 PDF 渲染（PyMuPDF）、图像旋转矫正、二值化。识别结果统一为 `[(box, text, conf), ...]`。
- **字段解析**：`parser/vat_invoice.py` 用关键词锚点定位（"发票号码"、"开票日期"、"购买方"、"销售方"、"价税合计"、"货物或应税劳务名称"）+ 正则提取金额/日期/税号；输出字段：`invoice_no, invoice_date, buyer, seller, buyer_tax_id, seller_tax_id, amount, tax, total, items[]`，并带 `confidence`。
- **分类**：`parser/classify.py` 维护 4 类关键词表（餐饮住宿 / 交通 / 办公用品 / 其他），按 `items[].name` + `seller` 加权打分，取最高且 ≥ 阈值的结果，否则归 `其他`。
- **LLM 兜底**：`llm/openai_compat.py` 复用 OpenAI SDK（DeepSeek/OpenRouter/Qwen/Doubao 等 OpenAI 兼容端点都用它）；`llm/router.py` 根据 `provider.vision=true` 自动把图像/PDF 转 base64 走 `chat.completions` vision 接口；输出 JSON Schema，缺失字段不阻塞入库（仅标记 `needs_review=true` 并写入 `run_logs`）。
- **Job 管理**：`jobs/manager.py` 维护内存 job 表并镜像到 `jobs`/`job_items` SQLite 表（崩溃后启动时恢复 pending 项）；后台线程池消费；`POST /api/jobs` 返回 `job_id`，前端 `/api/jobs/<id>` 每 1.5s 轮询；每项完成后调用 `library/organizer.py` 把原件复制到 `library/YYYY-MM/项目/<原文件名>` 并写 `invoices`。
- **文件夹监控**：`library/watcher.py` 用 `watchdog`（可选依赖，缺失则降级为启动时扫描）监听 `inbox/`，新文件入队到 job 队列，与前端拖入共用同一队列。
- **导出**：`export/xlsx.py`（openpyxl）生成 4 个 Sheet：汇总（按筛选条件）/ 按项目 / 按类型 / 明细，每 Sheet 末尾加合计行；`export/pdf_merge.py`（PyMuPDF）+ `export/cover.py`（reportlab）按当前勾选顺序合并 PDF 并在头部插入封面（生成日期、筛选条件、合计金额、明细列表）；图片格式发票在合并前用 PyMuPDF 转单页 PDF。
- **前端**：单页 + 4 个 Tab（导入 / 库 / 导出 / 调试）。导入 Tab：拖拽区 + 文件夹选择 + 已选文件列表 + 项目预选。库 Tab：可编辑表格（项目下拉、类型下拉、状态徽章点击切换、日期/金额直接改），筛选栏（状态/项目/月份/关键词），右栏实时金额合计（按当前筛选）。导出 Tab：勾选 + XLSX/PDF 按钮。调试 Tab：展示原图、OCR 原文、解析字段、可手动触发 LLM 兜底。
- **双日志**：
  - `CHANGELOG.md`：每次重大改动追加一段（日期、版本、变更点、原因），纯人维护。
  - `memory.md` 三节固定结构：`## 项目状态`（当前进度 + 下一步）、`## 近期决策`（含日期和理由，按时间倒序）、`## 开放问题`（待办/未决）。每次会话结束或关键决策后追加。
  - 运行日志同时落 `run_logs` 表和 `data/logs/YYYY-MM-DD.log`，便于 SQL 查询和文本查看。
- **`.gitignore`**：`config.yaml`、`invoices/`、`data/fapiao.db`、`data/models/`、`data/logs/`、`.venv/`、`__pycache__/`、`.idea/`、`.vscode/`。

## 4. 数据契约
**SQLite 表**（`data/fapiao.db`）：
- `invoices(id PK, sha256 UNIQUE, src_path, stored_path, invoice_no, invoice_date, buyer, seller, buyer_tax_id, seller_tax_id, amount, tax, total, category, project, status, needs_review BOOL, recognized_at, updated_at, confidence, raw_json TEXT)`；索引 `(status, project)`、`(invoice_date)`、`(sha256)`。
- `jobs(id PK, kind, status, total, done, failed, error, created_at, updated_at)`
- `job_items(job_id FK, invoice_id FK, status, error, PRIMARY KEY(job_id, invoice_id))`
- `run_logs(id PK, ts, level, scope, msg, ctx_json)`
- `projects(name PK, note, created_at)`（与 config 同步，运行期可增删）

**HTTP API**：
- `POST /api/invoices/upload`（multipart：files[] + folder + default_project）
- `GET /api/invoices?status=&project=&month=&q=&page=`、`GET /api/invoices/<id>`、`PATCH /api/invoices/<id>`、`POST /api/invoices/<id>/status`
- `POST /api/jobs`、`GET /api/jobs/<id>`、`GET /api/jobs?status=`
- `POST /api/export/xlsx`（body：filter + selected_ids）→ 返回文件
- `POST /api/export/pdf-merge`（body：selected_ids + cover_meta）→ 返回文件
- `GET /api/projects`、`POST /api/projects`、`DELETE /api/projects/<name>`
- `GET /api/stats?project=&month=`（用于跨表实时合计的兜底/校验）
- `GET /debug/invoice/<id>`、`POST /api/invoices/<id>/re-recognize`（手动触发 LLM 兜底）

## 5. 测试计划（pytest）
- `test_parser_vat.py`：用文本 fixture 验证金额/日期/购销方/税号的正则；含字段缺失、乱序、多行价税合计等负样本。
- `test_classify.py`：4 类典型 `items[].name` 验证分类；多类关键词同时命中时的优先级；阈值边界。
- `test_db.py`：schema 初始化、增删改查、唯一索引约束（重复 sha256）、并发写入（多线程同库）。
- `test_export_xlsx.py`：多 Sheet 生成、空筛选结果保护、合计列精度。
- `test_pdf_merge.py`：合并多 PDF + 图片转 PDF + 封面页存在 + 页数 = 单文件页数之和 + 1。
- `test_config.py`：缺字段时的默认值和错误提示。
- 不测：UI 交互、OCR 端到端（需 PaddleOCR 完整环境）、LLM 兜底（需密钥，单测走 mock）。

## 6. v1 范围与假设
**v1 包含**：拖拽上传 + inbox 监控、PaddleOCR + 正则解析、4 类分类、人工编辑、状态流转、XLSX 多 Sheet 导出、PDF 合并 + 封面、前端实时合计、`/debug` 页、CHANGELOG/memory/Agent 三文档骨架、start 脚本、`.gitignore`、核心单测。

**v1 不做（v2+）**：报销单号与报销人字段、报销流程审批、邮件/微信导入、多人协作、统计图表、报表模板、UI 主题切换、自动更新。

**默认值与约定**：
- 端口 5000；首次启动自动创建 `invoices/{inbox,library,exports}`、`data/{logs,models}`。
- PaddleOCR 模型首次联网下载约 200MB，之后离线可用；完全离线时用户手工把模型放到 `data/models/`。
- 云端 LLM 默认关闭；只在 `config.yaml` 显式填写 `api_key` 才启用；调用失败不阻塞入库。
- `Agent.markdown` v1 写入三节骨架和首批通用原则（中文优先、密钥隔离、本地优先、最小依赖等）。
- `memory.md` 由实现者在每次关键决策/会话结束时手工追加；初始内容含 v1 目标、技术栈摘要、首批决策。
- 文件名安全：原件复制时若重名自动追加 `_2`、`_3` 后缀，不覆盖。
- 金额字段统一 `DECIMAL(12,2)`，合计列前端 `toFixed(2)`。
