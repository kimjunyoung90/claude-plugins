#!/usr/bin/env python3
"""세션 기록(트랜스크립트)에서 정리 재료를 추린다 — 사용자 요청과 그 요청의 답변 전부(중간 답변·subagent 보고 포함).

    work-extract.py --issue <KEY> --out <파일>                          그 티켓에 연결된 세션, 금일
    work-extract.py --issue <KEY> --out <파일> --from YYYY-MM-DD [--to YYYY-MM-DD]   그 기간

요청·답변은 자르지 않는다 — 판단 근거(수치·결정)는 긴 답변 뒷부분에 있는 경우가 많다.
도구 결과·생각 과정은 뺀다. 트랜스크립트 용량 대부분이 도구 결과이고,
그 결과로 알아낸 것은 답변에 이미 요약돼 있다. 재료가 길 수 있어 화면이 아니라 파일로 쓴다.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from ticket_link import find_transcript, sessions_for  # 같은 scripts/ 폴더
from transcript import turns

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--issue", required=True, help="티켓 키 — 연결 파일(jira/state/*.json)로 세션을 찾는다")
    ap.add_argument("--from", dest="since", default=None, help="YYYY-MM-DD (기본: 금일)")
    ap.add_argument("--to", dest="until", default=None, help="YYYY-MM-DD (기본: 금일)")
    ap.add_argument("--out", required=True, help="재료를 쓸 파일 — 화면에는 파일 위치와 크기만 찍는다")
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

    lines: list[str] = []
    for day in sorted(by_day):
        lines.append(f"## {day}")
        for sid, t in sorted(by_day[day], key=lambda x: x[1]["time"]):
            lines.append(f"\n[{t['time']} · {sid[:8]}] 요청: {t['prompt'].strip()}")
            lines += [f"답변: {a.strip()}" for a in t["answers"]]
        lines.append("")
    text = "\n".join(lines) + "\n"
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"{args.out} — {len(text):,}자, {text.count(chr(10)):,}줄")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
