#!/usr/bin/env python3
"""세션 기록(트랜스크립트)에서 정리 재료만 추린다 — 사용자 요청과, 요청마다 마지막 답변.

    work-extract.py --issue <KEY>                          그 티켓에 연결된 세션, 금일
    work-extract.py --issue <KEY> --from YYYY-MM-DD [--to YYYY-MM-DD]   그 기간

도구 결과·생각 과정·작업 중 진행 안내는 뺀다. 트랜스크립트 용량 대부분이 도구 결과이고,
그 결과로 알아낸 것은 답변에 이미 요약돼 있다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from ticket_link import find_transcript, sessions_for  # 같은 scripts/ 폴더

MAX_PROMPT = 1000   # 붙여넣은 긴 글이 재료를 덮지 않게 자른다
MAX_ANSWER = 2000


def clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + " …(생략)"


def local_day(ts: str) -> tuple[str, str]:
    """UTC ISO 시각 → (로컬 날짜, HH:MM)"""
    t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    return t.date().isoformat(), t.strftime("%H:%M")


def prompt_text(rec: dict) -> str | None:
    """사람이 직접 입력한 요청만. 도구 결과·훅·시스템 안내(<...>)·압축 요약은 None."""
    if rec.get("isMeta") or rec.get("isSidechain") or rec.get("isCompactSummary"):
        return None
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = [b.get("text", "") for b in content if b.get("type") == "text"]
    else:
        return None
    parts = [p for p in parts if p.strip() and not p.lstrip().startswith(("<", "[Request interrupted"))]
    return "\n".join(parts) if parts else None


def answer_text(rec: dict) -> str | None:
    if rec.get("isSidechain"):
        return None
    content = (rec.get("message") or {}).get("content") or []
    texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    text = "\n".join(t for t in texts if t.strip())
    return text or None


def turns(transcript: Path) -> list[dict]:
    """요청 하나와 그 요청에 대한 마지막 답변을 한 묶음으로."""
    out: list[dict] = []
    for line in transcript.open(encoding="utf-8"):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("timestamp")
        if not ts:
            continue
        if rec.get("type") == "user" and (text := prompt_text(rec)):
            day, hm = local_day(ts)
            out.append({"day": day, "time": hm, "prompt": text, "answer": None})
        elif rec.get("type") == "assistant" and out and (text := answer_text(rec)):
            out[-1]["answer"] = text   # 뒤에 오는 답변이 앞의 것을 덮는다 = 마지막 답변만 남는다
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--issue", required=True, help="티켓 키 — 연결 파일(jira/state/*.json)로 세션을 찾는다")
    ap.add_argument("--from", dest="since", default=None, help="YYYY-MM-DD (기본: 금일)")
    ap.add_argument("--to", dest="until", default=None, help="YYYY-MM-DD (기본: 금일)")
    args = ap.parse_args(argv)

    today = date.today().isoformat()
    since, until = args.since or today, args.until or today
    sessions = sessions_for(args.issue, auto_bind_current=True)
    if not sessions:
        print(f"세션이 없다 — {args.issue} 에 연결된 세션이 없음", file=sys.stderr)
        return 1

    by_day: dict[str, list[tuple[str, dict]]] = {}
    for sid in sessions:
        path = find_transcript(sid)
        if not path:
            print(f"(세션 기록 없음: {sid} — 보관 기간이 지났을 수 있다)", file=sys.stderr)
            continue
        for t in turns(path):
            if since <= t["day"] <= until:
                by_day.setdefault(t["day"], []).append((sid, t))

    if not by_day:
        print(f"{since} ~ {until} 기록 없음")
        return 0

    for day in sorted(by_day):
        print(f"## {day}")
        for sid, t in sorted(by_day[day], key=lambda x: x[1]["time"]):
            print(f"\n[{t['time']} · {sid[:8]}] 요청: {clip(t['prompt'], MAX_PROMPT)}")
            if t["answer"]:
                print(f"답변: {clip(t['answer'], MAX_ANSWER)}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
