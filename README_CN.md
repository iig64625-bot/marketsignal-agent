<div align="center">

# 🛰️ SignalPulse

**面向产品、市场与销售团队的 AI 竞品情报与市场信号分析 Agent**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent%20Workflow-orange)](https://langchain-ai.github.io/langgraph/)
[![Chroma](https://img.shields.io/badge/Chroma-Vector%20DB-green)](https://www.trychroma.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-Demo%20UI-ff4b4b)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 一个能够持续监控竞品公开动态、识别市场信号、并自动生成**带引用证据**的竞品周报与销售 Battlecard 的 AI Agent。

[English](./README.md) · [简体中文](./README_CN.md) · [架构](./docs/architecture.md) · [Demo 脚本](./docs/demo-script.md)

</div>

---

## 🎯 这个项目解决什么问题

产品经理、市场分析师、销售团队每天都要回答这些问题：

- **竞品最近发布了什么？**
- **他们是不是在转向企业市场？**
- **他们的弱点是什么？客户在抱怨什么？**
- **我们应该怎么调整产品、销售和运营策略？**

但现实是：

- 信息分散在官网、Changelog、GitHub、招聘页、定价页、评论里
- 人工整理一份周报要 4–8 小时
- 没有来源的结论不可信，没人会真的拿去用
- 同样的事下周还要再做一遍

**SignalPulse** 把这件事自动化：

> 主动采集竞品公开信号 → 结构化抽取 → 识别市场信号 → 生成周报 + Battlecard → 校验每条结论的引用证据 → 输出 Eval 指标

---

## ✨ 核心特性

- 🔍 **多源采集**：官网、Blog、Changelog、GitHub Releases、招聘页、定价页、公开评论
- 🧠 **多 Agent 工作流**（LangGraph）：Collector → Extractor → SignalAnalyzer → ReportWriter → CitationChecker
- 📚 **RAG 检索增强**：Chroma 向量库 + 结构化 metadata，支持按公司/来源/时间检索
- 🛰️ **市场信号识别**：把"招聘岗位变化""GitHub Release 频率"等转成"业务方向""可执行建议"
- 📝 **业务输出**：竞品周报 + 销售 Battlecard，每条关键结论都有引用
- 🛡️ **引用校验**：Citation Checker 自动检查 unsupported claims，区分 fact / analysis / recommendation / confidence
- 📊 **Eval 与可观测性**：引用覆盖率、去重率、延迟、Token 成本
- 🖥️ **Streamlit Demo UI**：一键跑全流程，面试现场稳定演示
- 🧪 **本地样例数据集**：保证 demo 100% 不翻车

---

## 🏗️ 架构图

```
                ┌─────────────────────┐
                │  Competitor Config  │
                └──────────┬──────────┘
                           ↓
   ┌──────────────────────────────────────────┐
   │        Data Collection Layer             │
   │  HTTP · RSS · GitHub API · Playwright    │
   └──────────────────────┬───────────────────┘
                          ↓
   ┌──────────────────────────────────────────┐
   │      Cleaning & Normalization            │
   │  去重 · 正文提取 · 时间解析 · 分类         │
   └──────────────────────┬───────────────────┘
                          ↓
   ┌──────────────────────────────────────────┐
   │      Event Extraction (Structured)       │
   │  product_update · pricing · hiring …     │
   └──────────────────────┬───────────────────┘
                          ↓
   ┌──────────────────────────────────────────┐
   │      RAG Layer (Chroma)                  │
   │  chunking · embedding · metadata · search │
   └──────────────────────┬───────────────────┘
                          ↓
   ┌──────────────────────────────────────────┐
   │     LangGraph Agent Workflow             │
   │  Signal Analyzer → Report Writer         │
   │  → Citation Checker → Eval               │
   └──────────────────────┬───────────────────┘
                          ↓
   ┌──────────────────────────────────────────┐
   │     Markdown + JSON Reports              │
   │  weekly report · sales battlecard        │
   │  citations · eval_runs                   │
   └──────────────────────────────────────────┘
```

详细分层与模块说明见 [`docs/architecture.md`](./docs/architecture.md)。

---

## 🧰 技术选型

| 类别 | 选型 | 理由 |
|---|---|---|
| Workflow | LangGraph | 节点 + 状态机 + 分支，比手写 chain 健壮 |
| LLM Orchestration | LangChain | Provider-agnostic，一行切换 OpenAI / Anthropic / DeepSeek |
| Vector DB | Chroma | 本地 + 嵌入式，零运维 |
| ORM | SQLAlchemy 2.0 | 类型友好，可平迁到 Postgres |
| Migration | Alembic | 标准 |
| Config | pydantic-settings | 与 schema 复用 |
| HTTP | httpx | async / sync 兼顾 |
| 解析 | trafilatura + readability-lxml | 比 BeautifulSoup 更准 |
| RSS | feedparser | 优先静态请求，避免反爬 |
| 兜底渲染 | Playwright | 仅在必要时启用 |
| GitHub | PyGithub | 稳定 |
| 前端 | Streamlit | 5 行起 UI，面试演示最高效 |
| 日志 | loguru | 结构化、易读 |
| LLM | OpenAI / Anthropic / DeepSeek | Provider-agnostic |
| Embedding | text-embedding-3-small | 性价比高 |

---


### 技术选型理由（为什么不用别的）

| 选型 | 不选什么 | 理由 |
|---|---|---|
| **LangGraph** | CrewAI / AutoGen | LangGraph 是显式状态机（StateGraph + TypedDict），每个节点输入输出都进 state，调试时可重放、可单步。CrewAI 角色扮演式抽象层数太多，幻觉和不可观测问题难排。 |
| **Chroma** | Pinecone / Weaviate | 本地嵌入式 + 零运维，面试 demo 不用起 docker。Pinecone 商用要钱 + 网络依赖。Weaviate 太重，要单独 ES。 |
| **SQLAlchemy 2.0** | Django ORM / Tortoise | 类型友好（`Mapped[str]`）+ 异步原生。生产换 Postgres 改一行 URL 即可。 |
| **Pydantic v2** | dataclasses / attrs | v2 性能是 v1 的 50 倍，schema 复用给 API 和 LLM 输出校验。 |
| **loguru** | stdlib logging | 一行 `logger.add()` 完成结构化输出，handler / filter 概念对单服务过度。 |
| **Streamlit** | Gradio / Next.js | 5 行起一个交互页，demo 现场改 config 立刻能跑。Gradio 偏 ML 模型展示，Next.js 偏生产应用。 |
| **FastAPI** | Flask / Django REST | 自动 OpenAPI + Pydantic 集成 = API 文档零成本，类型提示贯穿 controller 到 schema。 |
| **Alembic** | 手写 DDL | schema 演化是真实生产痛点，alembic revision 文件就是 schema 的 git history。 |
| **tenacity → 自研 retry_with_backoff** | tenacity 现成方案 | 已经在用，但需要 429 + Retry-After 头时手写比 tenacity 干净。 |

> 一句话选型哲学：**用最 boring 的栈完成"实在"的事**——LangGraph 不是银弹，但它是当下最稳的"显式多 Agent 编排"工具；Chroma 不是最好的向量库，但它是 dev 零依赖能跑起来的那一个。


## 🚀 快速开始

### 1. 克隆与安装

```bash
git clone https://github.com/<your-username>/signalpulse-agent.git
cd signalpulse-agent

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
```

填入你的 LLM API Key（OpenAI / Anthropic / DeepSeek 任选）。

### 2. 初始化数据库

```bash
alembic upgrade head
```

### 3. 配置竞品

编辑 `configs/competitors.ai-agent.yaml`：

```yaml
target_company:
  name: "Dify"

competitors:
  - name: "Coze"
    website: "https://www.coze.com"
    changelog: "https://www.coze.com/changelog"
    github: "https://github.com/bytedance/coze"
    jobs: "https://www.coze.com/careers"

  - name: "FastGPT"
    website: "https://fastgpt.in"
    github: "https://github.com/labring/FastGPT"
    docs: "https://doc.tryfastfastgpt.ai"

monitoring_dimensions:
  - product_update
  - pricing
  - hiring
  - github_release
```

### 4. 跑一次完整流程

```bash
# CLI 模式
marketsignal run --config configs/competitors.ai-agent.yaml

# 或启动 UI
streamlit run src/marketsignal/ui/streamlit_app.py
```

### 5. 稳定 Demo（不依赖外网）

```bash
marketsignal run --use-sample-dataset
```

样例数据集已内置，面试现场 100% 可演示。

---

## 📁 项目结构

```
signalpulse-agent/
├── README.md
├── README_CN.md
├── pyproject.toml
├── .env.example
├── alembic.ini
├── configs/
│   └── competitors.ai-agent.yaml
├── docs/
│   ├── architecture.md
│   ├── workflow.md
│   ├── data-model.md
│   ├── api.md
│   ├── eval.md
│   ├── demo-script.md
│   └── interview-story.md
├── data/
│   ├── raw/
│   ├── normalized/
│   ├── reports/
│   ├── evals/
│   └── sample_dataset/
├── migrations/
├── src/marketsignal/
│   ├── api/                # FastAPI 路由
│   ├── agents/             # LangGraph 节点
│   │   └── nodes/
│   ├── analysis/           # 市场信号识别
│   ├── citation/           # 引用校验
│   ├── config/             # 配置
│   ├── db/                 # 数据库连接
│   ├── evals/              # 评估指标
│   ├── events/             # 结构化事件抽取
│   ├── ingestion/          # 数据采集
│   ├── models/             # ORM 模型
│   ├── normalization/      # 清洗与去重
│   ├── rag/                # chunking / embedding / retriever
│   ├── reporting/          # 周报 + Battlecard 渲染
│   ├── services/           # 业务服务
│   ├── ui/                 # Streamlit
│   └── utils/
└── tests/
```

---

## 📊 Eval 指标

| 指标 | 含义 | 目标 |
|---|---|---|
| Citation Coverage | 有引用支撑的关键结论占比 | > 90% |
| Unsupported Claim Rate | 无来源结论占比 | < 10% |
| Dedup Rate | 重复信息合并率 | 越高越好 |
| Latency | 端到端生成耗时 | 视模型而定 |
| Token Cost | 每次运行成本 | 视模型而定 |

详见 [`docs/eval.md`](./docs/eval.md)。

---

## 🎤 面试讲述逻辑

1. **为什么做**：竞品信息分散、人工周报耗时、结论没有来源
2. **为什么不是普通 RAG**：这是主动采集 + 信号识别 + 决策支持，不是被动问答
3. **怎么设计**：采集 → 清洗 → 抽取 → RAG → Agent → 报告 → 引用校验 → Eval
4. **怎么控幻觉**：每条 claim 必带 evidence，事实/分析/建议分层，Citation Checker 自动检查
5. **怎么评估**：引用覆盖率、去重率、延迟、成本
6. **业务价值**：帮 PM/Sales 持续监控市场变化、生成可执行建议，输出 Battlecard 直接服务销售场景

---

## ⚠️ 合规说明

- 仅采集公开数据（RSS、官网、GitHub、公开招聘页、官方文档、公开评论）
- 不抓取需登录、付费或绕过反爬的内容
- 控制请求频率，尊重 robots.txt
- 报告中所有引用均回溯到原始 URL

---

## 🛣️ Roadmap

- [x] 最小采集 + Markdown 报告
- [ ] LangGraph 多节点工作流
- [ ] Battlecard + 引用校验
- [ ] Eval 指标
- [ ] Streamlit UI
- [ ] 本地样例数据集
- [ ] 多语言报告（i18n）
- [ ] 定时任务（APScheduler）
- [ ] 多租户 / 团队协作（未来）

---

## 📜 License

MIT
