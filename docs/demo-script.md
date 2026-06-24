# SignalPulse — 面试演示脚本

> 本文用于面试现场的 5 分钟现场演示 + Q&A 准备。所有命令都在 PowerShell + venv 环境下验证过（57 个测试全绿）。

## 0. 演示总目标

让面试官在 5 分钟内看到 4 件事：

1. **真问题**：竞品情报分散、人力周报 4-8 小时、结论无来源
2. **真系统**：完整的多 Agent pipeline，不是单一 prompt
3. **真护栏**：每条结论有引用、有 eval 指标、可量化
4. **真离线**：样例数据集 100% 可演示，0 网络 0 token

> 不要花时间讲"什么是 RAG / 什么是 LangGraph"。直接 demo。

## 1. 演示前 30 秒准备

```powershell
# 打开 3 个终端 + 1 个 IDE
# T1: 项目根目录
# T2: data/reports/ 目录
# T3: pytest watch 模式（可选）

# 确认 venv 与依赖
.\.venv\Scripts\python.exe -c "import signalpulse; print('OK')"
```

**提前打印好贴在墙上**：
- `python -m signalpulse.cli run --use-sample-dataset` ← 主命令
- 9 个 signals / 2 个 competitors / 6 个 high-confidence ← 期望输出
- 引用覆盖率 0.47（无 LLM 的真实值）← 主动解释，不要回避

## 2. 5 分钟脚本（按时间分配）

### 0:00 - 0:30  开场：定位问题

> "做产品的都知道一个痛点：竞品周报。每周一要花 4-8 小时刷 8 个竞品的官网、changelog、GitHub、招聘页……即便写出来，老板第一句话也是：'来源呢？'"

**要点**：
- 强调"4-8 小时"和"来源"两个数字
- 不要展开 RAG / Agent 概念
- 顺势切到 T1，跑命令

### 0:30 - 1:30  跑 Sample Pipeline（核心动作）

```powershell
$env:PYTHONPATH = "src"
Remove-Item data\reports\*.md -ErrorAction SilentlyContinue
python -m signalpulse.cli run --use-sample-dataset
```

**T1 跑完后**关键日志会打印：

```
INFO  Pipeline completed: status=completed warnings=0
INFO  Metrics: {
  "citation_coverage": 0.47,
  "unsupported_claim_rate": 0.53,
  "total_claims": 77,
  "supported_claims": 36
}
```

**主动解释**（不等人问）：
- "0.47 不是 bug，是我故意演示的诚实值——无 LLM 时确定性 fallback 的真实水平"
- "配上 OpenAI key 跑真实模式，coverage 一般能到 0.9+"

### 1:30 - 2:30  打开周报 & Battlecard

```powershell
code .\data\reports\weekly_*.md
code .\data\reports\battlecard_*.md
```

**指着周报说**：
- "Executive Summary 告诉 PM 这周发生了什么"
- "Signals by Type / by Competitor 是结构化视图"
- "每条 finding 都标了 confidence"

**指着 Battlecard 说**：
- "这一张是给销售用的，可以直接打印带去见客户"
- "Suggested Sales Response 是可执行的下一步动作"
- "Evidence Sources 会回填真实 URL（demo 里走 fallback 不会回填，但接口已经留好）"

### 2:30 - 3:30  展示 Eval 指标

```powershell
code .\data\evals\eval_*.json
```

**解释 4 个指标**：
- `citation_coverage` — 关键结论有引用的比例
- `unsupported_claim_rate` — 没法验证的结论
- `dedup_rate` — 重复信息被合并的比率
- `total_claims` — claim 数量（侧面反映报告密度）

> "为什么这是 '实在' 的系统？因为我能告诉你哪些话没证据。这比一个只会说漂亮话的黑盒强 100 倍。"

### 3:30 - 4:30  展示代码 & 测试

```powershell
# 测试
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest -q

# 看一眼核心 graph
code .\src\marketsignal\agents\graph.py
code .\src\marketsignal\citation\checker.py
```

**重点**：
- "57 个测试 0.7 秒跑完"
- "graph.py 只有 88 行，但组装了 11 个节点"
- "checker.py 190 行 = LLM 模式 + 确定性 fallback 双实现"
- "全代码 0 行业务 hack，节点之间只走 GraphState"

### 4:30 - 5:00  收尾：技术选型一句话总结

> "LangGraph 管流程、SQLAlchemy 管持久化、Chroma 管 RAG、Pydantic 管 schema、Loguru 管日志、SQLite 让 demo 零成本。**没有用任何花架子**。"

## 3. 5 个高频 Q&A

### Q1：为什么用 LangGraph 而不是普通 Python function chain？

> 因为节点的依赖是**有状态 + 有分支**的。比如 collect_sources 失败要回退到 sample、check_citations 需要 evals 的指标回写、finalize 要根据前面所有 warnings 决定 status。LangGraph 给的 StateGraph + TypedDict 比手写 if-else 健壮得多。

### Q2：Embedding 不通怎么办？LLM key 缺失怎么办？

> 每一层都有 **deterministic fallback**：
> - Embedding 缺失 → `vector_store.search` 返回空 → `citation/checker` 立刻回退到 `NormalizedDocument` 表扫描
> - LLM 缺失 → `extractor` 用关键词规则；`analyze_signals` 跳过并 append warning；`citation/checker` 用关键词重叠判定
> - 全网络断开 → `--use-sample-dataset` 走 sample 流水线，0 网络跑通

### Q3：引用覆盖率 0.47 是不是太低了？

> 这是**没有 LLM 的下限**。确定性 fallback 只能做"关键词重叠"判定，碰到分析性 claim（"per-seat pricing 改善 land-and-expand"）就判不了。配上 OpenAI key 走 LLM 判定一般能到 0.9+。
>
> 同时这恰恰是"实在"的体现——系统**诚实地告诉你**哪些话没证据，而不是装作都验证了。

### Q4：生产环境怎么扩？

> 三个改动：
> 1. `MARKETSIGNAL_DB_URL` 指向 Postgres（已经走 SQLAlchemy，0 代码改动）
> 2. `load_config` 加 `apscheduler` 定时触发，weekly 报告 cron 跑
> 3. 加一个 `signalpulse.agents.nodes.publish_slack` 节点，把 report 推到 Slack/飞书
>
> 整套架构没为单机 demo 做特殊优化，迁移是**水平**的。

### Q5：和直接写 prompt 让 LLM 生成竞品周报有什么区别？

> 三点根本区别：
>
> | | Prompt 直接调 LLM | SignalPulse |
> |---|---|---|
> | **数据来源** | LLM 自己的训练知识（过时 + 幻觉） | 实抓的 URL（可点击） |
> | **过程** | 一次性生成 | 11 个节点 + 引用校验 + 评估 |
> | **可量化** | 无 | coverage / unsup / dedup / latency / cost |
>
> 本质差别是**有没有护栏**。LLM 写报告是把信任全压在一个模型上；这个系统是把信任分到「数据 + 抽取 + 引用 + 评估」4 道关卡。

## 4. 演示踩坑清单

| 坑 | 现象 | 应对 |
|---|---|---|
| PowerShell 编码乱码 | `Get-Content` 中文乱码 | 开头加 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` |
| 端口冲突 / 网络 | 抓不到竞品官网 | **永远用 `--use-sample-dataset`**，不要演示真实抓取 |
| 测试时间过长 | pytest 超时 | 跑 `pytest -q --no-header`，全量 0.7 秒 |
| venv 路径错 | `python` 找不到包 | 严格用 `.\.venv\Scripts\python.exe` 而非系统 python |
| 残留 DB | 上次跑的数据混入 | `Remove-Item data\marketsignal.db` + `alembic upgrade head` |
| MMX CLI 干扰 | `MMX_CONFIG_DIR` 残留导致路径错 | 演示前 `$env:MMX_CONFIG_DIR = $null` |

## 5. 一句话电梯演讲（30 秒版）

> "SignalPulse 是给产品/销售团队用的 AI 竞品情报系统。它主动抓竞品公开数据，过 LangGraph 多 Agent 工作流（不是单个 prompt），生成**带引用证据**的周报和销售 Battlecard，并自动跑 5 个 eval 指标（引用覆盖率、未支撑率、去重率、延迟、token 成本）。整套系统在本地 SQLite 上跑，57 个测试 0.7 秒绿，样例数据 0 网络可演示。"
