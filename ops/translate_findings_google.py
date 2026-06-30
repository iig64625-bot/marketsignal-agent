"""ops/translate_findings_google.py - 免 key 翻译 signal.findings (Google gtx + MyMemory fallback)."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from signalpulse.db.session import get_session
from signalpulse.models import Signal


def is_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def _google(text, target="zh-CN"):
    params = {"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text}
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    cn = "".join(seg[0] for seg in data[0] if seg[0])
    if cn and any("\u4e00" <= ch <= "\u9fff" for ch in cn):
        return cn
    raise RuntimeError("google returned no zh")


def _mymemory(text, target="zh-CN"):
    params = {"q": text, "langpair": f"en|{target}"}
    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    cn = data["responseData"]["translatedText"]
    if cn and any("\u4e00" <= ch <= "\u9fff" for ch in cn):
        return cn
    raise RuntimeError("mymemory returned no zh")


def translate(text, target="zh-CN"):
    for name, fn in (("google", _google), ("mymemory", _mymemory)):
        try:
            return fn(text, target), name
        except Exception:
            continue
    raise RuntimeError("all providers failed")


def main():
    with get_session() as s:
        signals = (
            s.query(Signal)
            .filter(Signal.finding.isnot(None), Signal.finding != "")
            .all()
        )
        pending = [x for x in signals if not is_chinese(x.finding or "")]
        skipped = len(signals) - len(pending)
        print(f"[scan] total={len(signals)} pending={len(pending)} skipped_CN={skipped}")
        ok = bad = 0
        last_prov = "-"
        for i, sig in enumerate(pending):
            try:
                cn, last_prov = translate(sig.finding)
                sig.finding = cn
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
        print(f"[done] ok={ok} fail={bad} provider={last_prov}")


if __name__ == "__main__":
    main()