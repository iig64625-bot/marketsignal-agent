"""ops/translate_findings.py - ???? signal.findings ??? (LLM ??)."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from openai import OpenAI
from signalpulse.db.session import get_session
from signalpulse.models import Signal

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL"))

SYSTEM_PROMPT = """You are a translation expert for competitive intelligence.
Translate the given English signal ''finding'' to Chinese (??).
Output ONLY the Chinese translation. Keep technical product names in original English
(e.g., Coze, FastGPT, GPT, Claude, Cursor, ByteDance). Keep tone concise & factual."""




def _is_chinese(text: str) -> bool:
    """Detect CJK Unified Ideographs (U+4E00-9FFF basic block)."""
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def translate(text):
    r = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": text}],
        max_tokens=400,
    )
    return r.choices[0].message.content.strip()


def main():
    with get_session() as s:
        signals = s.query(Signal).filter(Signal.finding.isnot(None), Signal.finding != "").all()
        pending = [x for x in signals if not _is_chinese(x.finding or "")]
        skipped = len(signals) - len(pending)
        print(f"[scan] total={len(signals)} pending={len(pending)} skipped_CN={skipped}")
        ok = bad = 0
        for i, sig in enumerate(pending):
            try:
                sig.finding = translate(sig.finding)
                ok += 1
            except Exception as e:
                bad += 1
                print(f"  [{i+1}/{len(pending)}] FAIL  {type(e).__name__}: {str(e)[:160]}")
                continue
            if (i + 1) % 3 == 0 or i == len(pending) - 1:
                try:
                    s.commit()
                except Exception as e:
                    print(f"  commit err {i+1}: {e}")
                    s.rollback()
            print(f"  [{i+1}/{len(pending)}] OK")
        print(f"[done] ok={ok} fail={bad}")


if __name__ == "__main__":
    main()