"""Section title constants + signal type labels (all in Chinese)."""
from __future__ import annotations

WEEKLY_SECTIONS = [
    "执行摘要",
    "按竞品的关键变化",
    "产品更新信号",
    "招聘与 GTM 信号",
    "行动建议",
    "引用",
]

BATTLECARD_SECTIONS = [
    "定位",
    "核心优势",
    "近期动作",
    "风险与弱点",
    "建议销售话术",
    "进攻点",
    "证据来源",
]

# Map signal_type (DB value) -> Chinese display label
SIGNAL_TYPE_LABELS: dict[str, str] = {
    "product": "产品",
    "product_update": "产品更新",
    "pricing": "定价",
    "hiring": "招聘",
    "gtm": "上市策略",
    "risk": "风险",
    "ecosystem": "生态",
    "enterprise": "企业",
    "community": "社区",
    "user_feedback": "用户反馈",
    "github_release": "GitHub 发布",
}


def label_signal_type(t: str | None) -> str:
    """Translate a raw signal_type to its Chinese display label."""
    return SIGNAL_TYPE_LABELS.get((t or "").lower(), t or "其他")