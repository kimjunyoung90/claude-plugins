#!/usr/bin/env python3
"""진행 중 할 일과 그 일을 맡은 Orca 세션 상태를 한눈에 본다 — /check 가 부른다.

    check.py                 진행 중(in_progress) 할 일마다 세션 상태·마지막 보고 첫 줄 + 할 일 밖 세션
    check.py 3               그 건만 (번호 · 할 일 id · 티켓 키) — 마지막 보고 전문 포함

세션 찾기 (하나라도 걸리면 그 건의 세션):
  1. 에이전트 프롬프트의 「이 작업은 KEY 건이다」 — /start 가 넣는 첫 지시
  2. Orca 워크트리에 연결된 지라 이슈(linkedItems) — Orca 화면에서 직접 연결한 경우
  3. ticket_link.py bind 가 남긴 연결 파일 → 그 세션 기록 폴더(작업 경로)

읽기만 한다. 할 일·세션 어느 쪽도 바꾸지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import todo as todo_mod  # 같은 scripts/ 폴더 — 할 일 읽기·번호 기준은 todo.py 하나로
from ticket_link import PROJECTS_DIR, links

TICKET_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,7})\b")
HEADLINE_LEN = 100

# Orca 에이전트 state → 보고용 상태. 목록에 없는 state(waiting·blocked 등)는 needs_input
STATUS_LABEL = {
    "working": "작업 중",
    "reported": "보고 완료 — 확인 필요",
    "needs_input": "입력 대기",
    "interrupted": "중단됨",
    "closed": "터미널 닫힘",
    "no_session": "세션 없음",
}


def load_worktrees() -> list[dict]:
    try:
        proc = subprocess.run(["orca", "worktree", "ps", "--json"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"orca worktree ps 실행 실패 — {exc}. Orca 가 켜져 있는지 확인하세요 (orca status)")
    if proc.returncode != 0:
        raise SystemExit(f"orca worktree ps 실패 (코드 {proc.returncode}): {proc.stderr.strip()[:300]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"orca worktree ps 출력 파싱 실패 — {exc}")
    if not data.get("ok", True):
        raise SystemExit(f"orca worktree ps 오류: {data.get('error')}")
    return (data.get("result") or {}).get("worktrees") or []


def encode_path(path: str) -> str:
    """Claude Code 가 세션 기록 폴더 이름을 만드는 방식 — 영숫자 외는 '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def bound_tickets_by_path() -> dict[str, set[str]]:
    """세션 기록 폴더 이름(작업 경로) → 그 폴더 세션들이 bind 한 티켓."""
    out: dict[str, set[str]] = {}
    if not PROJECTS_DIR.is_dir():
        return out
    folders = [p for p in PROJECTS_DIR.iterdir() if p.is_dir()]
    for session_id, issue in links().items():
        for folder in folders:
            if (folder / f"{session_id}.jsonl").exists():
                out.setdefault(folder.name, set()).add(issue)
    return out


def main_agent(wt: dict) -> dict | None:
    """최상위 에이전트 중 가장 최근 것. 서브에이전트 상태는 부모가 대신한다."""
    agents = [a for a in wt.get("agents") or [] if not a.get("parentPaneKey")]
    return max(agents, key=lambda a: a.get("updatedAt") or 0, default=None)


def status_of(wt: dict, agent: dict | None) -> str:
    if not wt.get("liveTerminalCount"):
        return "closed"
    if agent is None:
        return "no_session"
    if agent.get("interrupted"):
        return "interrupted"
    state = agent.get("state")
    if state == "working":
        return "working"
    if state == "done":
        return "reported"
    return "needs_input"


def headline(message: str | None) -> str:
    for line in (message or "").splitlines():
        text = line.strip().lstrip("#>-* ").replace("**", "").strip()
        if text:
            return text if len(text) <= HEADLINE_LEN else text[:HEADLINE_LEN - 1] + "…"
    return ""


def wt_name(wt: dict) -> str:
    return Path(wt.get("path") or "").name or wt.get("displayName") or "?"


def prompt_tickets(wt: dict) -> set[str]:
    found = set()
    for a in wt.get("agents") or []:
        for m in TICKET_PATTERN.finditer(a.get("prompt") or ""):
            found.add(m.group(1).upper())
    return found


def wt_tickets(wt: dict, bound: dict[str, set[str]]) -> set[str]:
    linked = {i.get("jiraIdentifier") for i in wt.get("linkedItems") or [] if i.get("jiraIdentifier")}
    return prompt_tickets(wt) | linked | bound.get(encode_path(wt.get("path") or ""), set())


def current_step(agent: dict | None) -> str:
    """작업 중이면 지난 보고보다 지금 하는 일이 맞다 — 실행 중인 도구와 입력 앞부분."""
    tool = (agent or {}).get("toolName")
    if not tool:
        return ""
    arg = " ".join(((agent or {}).get("toolInput") or "").split())
    return headline(f"{tool}: {arg}" if arg else tool)


def session_view(wt: dict, *, full: bool) -> dict:
    agent = main_agent(wt)
    message = (agent or {}).get("lastAssistantMessage") or ""
    status = status_of(wt, agent)
    view = {
        "worktree": wt_name(wt),
        "display": wt.get("displayName"),
        "repo": wt.get("repo"),
        "path": wt.get("path"),
        "status": status,
        "agent_state": (agent or {}).get("state"),
        "since": (agent or {}).get("stateStartedAt") or wt.get("lastOutputAt"),
        "headline": (current_step(agent) if status == "working" else "") or headline(message),
    }
    if full:
        view["message"] = message
        view["prompt"] = (agent or {}).get("prompt")
    return view


def build(records: list[dict], worktrees: list[dict], bound: dict[str, set[str]], ref: str | None) -> dict:
    rows = todo_mod.active_rows(records)
    numbered = [(n, r) for n, r in enumerate(rows, 1) if r["state"] == "in_progress"]
    if ref:
        target = todo_mod.find(records, ref)
        numbered = [(n, r) for n, r in numbered if r["id"] == target["id"]] or [(None, target)]
    sessions = [wt for wt in worktrees if wt.get("agents")]
    tickets = {id(wt): wt_tickets(wt, bound) for wt in sessions}
    matched: set[int] = set()
    items = []
    for no, rec in numbered:
        hits = [wt for wt in sessions if rec.get("jira") and rec["jira"] in tickets[id(wt)]]
        matched.update(id(wt) for wt in hits)
        views = [session_view(wt, full=bool(ref)) for wt in hits]
        items.append({"no": no, "id": rec["id"], "jira": rec.get("jira"), "title": rec["title"],
                      "status": views[0]["status"] if len(views) == 1 else ("no_session" if not views else "multi"),
                      "sessions": views})
    unmatched = []
    if not ref:
        for wt in sessions:
            if id(wt) in matched or wt.get("isMainWorktree"):
                continue
            view = session_view(wt, full=False)
            view["ticket"] = ", ".join(sorted(tickets[id(wt)])) or None
            unmatched.append(view)
    return {"items": items, "unmatched": unmatched}


def fmt_time(ms: int | None) -> str:
    if not ms:
        return "-"
    at = datetime.fromtimestamp(ms / 1000)
    return at.strftime("%H:%M") if at.date() == datetime.now().date() else at.strftime("%m-%d %H:%M")


def render_session(s: dict, indent: str, tag: str = "") -> list[str]:
    name = s["worktree"] if s.get("display") in (None, s["worktree"]) else f"{s['worktree']} ({s['display']})"
    name += tag
    lines = [f"{indent}{name} · {STATUS_LABEL.get(s['status'], s['status'])} · {fmt_time(s.get('since'))}"]
    if "message" in s:
        lines.append(f"{indent}  지시: {(s.get('prompt') or '').strip()[:200]}")
        lines += [f"{indent}  {line}" for line in (s.get("message") or "(보고 없음)").splitlines()]
    elif s.get("headline"):
        lines.append(f"{indent}  └ {s['headline']}")
    return lines


def render(out: dict) -> str:
    lines = []
    for item in out["items"]:
        no = f"{item['no']}." if item["no"] else "-"
        lines.append(f"{no} {item.get('jira') or '(티켓 없음)'} {item['title']}")
        if not item["sessions"]:
            lines.append(f"   {STATUS_LABEL['no_session']}")
        for s in item["sessions"]:
            lines += render_session(s, "   ")
    if not out["items"]:
        lines.append("진행 중인 할 일이 없습니다.")
    if out["unmatched"]:
        lines += ["", "할 일에 안 걸린 세션:"]
        for s in out["unmatched"]:
            lines += render_session(s, "   ", f" [{s.get('ticket') or '티켓 없음'}]")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="진행 중 할 일 ↔ Orca 세션 상태")
    parser.add_argument("ref", nargs="?", help="번호 · 할 일 id · 티켓 키 — 그 건만, 보고 전문 포함")
    args = parser.parse_args()
    print(render(build(todo_mod.load(), load_worktrees(), bound_tickets_by_path(), args.ref)))


if __name__ == "__main__":
    main()
