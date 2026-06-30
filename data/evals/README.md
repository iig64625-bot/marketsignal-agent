# Eval Runs

每次 pipeline run 的评估指标输出：

- citation_coverage — 有引用支撑的关键结论占比
- unsupported_claim_rate — 无来源结论占比
- dedup_rate — 重复信息合并率
- vg_latency_ms / 	oken_cost_usd — 性能与成本

文件名格式：eval_<run_id>.json。同时会写入 eval_runs 表便于历史对比。

