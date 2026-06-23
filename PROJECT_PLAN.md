# MarketSignal Agent — 开发计划

> 本文档供 Codex 逐条执行。每个 Task 包含：目标、要创建/修改的文件、具体代码要求、验收标准。
> 依赖关系按 Phase → Task 编号严格排序，Codex 必须按顺序执行。

---

## 项目现状

已完成（骨架阶段）：

- 目录结构已创建（`src/marketsignal/` 下 15 个模块子目录 + `__init__.py`）
- `pyproject.toml`（依赖声明、`marketsignal` CLI 入口）
- `.env.example`（环境变量模板）
- `.gitignore`、`Makefile`、`alembic.ini`
- `configs/competitors.ai-agent.yaml`（竞品配置）
- `migrations/env.py`、`migrations/script.py.mako`
- `src/marketsignal/cli.py`（CLI 骨架，`run` 子命令只有 TODO）
- `src/marketsignal/config/settings.py`（pydantic-settings 加载）
- `tests/conftest.py`（tmp_data_dir fixture）
- `docs/` 下 7 个占位 Markdown
- `README.md`

未完成（本计划要落实）：

- 所有业务逻辑代码
- 数据库 ORM 模型 + 迁移
- LangGraph Agent 工作流
- 抓取 / 清洗 / 事件抽取 / 信号分析 / 报告生成 / 引用校验 / Eval
- FastAPI 路由
- Streamlit UI
- 测试
- 示例输出与文档完善

---

## 约定

1. **所有 Python 代码**放在 `src/marketsignal/` 下，包名 `marketsignal`。
2. **数据模型**统一用 SQLAlchemy 2.0 declarative，所有表放在 `src/marketsignal/models/` 下。
3. **Pydantic schema**（API 请求/响应、事件结构、信号结构）放在 `src/marketsignal/models/schemas.py`。
4. **LLM 调用**统一走 `src/marketsignal/utils/llm.py` 封装，provider 由 `settings.llm_provider` 决定，不直接在各模块里 import langchain。
5. **日志**统一用 `loguru`，不在任何模块里 `import logging`。
6. **ID 生成**统一用 `uuid.uuid4().hex[:12]`，生成 12 位 hex 字符串作为主键。
7. **时间**统一用 UTC，`datetime.utcnow()` 或 `datetime.now(timezone.utc)`。
8. **配置加载**统一通过 `from marketsignal.config.settings import get_settings`。
9. **YAML 配置解析**统一走 `src/marketsignal/config/loader.py`。
10. **测试**每个 Phase 完成后必须写基础测试，确保 `pytest` 能通过。
11. **类型注解**所有公开函数必须有参数和返回值类型注解。
12. **docstring**所有模块、类、公开函数必须有 docstring。

---

## Phase 1：数据层（ORM 模型 + 迁移 + 配置加载）

**目标**：让数据库能跑起来，所有表可创建，YAML 配置可解析。

---

### Task 1.1：创建 ORM 基础设施

**文件**：
- `src/marketsignal/db/engine.py`
- `src/marketsignal/db/session.py`

**要求**：

`engine.py`：
```python
"""Database engine factory."""
from sqlalchemy import create_engine
from marketsignal.config.settings import get_settings

def get_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        echo=settings.app_env == "development",
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    )
```

`session.py`：
```python
"""Database session factory."""
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, Session
from marketsignal.db.engine import get_engine

_SessionFactory = None

def _get_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory

@contextmanager
def get_session() -> Session:
    """Yield a database session; auto-commit on success, rollback on exception."""
    factory = _get_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

**验收**：`from marketsignal.db.session import get_session` 不报错。

---

### Task 1.2：创建 ORM 模型

**文件**：
- `src/marketsignal/models/base.py`
- `src/marketsignal/models/company.py`
- `src/marketsignal/models/source.py`
- `src/marketsignal/models/crawl_run.py`
- `src/marketsignal/models/raw_document.py`
- `src/marketsignal/models/normalized_document.py`
- `src/marketsignal/models/document_chunk.py`
- `src/marketsignal/models/event.py`
- `src/marketsignal/models/signal.py`
- `src/marketsignal/models/report.py`
- `src/marketsignal/models/claim.py`
- `src/marketsignal/models/citation.py`
- `src/marketsignal/models/eval_run.py`
- `src/marketsignal/models/__init__.py`（re-export 所有模型）

**要求**：

`base.py`：
```python
"""SQLAlchemy declarative base."""
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
```

每个模型文件示例（以 `company.py` 为模板，其余表照此风格）：

```python
"""Company ORM model."""
import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from marketsignal.models.base import Base, TimestampMixin

class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "target" | "competitor"
    website: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
```

各表字段严格按照 README 和蓝图中的数据库设计：

- **companies**: id, name, role, website, description, created_at
- **sources**: id, company_id(FK→companies), source_type, name, url, is_enabled, fetch_strategy, created_at
- **crawl_runs**: id, started_at, finished_at, status, triggered_by, time_window_start, time_window_end, error_message
- **raw_documents**: id, crawl_run_id(FK→crawl_runs), source_id(FK→sources), url, http_status, fetched_at, content_type, raw_html_path, raw_text_path, checksum
- **normalized_documents**: id, raw_document_id(FK→raw_documents), company_id(FK→companies), source_type, title, clean_text, language, published_at, canonical_url, content_hash, dedup_group, category, created_at
- **document_chunks**: id, document_id(FK→normalized_documents), chunk_index, chunk_text, token_count, embedding_id, metadata_json
- **events**: id, document_id(FK→normalized_documents), company_id(FK→companies), event_type, title, summary, published_at, confidence, evidence_json, created_at
- **signals**: id, crawl_run_id(FK→crawl_runs), company_id(FK→companies), signal_type, finding, analysis, recommendation, confidence, supporting_event_ids_json, supporting_document_ids_json, created_at
- **reports**: id, crawl_run_id(FK→crawl_runs), report_type, company_id(FK→companies), title, markdown_path, json_path, created_at
- **claims**: id, report_id(FK→reports), claim_text, claim_type, confidence, is_supported, supporting_citation_ids_json, created_at
- **citations**: id, report_id(FK→reports), claim_id(FK→claims), document_id(FK→normalized_documents), url, snippet, created_at
- **eval_runs**: id, crawl_run_id(FK→crawl_runs), citation_coverage, unsupported_claim_rate, dedup_rate, avg_latency_ms, token_cost_usd, summary_json, created_at

`__init__.py` 必须把所有模型类 re-export，以便 Alembic `env.py` 的 `target_metadata` 能扫描到：
```python
from marketsignal.models.company import Company
from marketsignal.models.source import Source
# ... 所有模型
from marketsignal.models.base import Base

__all__ = [
    "Company", "Source", "CrawlRun", "RawDocument", "NormalizedDocument",
    "DocumentChunk", "Event", "Signal", "Report", "Claim", "Citation",
    "EvalRun", "Base",
]
```

**验收**：`from marketsignal.models import Base, Company, Source` 不报错。

---

### Task 1.3：连接 Alembic 和 ORM

**文件**：修改 `migrations/env.py`

**要求**：

把 `target_metadata = None` 替换为：
```python
from marketsignal.models import Base
target_metadata = Base.metadata
```

然后在项目根目录执行 `alembic revision --autogenerate -m "initial_schema"` 和 `alembic upgrade head`。

**验收**：`data/marketsignal.db` 文件生成，所有 12 张表存在。

---

### Task 1.4：YAML 配置加载器

**文件**：`src/marketsignal/config/loader.py`

**要求**：

```python
"""Load competitor configuration from YAML files."""
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import yaml


@dataclass
class SourceConfig:
    type: str
    url: str


@dataclass
class CompetitorConfig:
    name: str
    website: str
    sources: list[SourceConfig] = field(default_factory=list)


@dataclass
class TargetConfig:
    name: str
    website: str
    description: str = ""


@dataclass
class PipelineConfig:
    target: TargetConfig
    competitors: list[CompetitorConfig]
    monitoring_dimensions: list[str]
    time_window_days: int = 7
    use_sample_dataset: bool = False
    generate_weekly_report: bool = True
    generate_battlecards: bool = True
    run_evals: bool = True


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    """Parse a competitor YAML config into a PipelineConfig dataclass."""
    with open(path, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    target = TargetConfig(
        name=raw["target_company"]["name"],
        website=raw["target_company"]["website"],
        description=raw["target_company"].get("description", ""),
    )

    competitors = []
    for c in raw.get("competitors", []):
        sources = [SourceConfig(type=s["type"], url=s["url"]) for s in c.get("sources", [])]
        competitors.append(CompetitorConfig(name=c["name"], website=c["website"], sources=sources))

    opts = raw.get("run_options", {})

    return PipelineConfig(
        target=target,
        competitors=competitors,
        monitoring_dimensions=raw.get("monitoring_dimensions", []),
        time_window_days=opts.get("time_window_days", 7),
        use_sample_dataset=opts.get("use_sample_dataset", False),
        generate_weekly_report=opts.get("generate_weekly_report", True),
        generate_battlecards=opts.get("generate_battlecards", True),
        run_evals=opts.get("run_evals", True),
    )
```

**验收**：`from marketsignal.config.loader import load_pipeline_config; cfg = load_pipeline_config("configs/competitors.ai-agent.yaml")` 能正常解析。

---

### Task 1.5：Phase 1 测试

**文件**：
- `tests/models/test_models.py`
- `tests/config/test_loader.py`

**要求**：

`test_models.py`：创建所有表 → 插入一条 Company → 查询 → 断言 name 正确。

`test_loader.py`：`load_pipeline_config("configs/competitors.ai-agent.yaml")` → 断言 target.name == "Dify"，competitors 有 2 个。

**验收**：`pytest tests/ -k "test_models or test_loader"` 全绿。

---

## Phase 2：数据采集层（Ingestion）

**目标**：能从配置的数据源抓取公开页面，存入 `raw_documents` 和 `normalized_documents`。

---

### Task 2.1：HTTP 客户端封装

**文件**：`src/marketsignal/ingestion/http_client.py`

**要求**：

- 基于 `httpx.AsyncClient` 封装
- 从 `settings` 读取 `http_timeout`、`http_max_retries`、`http_rate_limit_per_sec`、`user_agent`
- 用 `tenacity` 做重试（最多 3 次，exponential backoff）
- 用 `asyncio.Semaphore` 做限速
- 提供 `async def fetch(url: str) -> httpx.Response` 方法
- 超时或失败时 loguru 记录 warning 并抛出自定义 `FetchError`

**验收**：写一个测试 mock httpx，验证重试逻辑。

---

### Task 2.2：网页抓取器

**文件**：
- `src/marketsignal/ingestion/fetch_webpage.py`
- `src/marketsignal/ingestion/fetch_rss.py`
- `src/marketsignal/ingestion/fetch_github.py`

**要求**：

`fetch_webpage.py`：
- `async def fetch_webpage(url: str, source_id: str, crawl_run_id: str) -> RawDocument`
- 调用 `http_client.fetch(url)`
- 保存原始 HTML 到 `data/raw/<crawl_run_id>/<source_id>_<timestamp>.html`
- 返回 `RawDocument` ORM 对象（不含正文，正文存文件）

`fetch_rss.py`：
- `async def fetch_rss(url: str, source_id: str, crawl_run_id: str) -> list[RawDocument]`
- 用 `feedparser` 解析 RSS
- 每条 entry 保存为单独 `RawDocument`

`fetch_github.py`：
- `async def fetch_github_releases(repo_url: str, source_id: str, crawl_run_id: str) -> list[RawDocument]`
- 从 repo_url 提取 owner/repo
- 用 `httpx` 调用 GitHub API `GET /repos/{owner}/{repo}/releases`
- 每条 release 保存为 `RawDocument`，raw_text_path 存 JSON

**验收**：对每个 fetcher 写测试，mock HTTP 返回，验证 RawDocument 字段。

---

### Task 2.3：正文提取与清洗

**文件**：
- `src/marketsignal/normalization/html_cleaner.py`
- `src/marketsignal/normalization/content_extractor.py`
- `src/marketsignal/normalization/deduper.py`

**要求**：

`html_cleaner.py`：
- `def clean_html(html: str) -> str`
- 用 `trafilatura` 提取正文，fallback 到 `readability-lxml`
- 去掉 script/style/nav/footer
- 返回纯文本

`content_extractor.py`：
- `def extract_content(raw_doc: RawDocument) -> NormalizedDocument`
- 读取 raw_doc 的 raw_html_path 或 raw_text_path
- 调用 `clean_html`
- 用 `hashlib.sha256` 算 content_hash
- 用 `langdetect` 识别语言
- 尝试解析 `published_at`（从 HTML meta / RSS entry / GitHub release published_at）
- 分类 category：先用简单规则（source_type 映射），后续可加 LLM

`deduper.py`：
- `def deduplicate(docs: list[NormalizedDocument]) -> list[NormalizedDocument]`
- 对相同 company_id + content_hash 的文档标记 dedup_group
- 只保留最新的一条

**验收**：测试用一段真实 HTML 验证 clean → extract → dedup 流程。

---

### Task 2.4：采集路由器

**文件**：`src/marketsignal/ingestion/router.py`

**要求**：

```python
"""Route source types to the correct fetcher."""
from marketsignal.models.source import Source

async def fetch_source(source: Source, crawl_run_id: str) -> list[RawDocument]:
    if source.source_type in ("website", "blog", "changelog", "docs", "jobs", "pricing"):
        return [await fetch_webpage(source.url, source.id, crawl_run_id)]
    elif source.source_type == "github":
        return await fetch_github_releases(source.url, source.id, crawl_run_id)
    elif source.source_type == "rss":
        return await fetch_rss(source.url, source.id, crawl_run_id)
    else:
        logger.warning("Unknown source_type={}, skipping", source.source_type)
        return []
```

**验收**：测试验证路由分发正确。

---

### Task 2.5：Phase 2 测试

**文件**：
- `tests/ingestion/test_http_client.py`
- `tests/ingestion/test_fetch_webpage.py`
- `tests/ingestion/test_fetch_rss.py`
- `tests/ingestion/test_fetch_github.py`
- `tests/normalization/test_html_cleaner.py`
- `tests/normalization/test_content_extractor.py`
- `tests/normalization/test_deduper.py`

**要求**：每个测试 mock 外部依赖，不依赖真实网络请求。

**验收**：`pytest tests/ingestion tests/normalization` 全绿。

---

## Phase 3：事件抽取与 RAG

**目标**：从清洗后的文档中抽取结构化事件，写入向量库。

---

### Task 3.1：LLM 调用封装

**文件**：`src/marketsignal/utils/llm.py`

**要求**：

```python
"""Unified LLM call wrapper — provider-agnostic."""
from marketsignal.config.settings import get_settings, Settings
from langchain_core.language_models import BaseChatModel

def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """Return a ChatModel based on settings.llm_provider."""
    settings = get_settings()
    provider = settings.llm_provider

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            temperature=temperature,
            api_key=settings.anthropic_api_key,
        )
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=temperature,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
```

**验收**：`from marketsignal.utils.llm import get_llm; llm = get_llm()` 不报错。

---

### Task 3.2：Pydantic Schema 定义

**文件**：`src/marketsignal/models/schemas.py`

**要求**：

定义以下 Pydantic v2 模型：

```python
class EventOutput(BaseModel):
    """LLM 输出的结构化事件。"""
    event_type: str  # product_update | github_release | pricing_change | hiring_change | ...
    title: str
    summary: str
    published_at: str | None = None
    confidence: float = 0.8  # 0-1
    evidence_spans: list[str] = Field(default_factory=list)

class SignalOutput(BaseModel):
    """LLM 输出的市场信号。"""
    signal_type: str
    finding: str  # 事实
    analysis: str  # 分析
    recommendation: str  # 建议
    confidence: str  # "high" | "medium" | "low"
    supporting_event_ids: list[str] = Field(default_factory=list)

class WeeklyReportSection(BaseModel):
    """周报一个 section。"""
    section_title: str
    items: list[dict[str, str]]  # 每个item至少含 finding / analysis / recommendation / confidence / source

class BattlecardSection(BaseModel):
    """Battlecard 一个 section。"""
    section_title: str
    items: list[str]

class CitationCheckResult(BaseModel):
    """引用校验结果。"""
    claim_text: str
    claim_type: str  # "fact" | "analysis" | "recommendation"
    is_supported: bool
    supporting_urls: list[str] = Field(default_factory=list)
```

**验收**：`from marketsignal.models.schemas import EventOutput, SignalOutput` 不报错。

---

### Task 3.3：事件抽取

**文件**：`src/marketsignal/events/extractor.py`

**要求**：

- `async def extract_events(doc: NormalizedDocument) -> list[Event]`
- 用 LLM + `EventOutput` 结构化输出从 `doc.clean_text` 中抽取事件
- Prompt 要点：
  - 你是一个竞品情报分析师
  - 从以下文本中抽取所有产品更新、定价变化、招聘变化、用户反馈、合作等事件
  - 每个事件必须包含 evidence_spans（原文中支持该事件的原文片段）
  - 如果没有事件，返回空列表
  - 不要编造信息
- 把 `EventOutput` 转成 `Event` ORM 对象
- `evidence_json` 存 `evidence_spans` 的 JSON
- `document_id` = `doc.id`
- `company_id` = `doc.company_id`

**验收**：写测试 mock LLM 返回，验证 Event 字段完整。

---

### Task 3.4：RAG 索引

**文件**：
- `src/marketsignal/rag/chunker.py`
- `src/marketsignal/rag/embedder.py`
- `src/marketsignal/rag/vector_store.py`
- `src/marketsignal/rag/retriever.py`

**要求**：

`chunker.py`：
- `def chunk_document(doc: NormalizedDocument, max_tokens: int = 500, overlap: int = 50) -> list[DocumentChunk]`
- 用 `tiktoken` 计算 token 数
- 滑窗切分，overlap 50 tokens
- 每个 chunk 的 `metadata_json` 包含 `company`、`source_type`、`url`、`published_at`、`document_id`

`embedder.py`：
- `def get_embedding_model()`：返回 `langchain_openai.OpenAIEmbeddings`
- model 从 `settings.embedding_model` 读取

`vector_store.py`：
- `class MarketSignalVectorStore`
- `__init__`：初始化 Chroma，persist_directory 从 `settings.chroma_persist_dir` 读取
- `add_chunks(chunks: list[DocumentChunk])`：把 chunk 文本和 metadata upsert 到 Chroma
- `search(query: str, n: int = 5, filter_company: str | None = None) -> list[dict]`

`retriever.py`：
- `def retrieve_evidence(query: str, company: str | None = None, n: int = 5) -> list[dict]`
- 调用 `vector_store.search`

**验收**：用几段测试文本验证 chunk → embed → search 流程。

---

### Task 3.5：Phase 3 测试

**文件**：
- `tests/events/test_extractor.py`
- `tests/rag/test_chunker.py`
- `tests/rag/test_vector_store.py`

**验收**：`pytest tests/events tests/rag` 全绿。

---

## Phase 4：LangGraph Agent 工作流

**目标**：把前面的模块串成完整的 Agent pipeline。

---

### Task 4.1：定义 Graph State

**文件**：修改 `src/marketsignal/agents/state.py`

**要求**：

```python
"""LangGraph state definitions."""
from typing import TypedDict

class GraphState(TypedDict, total=False):
    run_id: str
    target_company: str
    competitor_ids: list[str]
    source_ids: list[str]
    time_window_start: str
    time_window_end: str

    raw_document_ids: list[str]
    normalized_document_ids: list[str]
    event_ids: list[str]
    signal_ids: list[str]
    report_ids: list[str]

    warnings: list[str]
    metrics: dict[str, float]
    status: str
```

**验收**：`from marketsignal.agents.state import GraphState` 不报错。

---

### Task 4.2：实现 Agent 节点

**文件**（每个文件一个节点函数）：
- `src/marketsignal/agents/nodes/load_config.py`
- `src/marketsignal/agents/nodes/collect_sources.py`
- `src/marketsignal/agents/nodes/normalize_documents.py`
- `src/marketsignal/agents/nodes/extract_events.py`
- `src/marketsignal/agents/nodes/index_documents.py`
- `src/marketsignal/agents/nodes/analyze_signals.py`
- `src/marketsignal/agents/nodes/generate_weekly_report.py`
- `src/marketsignal/agents/nodes/generate_battlecards.py`
- `src/marketsignal/agents/nodes/check_citations.py`
- `src/marketsignal/agents/nodes/run_evals.py`
- `src/marketsignal/agents/nodes/finalize.py`

**要求**：

每个节点的签名统一为：
```python
async def node_name(state: GraphState) -> GraphState:
    ...
```

`load_config.py`：
- 读取 YAML 配置
- 创建 CrawlRun 记录
- 创建/更新 Company 和 Source 记录
- 填充 state 中的 run_id、target_company、competitor_ids、source_ids

`collect_sources.py`：
- 对每个 source_id 调用 `router.fetch_source`
- 保存 RawDocument 到数据库
- 填充 state.raw_document_ids
- 单个 source 失败不中断，追加 warning

`normalize_documents.py`：
- 对每个 raw_document_id 调用 `content_extractor.extract_content`
- 调用 `deduper.deduplicate`
- 保存 NormalizedDocument 到数据库
- 填充 state.normalized_document_ids

`extract_events.py`：
- 对每个 normalized_document 调用 `events.extractor.extract_events`
- 保存 Event 到数据库
- 填充 state.event_ids

`index_documents.py`：
- 对每个 normalized_document 调用 `rag.chunker.chunk_document`
- 调用 `rag.vector_store.add_chunks`
- 记录 chunk 数到 state.metrics

`analyze_signals.py`：
- 从数据库读取本次 run 的所有 events
- 按 company_id 分组
- 对每组 events 用 LLM + `SignalOutput` 生成市场信号
- Prompt 要点：
  - 你是市场分析师
  - 基于以下事件，识别市场信号
  - 每个信号必须包含：事实(finding)、分析(analysis)、建议(recommendation)、置信度(confidence)
  - 每个信号必须引用 supporting_event_ids
  - 不要编造事件中没有的信息
  - 区分事实和推测：事实来自事件原文，推测必须标记为 medium/low confidence
- 保存 Signal 到数据库
- 填充 state.signal_ids

`generate_weekly_report.py`：
- 从数据库读取本次 run 的所有 signals
- 用 LLM 生成周报
- Prompt 要点：
  - 基于以下市场信号，生成竞品周报
  - 报告必须包含以下 section：Executive Summary / Key Changes / Product Signals / Hiring & GTM Signals / Recommendations / Citations
  - 每条关键结论必须标注来源编号 [1][2]...
  - 末尾列出完整来源 URL
  - 区分 fact / analysis / recommendation
- 用 `reporting.render_markdown` 渲染
- 保存 Report 到数据库 + 写文件到 `data/reports/`
- 填充 state.report_ids

`generate_battlecards.py`：
- 从数据库读取每个竞品的 signals
- 对每个竞品用 LLM 生成 Battlecard
- Prompt 要点：
  - 基于以下信号，生成该竞品的销售 Battlecard
  - 必须包含：Positioning / Key Strengths / Recent Moves / Risks & Weaknesses / Suggested Sales Response / Evidence Sources
  - 每条弱点或攻击点必须有证据来源
- 保存 Report（report_type="battlecard"）到数据库
- 追加到 state.report_ids

`check_citations.py`：
- 从数据库读取本次 run 的所有 reports
- 抽取报告中的 claims
- 对每个 claim：检查是否有对应的 NormalizedDocument 作为证据
- 用 LLM + `CitationCheckResult` 判断 claim 是否有支撑
- 保存 Claim 和 Citation 到数据库
- 计算 citation_coverage 和 unsupported_claim_rate
- 填入 state.metrics

`run_evals.py`：
- 从数据库和 state.metrics 汇总所有指标
- 保存 EvalRun 到数据库
- 写 eval 结果到 `data/evals/`

`finalize.py`：
- 更新 CrawlRun status 为 "completed"
- 汇总 state 为最终输出

---

### Task 4.3：组装 LangGraph 图

**文件**：修改 `src/marketsignal/agents/graph.py`

**要求**：

```python
"""LangGraph graph definition."""
from langgraph.graph import StateGraph, END
from marketsignal.agents.state import GraphState
# import all nodes

def build_pipeline() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("load_config", load_config_node)
    graph.add_node("collect_sources", collect_sources_node)
    graph.add_node("normalize_documents", normalize_documents_node)
    graph.add_node("extract_events", extract_events_node)
    graph.add_node("index_documents", index_documents_node)
    graph.add_node("analyze_signals", analyze_signals_node)
    graph.add_node("generate_weekly_report", generate_weekly_report_node)
    graph.add_node("generate_battlecards", generate_battlecards_node)
    graph.add_node("check_citations", check_citations_node)
    graph.add_node("run_evals", run_evals_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("load_config")

    graph.add_edge("load_config", "collect_sources")
    graph.add_edge("collect_sources", "normalize_documents")
    graph.add_edge("normalize_documents", "extract_events")
    graph.add_edge("extract_events", "index_documents")
    graph.add_edge("index_documents", "analyze_signals")

    # weekly_report 和 battlecards 可以并行，但 MVP 先串行
    graph.add_edge("analyze_signals", "generate_weekly_report")
    graph.add_edge("generate_weekly_report", "generate_battlecards")

    graph.add_edge("generate_battlecards", "check_citations")
    graph.add_edge("check_citations", "run_evals")
    graph.add_edge("run_evals", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()
```

**验收**：`from marketsignal.agents.graph import build_pipeline; app = build_pipeline()` 不报错。

---

### Task 4.4：连接 CLI

**文件**：修改 `src/marketsignal/cli.py`

**要求**：

把 `main()` 中的 TODO 替换为：

```python
from marketsignal.agents.graph import build_pipeline
from marketsignal.config.loader import load_pipeline_config

pipeline = build_pipeline()
config = load_pipeline_config(args.config)

initial_state = GraphState(
    target_company=config.target.name,
    competitor_ids=[c.name for c in config.competitors],
    time_window_start="",  # 由 load_config 节点填充
    time_window_end="",
    warnings=[],
    metrics={},
    status="pending",
)

result = await pipeline.ainvoke(initial_state)
logger.info("Pipeline completed: status={}", result.get("status"))
```

**验收**：`marketsignal run --config configs/competitors.ai-agent.yaml` 不报错（可能因无 API Key 而中途失败，但不应在 import 阶段崩溃）。

---

### Task 4.5：Phase 4 测试

**文件**：
- `tests/agents/test_graph.py`
- `tests/agents/test_nodes.py`

**要求**：

`test_graph.py`：验证 `build_pipeline()` 返回的图节点数量和边正确。

`test_nodes.py`：对每个节点写单元测试，mock 数据库和 LLM 调用。

**验收**：`pytest tests/agents` 全绿。

---

## Phase 5：报告渲染与输出

**目标**：让报告和 Battlecard 的输出格式固定、美观、可直接展示。

---

### Task 5.1：Markdown 报告渲染

**文件**：
- `src/marketsignal/reporting/render_markdown.py`
- `src/marketsignal/reporting/templates.py`

**要求**：

`templates.py`：定义周报和 Battlecard 的 section 模板常量。

`render_markdown.py`：

```python
def render_weekly_report(signals: list[Signal], target_name: str) -> str:
    """Render a weekly competitive intelligence report as Markdown."""
    # 按 section 组装：
    # 1. Executive Summary
    # 2. Key Changes by Competitor
    # 3. Product Update Signals (表格)
    # 4. Hiring & GTM Signals (表格)
    # 5. Recommendations (Product / Sales / Operations)
    # 6. Citations (编号列表)
    ...

def render_battlecard(company_name: str, signals: list[Signal], target_name: str) -> str:
    """Render a battlecard for a specific competitor as Markdown."""
    # 按 section 组装：
    # 1. Positioning
    # 2. Key Strengths
    # 3. Recent Moves
    # 4. Risks & Weaknesses
    # 5. Suggested Sales Response
    # 6. Evidence Sources
    ...
```

**验收**：用 mock signals 数据验证输出包含所有 section。

---

### Task 5.2：JSON 报告输出

**文件**：`src/marketsignal/reporting/render_json.py`

**要求**：

- `def render_report_json(report: Report, signals: list[Signal], claims: list[Claim], citations: list[Citation]) -> dict`
- 返回可直接 `json.dump` 的 dict

**验收**：输出 dict 包含所有 section key。

---

### Task 5.3：Phase 5 测试

**文件**：
- `tests/reporting/test_render_markdown.py`
- `tests/reporting/test_render_json.py`

**验收**：`pytest tests/reporting` 全绿。

---

## Phase 6：引用校验与评估

**目标**：实现 Citation Checker 和 Eval 指标计算。

---

### Task 6.1：引用校验器

**文件**：`src/marketsignal/citation/checker.py`

**要求**：

```python
async def check_report_citations(report: Report, session: Session) -> list[Claim]:
    """Check every claim in a report against available evidence.

    Returns a list of Claim objects with is_supported set.
    """
    # 1. 用 LLM 从报告 markdown 中抽取所有 claims
    # 2. 对每个 claim：
    #    a. 在向量库中检索相关文档片段
    #    b. 用 LLM 判断 claim 是否有检索到的片段支撑
    #    c. 标记 is_supported = True/False
    #    d. 记录 supporting_urls
    # 3. 保存 Claim 和 Citation 到数据库
```

**验收**：用 mock 报告验证 unsupported claim 被正确标记。

---

### Task 6.2：Eval 指标计算

**文件**：
- `src/marketsignal/evals/citation_coverage.py`
- `src/marketsignal/evals/unsupported_claims.py`
- `src/marketsignal/evals/dedup_rate.py`
- `src/marketsignal/evals/latency.py`
- `src/marketsignal/evals/token_cost.py`
- `src/marketsignal/evals/summary.py`

**要求**：

每个文件实现一个计算函数：

- `citation_coverage(claims: list[Claim]) -> float`：supported / total
- `unsupported_claim_rate(claims: list[Claim]) -> float`：unsupported / total
- `dedup_rate(docs: list[NormalizedDocument]) -> float`：deduped / total
- `measure_latency(func)`：装饰器，记录耗时到 state.metrics["avg_latency_ms"]
- `token_cost(tokens: int, model: str) -> float`：根据模型价格表计算 USD

`summary.py`：
- `def build_eval_summary(run_id: str, session: Session) -> EvalRun`
- 汇总所有指标，保存到数据库

**验收**：用 mock 数据验证各指标计算正确。

---

### Task 6.3：Phase 6 测试

**文件**：
- `tests/citation/test_checker.py`
- `tests/evals/test_metrics.py`

**验收**：`pytest tests/citation tests/evals` 全绿。

---

## Phase 7：FastAPI 接口

**目标**：暴露 REST API，让外部可以触发 pipeline、查询结果。

---

### Task 7.1：FastAPI 应用骨架

**文件**：`src/marketsignal/api/main.py`

**要求**：

```python
from fastapi import FastAPI
from marketsignal.api.routes import runs, reports, competitors, health

app = FastAPI(title="MarketSignal Agent", version="0.1.0")
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(competitors.router, prefix="/api/v1/companies", tags=["companies"])
app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
```

**验收**：`uvicorn marketsignal.api.main:app` 能启动。

---

### Task 7.2：路由实现

**文件**：
- `src/marketsignal/api/routes/health.py`
- `src/marketsignal/api/routes/competitors.py`
- `src/marketsignal/api/routes/runs.py`
- `src/marketsignal/api/routes/reports.py`

**要求**：

`health.py`：
- `GET /` → `{"status": "ok"}`

`competitors.py`：
- `GET /` → 公司列表
- `POST /` → 创建公司

`runs.py`：
- `POST /` → 启动 pipeline（异步，返回 run_id）
- `GET /{run_id}` → 查看 run 状态

`reports.py`：
- `GET /` → 报告列表
- `GET /{report_id}` → 报告元数据
- `GET /{report_id}/markdown` → Markdown 内容
- `GET /{report_id}/json` → JSON 内容

**验收**：`pytest tests/api` 全绿。

---

### Task 7.3：Phase 7 测试

**文件**：`tests/api/test_routes.py`

**要求**：用 `httpx.AsyncClient` + `FastAPI` 的 test client 测试每个 endpoint。

**验收**：`pytest tests/api` 全绿。

---

## Phase 8：Streamlit UI

**目标**：面试演示用的简单 Web UI。

---

### Task 8.1：Streamlit 主页

**文件**：`src/marketsignal/ui/streamlit_app.py`

**要求**：

```python
import streamlit as st

st.set_page_config(page_title="MarketSignal Agent", layout="wide")
st.title("🛰️ MarketSignal Agent")

# Sidebar: 配置
with st.sidebar:
    st.header("Configuration")
    config_path = st.text_input("Config path", "configs/competitors.ai-agent.yaml")
    use_sample = st.checkbox("Use sample dataset", value=True)
    if st.button("🚀 Run Pipeline"):
        st.session_state["running"] = True

# Main: 结果展示
tab1, tab2, tab3, tab4 = st.tabs(["📊 Weekly Report", "⚔️ Battlecards", "📈 Evals", "🔍 Evidence"])

with tab1:
    # 显示最新周报 markdown
    ...

with tab2:
    # 选择竞品，显示 Battlecard
    ...

with tab3:
    # 显示 eval 指标
    ...

with tab4:
    # 搜索证据片段
    ...
```

**验收**：`streamlit run src/marketsignal/ui/streamlit_app.py` 能启动并显示页面。

---

### Task 8.2：Phase 8 测试

Streamlit UI 不写单元测试，改为手动验收。

---

## Phase 9：本地样例数据集

**目标**：保证面试 demo 不依赖外网，100% 稳定。

---

### Task 9.1：准备样例数据

**文件**：
- `data/sample_dataset/raw/` — 预先抓取的 HTML/JSON/RSS 文件
- `data/sample_dataset/normalized/` — 预清洗的文本
- `data/sample_dataset/reports/` — 预生成的周报和 Battlecard
- `data/sample_dataset/evals/` — 预计算的 eval 结果
- `scripts/prepare_sample_dataset.py` — 从真实数据生成样例的脚本

**要求**：

- 手动运行一次完整 pipeline，把结果复制到 `sample_dataset/`
- CLI 的 `--use-sample-dataset` 模式直接读取本地文件，跳过抓取
- 样例数据必须包含：3 个竞品、5 类以上事件、至少 1 份周报和 2 份 Battlecard

**验收**：`marketsignal run --use-sample-dataset` 在无网络环境下完成运行。

---

## Phase 10：文档完善与作品集包装

**目标**：项目从"能跑"升级为"能面试"。

---

### Task 10.1：补充 docs/

**文件**：
- `docs/architecture.md` — 系统架构、模块依赖、数据流
- `docs/workflow.md` — LangGraph 工作流图、节点职责、状态流转
- `docs/data-model.md` — 数据库 ER 图、表结构说明
- `docs/api.md` — FastAPI 接口文档
- `docs/eval.md` — Eval 指标说明
- `docs/demo-script.md` — 面试演示脚本
- `docs/interview-story.md` — 面试讲述逻辑

**要求**：每篇文档不少于 200 字，配图用 Mermaid 或文本框。

---

### Task 10.2：README 中文版

**文件**：`README_CN.md`

**要求**：README.md 的完整中文翻译。

---

### Task 10.3：简历项目描述

**文件**：`docs/resume-bullets.md`

**要求**：

中文版：
> 设计并实现 MarketSignal Agent，一个面向产品与销售团队的竞品情报分析系统。系统支持自动采集竞品官网、产品更新、新闻稿、招聘岗位、GitHub Release 和用户评论等公开数据，通过 RAG、工具调用和多 Agent 工作流完成信息抽取、市场信号识别、竞品周报生成和销售 Battlecard 输出。项目实现来源引用、去重、事实校验和基础 Eval 指标，用于降低人工竞品调研成本并提升分析可信度。

英文版：
> Designed and built MarketSignal Agent, a competitive intelligence system for product and sales teams. The agent automatically collects public competitor data from websites, changelogs, GitHub releases, job postings, and reviews, then uses RAG, tool calling, and a multi-agent LangGraph workflow to extract structured events, identify market signals, and generate evidence-backed weekly reports and sales battlecards. Includes citation checking, deduplication, and eval metrics (citation coverage, unsupported claim rate, token cost).

---

### Task 10.4：演示录屏 / GIF

**要求**：
- 录制 2-3 分钟 demo 视频
- 展示：配置竞品 → 运行 pipeline → 查看周报 → 查看 Battlecard → 查看 Eval
- 保存为 `docs/demo.gif` 或 `docs/demo.mp4`

---

## 执行顺序总览

```
Phase 1  数据层          ──→  Phase 2  数据采集层
                                │
                                ↓
         Phase 3  事件抽取与 RAG
                                │
                                ↓
         Phase 4  LangGraph 工作流（核心）
                                │
                                ↓
         Phase 5  报告渲染 ←── Phase 6  引用校验与评估
                                │
                                ↓
         Phase 7  FastAPI ──→  Phase 8  Streamlit UI
                                │
                                ↓
         Phase 9  样例数据集 ──→  Phase 10  文档与包装
```

**预计时间**：4 周（按前述路线图分配）

| 周 | Phase | 交付物 |
|---|---|---|
| 第 1 周 | Phase 1 + Phase 2 | 数据库 + 抓取 + 清洗 |
| 第 2 周 | Phase 3 + Phase 4 | 事件抽取 + RAG + LangGraph 工作流 |
| 第 3 周 | Phase 5 + Phase 6 | 报告 + Battlecard + 引用校验 + Eval |
| 第 4 周 | Phase 7 + Phase 8 + Phase 9 + Phase 10 | API + UI + 样例数据 + 文档包装 |
