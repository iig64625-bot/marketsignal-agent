# MarketSignal Agent — Codex 改进执行文档

> **生成时间**：2026-06-23  
> **基于**：对当前 4053 行源码 + 948 行测试的深度审查  
> **现状**：57 测试全通过，核心链路代码完整，但存在 7 类关键缺陷和 5 个缺失模块

---

## 当前状态总结

| 维度 | 状态 | 详情 |
|---|---|---|
| 源码量 | ✅ 4053 行 | 75 个 .py 文件（不含 venv/migrations） |
| 测试量 | ✅ 948 行 / 57 测试 | 全部通过 |
| LangGraph 工作流 | ✅ 完整 | 11 节点全连接，含 sample 快捷路径 |
| 数据模型 | ✅ 完整 | 11 个 ORM 模型 + Pydantic schemas |
| 端到端运行 | ⚠️ sample 模式可跑 | 完整模式需要 API key |
| FastAPI | ❌ 空壳 | `api/deps.py` 和 `api/routes/` 只有 docstring |
| Streamlit UI | ❌ 空壳 | `ui/__init__.py` 只有 docstring |
| `__main__.py` | ❌ 缺失 | `python -m marketsignal` 无法运行 |
| 报告输出 | ⚠️ 有但不够 | 周报/Battlecard 渲染完整，但无 PDF 输出 |
| 错误处理 | ⚠️ 基础级 | 有 try/except 但缺重试、超时、优雅降级 |
| 可观测性 | ❌ 缺失 | 无 structured logging、无 tracing、无 metrics 导出 |

---

## 执行任务（按优先级排序）

### P0 — 必须修复（不修就跑不起来/面不过）

---

#### Task 1: 添加 `__main__.py` 入口

**文件**: `src/marketsignal/__main__.py`

**原因**: `python -m marketsignal run --use-sample-dataset` 当前报错 `No module named marketsignal.__main__`

**要求**:
```python
"""Allow ``python -m marketsignal`` to work."""
from marketsignal.cli import main
import sys
sys.exit(main())
```

**验证**: `python -m marketsignal run --use-sample-dataset` 成功执行

---

#### Task 2: 实现 FastAPI 应用和路由

**文件**: 
- `src/marketsignal/api/app.py` (新建)
- `src/marketsignal/api/deps.py` (重写)
- `src/marketsignal/api/routes/runs.py` (新建)
- `src/marketsignal/api/routes/reports.py` (新建)
- `src/marketsignal/api/routes/health.py` (新建)

**原因**: `api/deps.py` 当前只有一行 docstring，整个 API 层是空壳。面试官会看你的 API 设计。

**要求**:

1. `app.py` — FastAPI 应用工厂:
   - `create_app()` 返回配置好的 FastAPI 实例
   - CORS middleware
   - lifespan 事件（初始化 DB、Chroma）
   - 挂载 routes

2. `deps.py` — 依赖注入:
   - `get_db_session()` — yield SQLAlchemy session
   - `get_vector_store()` — yield Chroma store singleton
   - `get_pipeline()` — yield compiled LangGraph pipeline

3. `routes/health.py`:
   - `GET /health` — 返回 `{"status": "ok", "version": "0.1.0"}`
   - `GET /ready` — 检查 DB + Chroma 连通性

4. `routes/runs.py`:
   - `POST /runs` — 启动新 pipeline run（接受 config YAML body，返回 run_id）
   - `GET /runs/{run_id}` — 查询 run 状态和 metrics
   - `GET /runs` — 列出最近 runs

5. `routes/reports.py`:
   - `GET /reports` — 列出报告（支持 `?report_type=weekly|battlecard` 过滤）
   - `GET /reports/{report_id}` — 返回报告 markdown 内容
   - `GET /reports/{report_id}/download` — 下载报告文件

**验证**: 
- `uvicorn marketsignal.api.app:create_app --factory` 启动不报错
- `curl localhost:8000/health` 返回 200
- 写 `tests/api/test_app.py` 覆盖 health + runs + reports

---

#### Task 3: 实现 Streamlit UI

**文件**:
- `src/marketsignal/ui/app.py` (新建，主页面)
- `src/marketsignal/ui/components/sidebar.py` (新建)
- `src/marketsignal/ui/components/report_viewer.py` (新建)
- `src/marketsignal/ui/components/run_monitor.py` (新建)

**原因**: `ui/__init__.py` 当前只有 docstring。Streamlit 是项目技术栈承诺的前端，面试必问。

**要求**:

1. `app.py` — 主 Streamlit 页面:
   - `st.set_page_config(page_title="MarketSignal Agent")`
   - Sidebar: 选择竞品配置 YAML、选择 run 模式（sample/live）、触发新 run
   - Main area: Tab 1 = 最近周报，Tab 2 = Battlecard，Tab 3 = Eval 指标，Tab 4 = Run 历史
   - 底部: 信号时间线图（用 `st.dataframe` 或 `st.line_chart`）

2. `components/sidebar.py`:
   - 竞品配置选择器
   - Run 模式切换
   - "Run Pipeline" 按钮（调用 `build_pipeline`）

3. `components/report_viewer.py`:
   - 读取 `data/reports/` 下的 markdown 文件
   - 用 `st.markdown()` 渲染
   - 支持下载按钮

4. `components/run_monitor.py`:
   - 显示最近 runs 的状态/时间/metrics
   - 用 `st.dataframe` 展示

**验证**: `streamlit run src/marketsignal/ui/app.py` 启动不报错，能看到页面

---

### P1 — 重要改进（不做会显得项目不完整）

---

#### Task 4: 完善 LLM Provider 支持

**文件**: `src/marketsignal/utils/llm.py`

**原因**: 当前只支持 openai/anthropic/deepseek。缺少：
- Gemini（Google）
- Qwen（通义千问，通过 OpenAI-compatible endpoint）
- Ollama（本地模型，面试展示时省 API 费用）
- 环境变量 `LLM_BASE_URL` 的通用覆盖

**要求**:
1. 添加 `gemini` provider（使用 `langchain-google-genai`）
2. 添加 `qwen` provider（OpenAI-compatible，base_url=`https://dashscope.aliyuncs.com/compatible-mode/v1`）
3. 添加 `ollama` provider（OpenAI-compatible，base_url=`http://localhost:11434/v1`）
4. 添加 `custom` provider：当 `LLM_BASE_URL` 环境变量存在时，使用 `ChatOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)`
5. 在 `settings.py` 中添加对应的环境变量：`GEMINI_API_KEY`, `QWEN_API_KEY`, `OLLAMA_BASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`
6. 在 `.env.example` 中添加这些新变量

**验证**: 
- 单元测试 mock 各 provider 的构造
- `get_llm(provider="ollama", model="llama3")` 不报错

---

#### Task 5: 添加重试和超时机制

**文件**:
- `src/marketsignal/ingestion/http_client.py` (改进)
- `src/marketsignal/utils/retry.py` (新建)

**原因**: 当前 `http_client.py` 有 `http_max_retries` 配置但未实现指数退避重试。网络请求失败时直接抛异常。

**要求**:

1. `utils/retry.py` — 通用重试装饰器:
   ```python
   async def retry_with_backoff(
       fn,
       *,
       max_retries: int = 3,
       base_delay: float = 1.0,
       max_delay: float = 30.0,
       retryable_exceptions: tuple = (httpx.HTTPError, httpx.TimeoutException),
   ):
   ```
   - 指数退避 + jitter
   - 可配置重试异常类型
   - 每次重试 log.warning

2. 改进 `http_client.py`:
   - `fetch()` 方法使用 `retry_with_backoff`
   - 添加 per-request timeout（从 settings 读取）
   - 429 Too Many Requests 时自动等待 `Retry-After` header

3. 改进 `agents/nodes/collect_sources.py`:
   - 单个 source 失败不影响其他 source（当前已有 try/except，但需加 retry）

**验证**: 
- Mock 一个会失败 2 次后成功的 HTTP 请求，验证重试生效
- Mock 429 响应，验证等待后重试

---

#### Task 6: 添加结构化日志和可观测性

**文件**:
- `src/marketsignal/utils/logging.py` (新建)
- `src/marketsignal/utils/tracing.py` (新建)

**原因**: 当前使用 loguru 但没有结构化输出、没有 trace ID、没有 pipeline 运行耗时统计。面试官会问"你怎么知道系统在生产中运行正常？"

**要求**:

1. `utils/logging.py`:
   - 配置 loguru 输出 JSON 格式（方便 ELK/Datadog 消费）
   - 每条日志带 `run_id`、`node_name`、`timestamp`
   - 支持 `LOG_FORMAT=json|text` 环境变量切换

2. `utils/tracing.py`:
   - 简单的 pipeline trace 记录器（不需要 OpenTelemetry 那么重）
   - `PipelineTrace` 类：记录每个 node 的进入/退出时间、输入/输出摘要、错误
   - `trace_node()` 装饰器：自动记录 node 执行耗时
   - trace 结果写入 `data/traces/{run_id}.json`

3. 在每个 agent node 上加 `@trace_node` 装饰器

4. 在 `settings.py` 添加 `trace_enabled: bool = True`

**验证**: 
- 运行 sample pipeline 后检查 `data/traces/` 下生成了 trace JSON
- 验证 JSON 中每个 node 都有 enter/exit 时间和耗时

---

#### Task 7: 完善 Eval 模块

**文件**:
- `src/marketsignal/evals/summary.py` (重写，当前可能是占位)
- `src/marketsignal/evals/eval_runner.py` (新建)

**原因**: 当前 eval 模块有 citation_coverage、dedup_rate、latency、token_cost、unsupported_claims，但缺少：
- 摘要一致性评估（summary faithfulness）
- 信号分类准确率
- 综合评估报告生成
- Eval 结果持久化到 DB

**要求**:

1. `evals/summary.py` — 摘要一致性:
   - 输入：原始文档 + 生成的摘要
   - 使用关键词重叠 + LLM 判断两种方式
   - 返回 `faithfulness_score: float` (0-1)

2. `evals/eval_runner.py` — 综合评估运行器:
   - `run_all_evals(run_id, session)` — 运行所有 eval 指标
   - 返回 `EvalReport` dataclass 包含所有指标
   - 将结果写入 `eval_runs` DB 表
   - 生成 `data/evals/{run_id}.json` 报告

3. 改进 `evals/token_cost.py`:
   - 使用 LangChain callback 追踪 token 用量
   - 记录 per-node token 消耗

4. 改进 `evals/latency.py`:
   - 从 trace JSON 读取各 node 耗时
   - 计算 p50/p95 延迟

**验证**: 
- 运行 sample pipeline 后 `data/evals/` 下有完整 eval 报告
- 验证 eval 报告包含所有指标

---

### P2 — 增强体验（做了加分，不做不扣分）

---

#### Task 8: 添加 PDF 报告输出

**文件**:
- `src/marketsignal/reporting/render_pdf.py` (新建)

**原因**: 当前只有 Markdown 输出。PDF 输出让报告更专业，面试展示时更直观。

**要求**:
1. 使用 `weasyprint` 或 `markdown2` + `pdfkit` 将 Markdown 转 PDF
2. 支持中文字体
3. 在 `settings.py` 添加 `report_formats: str = "markdown,pdf"`
4. 在 `generate_weekly_report_node` 和 `generate_battlecards_node` 中，如果配置包含 pdf，同时生成 PDF

**验证**: 运行 sample pipeline 后 `data/reports/` 下有 `.pdf` 文件

---

#### Task 9: 添加 APScheduler 定时任务支持

**文件**:
- `src/marketsignal/scheduler.py` (新建)

**原因**: 竞品情报系统天然需要定时运行（每日/每周）。当前只能手动触发。

**要求**:
1. 使用 APScheduler 实现:
   - `start_scheduler()` — 启动后台调度器
   - `add_weekly_job(config_path, cron_day="mon", cron_hour=9)` — 添加周报任务
   - `add_daily_job(config_path, cron_hour=8)` — 添加每日监控任务
2. 在 CLI 中添加 `schedule` 子命令:
   - `marketsignal schedule --config xxx --cron "0 9 * * 1"` 
3. 在 FastAPI 中添加 `POST /scheduler/jobs` 端点

**验证**: 
- `marketsignal schedule --config configs/competitors.ai-agent.yaml --cron "*/5 * * * *"` 启动后 5 分钟内自动执行一次 pipeline

---

#### Task 10: 改进 Battlecard 模板

**文件**: `src/marketsignal/reporting/templates.py`

**原因**: 当前 Battlecard 模板较简单，缺少"我方应对话术"和"可攻击点"的 LLM 生成。

**要求**:
1. 在 `generate_battlecards_node` 中增加 LLM 调用:
   - 输入：竞品信号 + 我方产品信息
   - 输出：结构化的应对话术和可攻击点
   - 使用 `BattlecardOutput` schema 做 structured output
2. 在 `render_battlecard()` 中增加两个 section:
   - "Suggested Sales Response" — LLM 生成的销售话术
   - "Attack Points" — LLM 生成的竞品弱点
3. 每个话术/攻击点带 confidence 和 evidence source

**验证**: 
- Sample pipeline 生成的 Battlecard 包含"Sales Response"和"Attack Points" section
- 每个点都有 confidence 标记

---

#### Task 11: 添加数据源健康检查

**文件**:
- `src/marketsignal/ingestion/health_check.py` (新建)

**原因**: 运行 pipeline 前不知道哪些数据源可用。面试官会问"如果某个网站挂了怎么办？"

**要求**:
1. `check_source_health(source: Source) -> SourceHealth`:
   - 发 HEAD 请求检查 URL 可达性
   - 记录响应时间
   - 检查 content-type 是否符合预期
   - GitHub API 检查 rate limit
2. `check_all_sources(config_path) -> list[SourceHealth]`
3. 在 CLI 添加 `marketsignal check-sources --config xxx`
4. 在 Streamlit sidebar 显示数据源状态（绿/红/黄）

**验证**: `marketsignal check-sources --config configs/competitors.ai-agent.yaml` 输出各源状态

---

#### Task 12: 添加 README 中文版和 Demo 截图

**文件**:
- `README_CN.md` (新建)
- `docs/demo_screenshot.md` (新建)

**原因**: 你说中文、投国内岗，中文 README 是必须的。Demo 截图让面试官一眼看到效果。

**要求**:
1. `README_CN.md` — 英文 README 的完整中文翻译，加上:
   - 项目背景和求职定位说明
   - 技术选型理由（为什么 LangGraph 不用 CrewAI？为什么 Chroma 不用 Pinecone？）
   - 面试讲述逻辑（5 步法）
   - 架构图（ASCII 或 Mermaid）

2. `docs/demo_screenshot.md`:
   - Sample pipeline 运行结果截图
   - Streamlit UI 截图
   - 周报和 Battlecard 示例输出

**验证**: `README_CN.md` 内容完整，无占位符

---

### P3 — 锦上添花

---

#### Task 13: 添加 GitHub Actions CI

**文件**: `.github/workflows/ci.yml` (新建)

**要求**:
1. On push/PR to main: run pytest + ruff check + mypy
2. Python 3.10 / 3.11 matrix
3. Cache .venv
4. Sample pipeline smoke test

---

#### Task 14: 添加 Docker Compose 开发环境

**文件**: `docker-compose.yml` (改进)

**要求**:
1. `marketsignal-api` service（FastAPI）
2. `marketsignal-ui` service（Streamlit）  
3. `marketsignal-scheduler` service（APScheduler）
4. 共享 volume `./data`
5. `.env` 文件注入

---

#### Task 15: 添加 Alembic 迁移文档和 DB 初始化脚本

**文件**:
- `scripts/init_db.py` (新建)
- `docs/database.md` (新建)

**要求**:
1. `init_db.py` — 创建所有表 + 插入 sample 数据
2. `docs/database.md` — ER 图 + 表说明 + 迁移指南

---

## 执行顺序建议

```
第一批（让项目能跑+能看）:
  Task 1 → Task 2 → Task 3

第二批（让项目健壮）:
  Task 5 → Task 6 → Task 4

第三批（让项目完整）:
  Task 7 → Task 10 → Task 11

第四批（让项目专业）:
  Task 8 → Task 9 → Task 12 → Task 13 → Task 14 → Task 15
```

---

## 代码规范（Codex 必须遵守）

1. **所有新文件必须有 module docstring**
2. **所有 public 函数必须有 type hints 和 docstring**
3. **错误处理用 loguru + 具体异常类型，不用 bare except**
4. **测试覆盖每个新函数的 happy path + 至少 1 个 error path**
5. **不引入新依赖除非在 pyproject.toml 的 [project.optional-dependencies] 中声明**
6. **异步函数用 `async def`，不用 `asyncio.run()` 嵌套**
7. **配置从 Settings 读取，不硬编码**
8. **ID 生成用 `models.base.new_id()`，不自己造**
9. **DB 操作用 `get_session()` context manager，不裸创建 session**
10. **LLM 调用用 `utils.llm.get_llm()`，不直接 import ChatOpenAI**

---

## 验证清单（每个 Task 完成后跑）

```bash
# 1. 代码质量
.venv/Scripts/python.exe -m ruff check src/ tests/

# 2. 测试
.venv/Scripts/python.exe -m pytest tests/ -x -v

# 3. Sample pipeline 端到端
.venv/Scripts/python.exe -m marketsignal run --use-sample-dataset

# 4. FastAPI 启动
.venv/Scripts/python.exe -m uvicorn marketsignal.api.app:create_app --factory --port 8000

# 5. Streamlit 启动
streamlit run src/marketsignal/ui/app.py
```
