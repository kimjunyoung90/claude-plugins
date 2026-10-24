#!/usr/bin/env python3
"""세션 ↔ 지라 티켓 연결. /start 가 새 세션 지시문에 넣어 Claude 가 호출하고, /finish 는 status 로 티켓을 찾는다.

    ticket_link.py bind <KEY>      이 세션을 그 티켓에 연결
    ticket_link.py status          연결 상태

세션은 Claude Code 가 Bash 에 넣어 주는 CLAUDE_CODE_SESSION_ID 로 정한다.
티켓이 지라에 실제로 있는지는 확인하지 않는다 — 티켓은 할 일을 추가할 때(/todo:add) 이미 만들어져 있다.

연결 파일은 jira/state/<세션>.json 이고 완료 뒤에도 지우지 않는다(기록으로 남긴다).
worklog-update.py · work-extract.py · check.py 가 여기 함수로 티켓의 세션과 세션 기록을 찾는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from todo import TODO_DATA_DIR  # 같은 scripts/ 폴더 — 데이터 위치는 todo.py 하나로 정한다

STATE_DIR = TODO_DATA_DIR / "jira/state"
PROJECTS_DIR = Path.home() / ".claude/projects"
KEY = re.compile(r"[A-Z][A-Z0-9]{1,9}-\d{1,7}")


def sanitize_id(session_id: str) -> str:
    """session_id 는 외부 입력이다. 경로로 쓰기 전에 거른다."""
    return re.sub(r"[^A-Za-z0-9_-]", "", session_id or "unknown")[:128]


def state_file(session_id: str) -> Path:
    return STATE_DIR / f"{sanitize_id(session_id)}.json"


def bind(session_id: str, key: str) -> bool:
    """세션을 티켓 키에 연결한다."""
    key = key.upper()
    if not KEY.fullmatch(key):
        return False
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    f = state_file(session_id)
    f.write_text(json.dumps({"issue": key, "bound_at": datetime.now().astimezone().isoformat(timespec="seconds")}),
                 encoding="utf-8")
    return True


def links() -> dict[str, str]:
    """연결 전부 {세션 id: 티켓 키}."""
    out = {}
    for f in sorted(STATE_DIR.glob("*.json")):
        try:
            issue = json.loads(f.read_text(encoding="utf-8")).get("issue")
        except (OSError, ValueError):
            continue
        if issue:
            out[f.stem] = issue.upper()
    return out


def sessions_for(issue: str, auto_bind_current: bool = False) -> list[str]:
    """그 티켓에 연결된 세션 — 한 티켓을 여러 세션이 나눠 작업한 경우 모두.
    연결된 세션이 없고 auto_bind_current 가 참이면 현재 세션(CLAUDE_CODE_SESSION_ID)을 자동 연결한다."""
    sids = [sid for sid, key in links().items() if key == issue.upper()]
    if not sids and auto_bind_current:
        cur_sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
        if cur_sid and bind(cur_sid, issue):
            return [cur_sid]
    return sids


def find_transcript(session_id: str) -> Path | None:
    return next(PROJECTS_DIR.glob(f"*/{sanitize_id(session_id)}.jsonl"), None)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    # 추측하지 않는다. 세션을 여럿 동시에 돌리면 "가장 최근 기록" 같은 추측은 엉뚱한 세션에 티켓을 붙인다.
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        print("세션을 특정하지 못했다. Claude Code 안에서 실행하라.", file=sys.stderr)
        return 1
    f = state_file(session_id)

    if cmd == "bind" and len(argv) == 2:
        key = argv[1].upper()
        if not bind(session_id, key):
            print(f"티켓 키 형식이 아니다: {argv[1]} — 사용법: ticket_link.py bind <KEY>", file=sys.stderr)
            return 1
        print(f"연결 완료: {key}\n이 세션의 작업은 {key} 건으로 기록된다.")
        return 0
    if cmd == "status" and len(argv) <= 1:
        try:
            link = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            link = {}
        if link.get("issue"):
            print(f"연결: {link['issue']}\n시각: {link.get('bound_at')}")
        else:
            print(f"연결된 티켓 없음 (session={session_id})")
        return 0
    print("사용법: ticket_link.py {bind <KEY>|status}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
