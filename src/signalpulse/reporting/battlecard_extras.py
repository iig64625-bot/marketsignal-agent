"""LLM-driven battlecard enrichment (sales pitch + attack points + talk tracks, in Chinese)."""
from __future__ import annotations

from typing import Any

from loguru import logger

from signalpulse.models.signal import Signal
from signalpulse.utils.llm import get_llm

_BATTLE_PROMPT = """你是一位资深竞争销售策略师。根据下面提供的竞品市场信号，生成一份**中文**销售竞争卡片，包含：
- sales_pitch：1-2 句话的电梯演讲，供销售团队直接使用。
- attack_points：3-5 个具体可利用的弱点，每条配一句证据引用。
- talk_tracks：3-5 句具体话术，对应常见客户场景。
- summary：一句话 TL;DR 总结。

要求：具体、可执行、紧扣提供的信号。如果信号是推断性内容（analysis/recommendation），标注可信度较低。不要编造信号中没有的事实。
**所有输出必须使用中文。**"""


def _build_prompt(target_company: str, competitor: str, signals: list[Signal]) -> str:
    lines = [
        f"我方（TARGET）：{target_company}",
        f"竞品（COMPETITOR）：{competitor}",
        "信号（SIGNALS）：",
    ]
    for s in signals:
        lines.append(f"- 类型={s.signal_type} 可信度={s.confidence} 发现={s.finding}")
        if s.analysis:
            lines.append(f"  分析：{s.analysis}")
        if s.recommendation:
            lines.append(f"  建议：{s.recommendation}")
    lines.append("请按以下 JSON 字段返回一个扁平对象：sales_pitch (字符串), attack_points (3-5 个对象，每个含 weakness/evidence/confidence 浮点数), talk_tracks (3-5 个对象，每个含 situation/line/confidence 浮点数), summary (字符串)。注意：所有 confidence 字段必须是 0.0 到 1.0 之间的浮点数（如 0.75），不允许传字符串。不要包装在额外字段中。")
    return "\n".join(lines)


async def generate_battlecard_extras(
    target_company: str,
    competitor: str,
    signals: list[Signal],
    *,
    run_id: str | None = None,
    node: str = "generate_battlecard_extras",
) -> dict[str, Any]:
    """Call the LLM for sales_pitch + attack_points + talk_tracks (Chinese).

    Falls back to a deterministic, signal-derived result if no LLM is configured
    or the call fails.
    """
    fallback: dict[str, Any] = {
        "sales_pitch": "",
        "attack_points": [],
        "talk_tracks": [],
        "summary": "",
        "fallback": True,
    }
    if not signals:
        return fallback
    try:
        llm = get_llm()
    except ValueError as exc:
        logger.info("battlecard_extras: LLM unavailable, using fallback: {}", exc)
        return fallback
    from signalpulse.models.schemas import BattlecardExtras  # local to avoid cycles

    # NOTE: skip with_structured_output (DeepSeek no json_schema support)
    try:
        from signalpulse.observability.llm_tracking import invoke_with_metrics

        result_msg = await invoke_with_metrics(
            run_id=run_id,
            node=node,
            llm=llm,
            messages=[
                {"role": "system", "content": _BATTLE_PROMPT},
                {"role": "user", "content": _build_prompt(target_company, competitor, signals)},
            ],
        )
        # Manual JSON parse (DeepSeek no response_format=json_schema).
        import json as _json
        content = getattr(result_msg, "content", None) or str(result_msg)
        raw_text = content.strip()
        if raw_text.startswith("`"):
            raw_text = raw_text.strip("`")
            if raw_text.lower().startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        data = _json.loads(raw_text)
        # Tolerate LLMs that wrap the response in {"battlecard_extras": {...}}
        if isinstance(data, dict) and "battlecard_extras" in data and isinstance(data["battlecard_extras"], dict):
            data = data["battlecard_extras"]
        result = BattlecardExtras.model_validate(data)
        return {
            "sales_pitch": result.sales_pitch,
            "attack_points": [ap.model_dump() for ap in result.attack_points],
            "talk_tracks": [t.model_dump() for t in result.talk_tracks],
            "summary": result.summary,
            "fallback": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("battlecard_extras: LLM call failed, using fallback: {}", exc)
        return fallback


__all__ = ["generate_battlecard_extras"]