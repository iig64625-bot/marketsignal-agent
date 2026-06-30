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

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """You are a translation expert for competitive intelligence.
Translate the given English signal ''finding'' to Chinese (??).
Output ONLY the Chinese translation. Keep technical product names in original English
(e.g., Coze, FastGPT, GPT, Claude, Cursor, ByteDance). Keep tone concise & factual."""


def translate(text):
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": text}],
        max_tokens=400,
    )
    return r.choices[0].message.content.strip()


def main():
    with get_session() as s:
        signals = s.query(Signal).filter(Signal.finding.isnot(None), Signal.finding != "").all()
        print(f"Translating {len(signals)} signals...")
        for i, sig in enumerate(signals):
            try:
                sig.finding = translate(sig.finding)
                if (i + 1) % 10 == 0:
                    s.commit()
                    print(f"  {i+1}/{len(signals)} done")
            except Exception as e:
                print(f"  {i+1} failed: {e}")
                s.rollback()
        s.commit()
        print(f"All {len(signals)} translated")


if __name__ == "__main__":
    main()