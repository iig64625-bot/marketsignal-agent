"""LLM-driven battlecard enrichment (sales pitch + attack points + talk tracks)."""
from __future__ import annotations

from typing import Any

from loguru import logger

from marketsignal.models.signal import Signal
from marketsignal.utils.llm import get_llm

_BATTLE_PROMPT = """You are a competitive sales strategist. Given a set of observed market signals
about a competitor, produce a sales battlecard with:
- sales_pitch: 1-2 sentence elevator pitch our sales team can use.
- attack_points: 3-5 specific weaknesses we can exploit, each with a one-line evidence citation.
- talk_tracks: 3-5 specific conversation lines mapped to common buyer situations.
- summary: one-sentence TL;DR for the sales rep.

Be specific, actionable, and grounded in the provided signals. If a signal is interpretive
(analysis/recommendation), note it has lower confidence. Do not invent facts not present
in the signals."""


def _build_prompt(target_company: str, competitor: str, signals: list[Signal]) -> str:
    lines = [f"TARGET (us): {target_company}", f"COMPETITOR: {competitor}", "SIGNALS:"]
    for s in signals:
        lines.append(
            f"- type={s.signal_type} confidence={s.confidence} finding={s.finding}"
        )
        if s.analysis:
            lines.append(f"  analysis: {s.analysis}")
        if s.recommendation:
            lines.append(f"  recommendation: {s.recommendation}")
    lines.append("Return the JSON for BattlecardExtras.")
    return "\n".join(lines)


async def generate_battlecard_extras(
    target_company: str,
    competitor: str,
    signals: list[Signal],
    *,
    run_id: str | None = None,
    node: str = "generate_battlecard_extras",
) -> dict[str, Any]:
    """Call the LLM for sales_pitch + attack_points + talk_tracks.

    Falls back to a deterministic, signal-derived result if no LLM is configured
    or the call fails. The fallback is intentionally lightweight: the existing
    "Suggested Sales Response" section still works on signal.recommendation.
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
    from marketsignal.models.schemas import BattlecardExtras  # local to avoid cycles

    structured = llm.with_structured_output(BattlecardExtras)
    try:
        from marketsignal.observability.llm_tracking import invoke_with_metrics

        result: BattlecardExtras = await invoke_with_metrics(
            run_id=run_id,
            node=node,
            llm=structured,
            messages=[
                {"role": "system", "content": _BATTLE_PROMPT},
                {"role": "user", "content": _build_prompt(target_company, competitor, signals)},
            ],
        )
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
