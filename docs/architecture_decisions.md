# SignalPulse — Architecture Decision Records (ADRs)

This document captures the **why** behind the non-obvious technical
choices in SignalPulse. Each entry follows the classic
"Context / Decision / Consequences" pattern, which is the same one used
by the [AWS ADR template](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
and the [Microsoft ADR lessons learned](https://learn.microsoft.com/en-us/azure/architecture/architectural-decision-records/recording-architectural-decisions).

> ADRs are immutable once accepted. If we want to revisit a decision,
> we add a new ADR that supersedes the old one and update the status
> field on the old entry. We never silently edit a decision in place.

The "Status" column tracks whether the decision is still current.

| #   | Title                                       | Status   |
| --- | ------------------------------------------- | -------- |
| 001 | LangGraph over CrewAI / AutoGen             | Accepted |
| 002 | Chroma over Pinecone / Weaviate / pgvector  | Accepted |
| 003 | Deterministic citation fallback             | Accepted |
| 004 | Bundled sample dataset for offline demo     | Accepted |
| 005 | Single-process CLI + FastAPI hybrid         | Accepted |
| 006 | 12-char hex run IDs                         | Accepted |
| 007 | 7-field cron in the scheduler               | Accepted |
| 008 | In-process observability vs. OpenTelemetry  | Accepted |
| 009 | WebSocket polling over in-memory pub/sub    | Accepted |
| 010 | RAG gold set over LLM self-grading          | Accepted |
| 011 | Incremental trace persistence + LRU cleanup | Accepted |

---

## ADR-001 — LangGraph over CrewAI / AutoGen

**Context.** The pipeline has a fixed sequence of 10+ steps that must
run in order, with side effects at each one (DB writes, file writes,
LLM calls). We need a graph abstraction that gives us a typed state
container, retries per node, and visibility into what ran.

**Decision.** Use [LangGraph](https://langchain-ai.github.io/langgraph/).
Each pipeline step is a Python function that takes a `GraphState`
(TypedDict) and returns a partial update. The graph is a `StateGraph`
compiled once via `build_pipeline()`.

**Consequences.**

* (+) Typed state catches "I forgot to populate X" bugs at import time.
* (+) `astream_events` and a single in-process `PipelineTrace` give us
  free observability without bolting on LangSmith.
* (+) Nodes are pure(ish) Python, so they are trivial to unit-test
  (see `tests/test_chaos.py`).
* (-) LangGraph is fast-moving; the API has churned in 2024-2025.
  We pin `langgraph>=0.1,<0.3`.
* (-) The "graph of nodes" mental model is heavier than a linear script
  for a 5-step pipeline. We accept that cost for the future-proofing.

---

## ADR-002 — Chroma over Pinecone / Weaviate / pgvector

**Context.** We need a small (≤ 10k chunks) in-process vector store
that is pip-installable and has no external service to manage. The
store is read-heavy and write-rare (one upsert per indexed document).

**Decision.** Use [Chroma](https://www.trychroma.com/) in embedded
mode. Persist to `data/chroma/`.

**Consequences.**

* (+) Zero ops: no extra container, no API key, no cost.
* (+) Persistent: data survives process restarts.
* (+) LangChain has a first-class `Chroma` integration.
* (-) Single-process lock means only one writer at a time. Acceptable
  because the pipeline is single-writer by design.
* (-) Chroma has been less stable than pgvector. We pin a specific
  version and re-evaluate if it breaks.

---

## ADR-003 — Deterministic citation fallback

**Context.** A LLM can claim "X is true" with no source attached. We
need a way to mark a claim as supported even when the LLM drops the
citation, *and* a way to mark a claim as unsupported even when the LLM
swears it cited something.

**Decision.** Add `signalpulse.citation.checker.check_report_citations`
that runs after report generation. For every `Claim`, it does a
deterministic keyword overlap check between the claim text and the
corpus of normalized documents. Claims with zero overlap are flagged
`is_supported=false` regardless of what the LLM said.

**Consequences.**

* (+) Catches LLM hallucinations at the claim level, not the report
  level. Reviewers can see *which* claim is unsupported.
* (+) No extra LLM calls; cheap to run.
* (-) Keyword overlap is naive. A claim that paraphrases the source
  (e.g. "the company expanded its leadership team" vs "VP of
  Engineering hired") will be flagged unsupported. We accept false
  positives because false negatives (uncited claims sneaking through)
  are the worse failure mode for this use case.

---

## ADR-004 — Bundled sample dataset for offline demo

**Context.** The system is a portfolio project meant to be demoed in
job interviews. The interviewer is not going to wait 3 minutes for
web fetches and LLM calls. The network may not even be available.

**Decision.** Ship a curated sample dataset in `data/sample/`
(pre-populated companies, raw documents, events, signals). The
`build_pipeline(use_sample_dataset=True)` path skips the
fetch / LLM-extract / LLM-analyze nodes and uses a `load_sample_node`
that injects this dataset into the graph state.

**Consequences.**

* (+) End-to-end pipeline completes in ~1 second on a laptop, with
  zero API keys. The interviewer sees the full report / battlecard
  output.
* (+) Smoke test (`scripts/init_db.py --with-sample` + `marketsignal
  run --use-sample-dataset`) doubles as a CI gate.
* (-) The sample dataset must be hand-maintained. We commit
  `data/sample/*.json` to git.
* (-) LLM-driven nodes are not exercised in the smoke test, so we
  keep a separate `tests/evals/test_rag_eval.py` that uses a real
  keyword-overlap check and runs against the bundled data.

---

## ADR-005 — Single-process CLI + FastAPI hybrid

**Context.** The pipeline is a stateful, write-heavy workload that
should not be parallelized. The API is mostly read (list runs, fetch
reports, fetch metrics) and benefits from being async. We do not have
ops budget for a worker queue (Celery + Redis) for a single-developer
project.

**Decision.** Expose two entry points that share the same DB and
the same pipeline code:

1. `python -m signalpulse run ...` — synchronous CLI. Spins up a
   fresh pipeline per invocation.
2. `uvicorn marketsignal.api.app:create_app --factory` — FastAPI
   server. The `POST /runs` route kicks the pipeline off in a
   `BackgroundTasks` thread; everything else is in-process.

**Consequences.**

* (+) One process, one DB, one pipeline definition. No queue to
  configure, no separate worker container.
* (+) FastAPI's TestClient gives us full HTTP coverage in unit tests
  (see `tests/test_app.py`, `tests/test_metrics_endpoint.py`).
* (-) The background-task model means the API and the pipeline share
  a Python process. If the pipeline OOMs, the API goes down too.
  Acceptable for a portfolio project; would not be acceptable for
  production.
* (-) No real concurrency. Two simultaneous `POST /runs` will run
  sequentially.

---

## ADR-006 — 12-char hex run IDs

**Context.** Every `CrawlRun`, `Event`, `Signal`, and `Report` row
needs a primary key. UUIDs are 36 chars and look noisy in URLs; serial
integers leak business volume.

**Decision.** Generate IDs with `new_id() = secrets.token_hex(6)`,
giving 12 lowercase hex characters (48 bits of entropy). Use as the
primary key column type (`String(12)`) in every model.

**Consequences.**

* (+) ~281 trillion possible IDs — collision probability is
  negligible for a single-process system.
* (+) Short, URL-safe, log-friendly.
* (-) Not sortable by creation time. If we ever need that, we add
  a `created_at` index (already present via `TimestampMixin`).
* (-) 12 chars is non-standard; if we ever migrate to UUIDv7 we
  will need a one-time backfill.

---

## ADR-007 — 7-field cron in the scheduler

**Context.** Some users want to schedule runs ("every weekday at 8am",
"every 15 minutes"). We do not want to pull in `croniter` for what is
essentially 30 lines of parsing.

**Decision.** Support the **7-field extended cron** format
`(seconds) minutes hours day-of-month month day-of-week (year)`.
The first 6 fields behave like Vixie cron; the 7th field is an
optional year filter. We ship our own `_parse_cron()` that rejects
anything that is not 7 fields (see `tests/test_chaos.py` for the
rejection cases).

**Consequences.**

* (+) 7 fields gives us sub-minute resolution (a 5-field cron
  cannot say "every 30 seconds" without another tool).
* (+) Self-contained — no `croniter` dep.
* (-) Not POSIX. A user coming from crontab will get surprised by
  the extra field. We document the format in `docs/architecture.md`
  and reject 5-field input at the parser, not silently.

---

## ADR-008 — In-process observability vs. OpenTelemetry

**Context.** We need per-run cost (USD) and latency (p50/p95) data
to put on a dashboard. The "right" answer is OpenTelemetry +
Prometheus + Grafana. That is a 3-package dependency and ~1k LoC of
configuration for a project that is read once per run.

**Decision.** Roll our own 150-line `RunMetrics` class that
accumulates token counts via a LangChain `BaseCallbackHandler` and
node durations via the existing `trace_node` decorator. Persist as
a JSON blob inside the trace file. Expose via `GET /metrics/{run_id}`.

**Consequences.**

* (+) One file, no extra deps, no exporter config.
* (+) Token cost can use the project's own price table
  (`signalpulse.evals.token_cost`), so a model swap is one line.
* (-) No histograms, no Prometheus scraping, no Grafana dashboards.
  If we need those later, we add a `RunMetricsExporter` that reads
  the same JSON blob.
* (-) Token counts depend on the LLM provider returning usage in
  `response.llm_output.token_usage`. Some providers do not; we
  fall back to 0 with a warning in the logs.

---

## ADR-009 — WebSocket polling over in-memory pub/sub

**Context.** The Streamlit UI wants to show "the pipeline is currently
running node X" without polling. The pipeline runs in a
`BackgroundTasks` thread inside the FastAPI process, so we *could*
hand a `queue.Queue` to the node decorator and have the WebSocket
endpoint consume from it.

**Decision.** Have `trace_node` rewrite the trace JSON on every span
completion, and have the WebSocket endpoint poll the trace file every
500ms. The DB row's status is the secondary signal.

**Consequences.**

* (+) No cross-thread queue plumbing. The WebSocket endpoint is
  pure-Python async; the pipeline is a regular thread; the only
  shared state is a file on disk.
* (+) The trace file is the single source of truth — if the
  WebSocket client reconnects, it gets the full state.
* (-) Up to 500ms of latency between span completion and the
  client seeing it. Acceptable for a human-facing dashboard.
* (-) Extra disk writes (one per span). O(10) spans per run, file
  is small — negligible.

---

## ADR-010 — RAG gold set over LLM self-grading

**Context.** The original `citation_coverage` metric asked the LLM
"are all your claims supported?" — i.e. the LLM graded itself. This
systematically over-reports quality. The team agreed this was a real
liability for a system that ships claims into sales conversations.

**Decision.** Hand-curate a 15-question RAG gold set in
`data/eval_goldset/rag_qa.json`. Each question has an expected
company and a list of expected keywords. The new
`marketsignal rag-eval` command computes recall@1/3/5, MRR, and
keyword coverage, and prints a per-category breakdown.

**Consequences.**

* (+) A reproducible, deterministic metric. We can chart it over
  time and gate releases on it.
* (+) Per-category breakdown surfaces where the retriever is weak
  (e.g. "pricing" questions have lower coverage than "hiring").
* (-) 15 questions is a small gold set. We add to it when we find
  a regression.
* (-) The gold set drifts if the bundled sample dataset changes.
  We pin both to the same commit.

---

---

## ADR-011 — Incremental trace persistence + LRU cleanup

**Context.** The trace JSON at ``data/traces/{run_id}.json`` is the
single source of truth for the WebSocket stream endpoint (ADR-009). To
make live progress visible, the trace has to be on disk *before* the
run finishes. That means rewriting the file on every completed span
rather than once at ``finish_trace``.

A side effect of this is that ``utils/tracing.py`` accumulates entries
in two module-level dicts (``_CURRENT``, ``_METRICS``) and on disk
indefinitely. A long-running API server would have:
- unbounded memory (each ``RunMetrics`` is small but there is no cap)
- unbounded ``data/traces/`` directory growth
- unbounded disk usage in deployments that share storage with the DB

**Decision.** Two policies, both applied at every ``start_trace`` /
``finish_trace`` call (under a single ``threading.Lock``):

1. **Age-based eviction**: any run whose ``RunMetrics.finished_at``
   is older than 24 hours is dropped from the in-memory dicts and
   its on-disk JSON is unlinked.
2. **Cap-based eviction**: if the in-memory dict is still over
   ``_MAX_ENTRIES = 50`` after age-based eviction, the oldest runs
   (by dict insertion order) are dropped.

The lock is per-module, not per-run, so concurrent WebSocket clients
do not see a half-pruned state.

**Consequences.**

* (+) Bounded memory: at most 50 ``RunMetrics`` in the process.
* (+) Bounded disk: at most ~50 trace JSON files at any time.
* (+) Self-healing: no scheduled cleanup job needed; the next pipeline
  run evicts the old ones.
* (-) The 24h / 50 cap is a hard ceiling. A user who wants to keep
  traces for a month must copy ``data/traces/`` to cold storage before
  the next run evicts them. The ADR is honest about this trade-off.
* (-) The cap is per-process, not global. Multiple API workers each
  keep their own 50 entries. For a single-process dev server (the
  only deployment we currently support) this is fine; a multi-worker
  production deployment would need an out-of-process store.

---

## See also

* `docs/architecture.md` — the system-level architecture (layers,
  data flow, deployment).
* `docs/database.md` — the relational schema and migration story.
* `docs/demo-script.md` — how to demo this in a 5-minute interview.
* `docs/interview-story.md` — the "tell me about this project"
  walk-through.
## See also

* `docs/architecture.md` — the system-level architecture (layers,
  data flow, deployment).
* `docs/database.md` — the relational schema and migration story.
* `docs/demo-script.md` — how to demo this in a 5-minute interview.
* `docs/interview-story.md` — the "tell me about this project"
  walk-through.
