#!/usr/bin/env python3
"""진행 중 할 일과 그 일을 맡은 세션 상태를 한눈에 본다 — /check 가 부른다.

    check.py                 진행 중(in_progress) 할 일마다 세션이 지금 무엇을 하는지 한 줄 · 마지막 보고 첫 줄
    check.py 3               그 건만 (번호 · 할 일 id · 티켓 키) — 마지막 보고 전문 포함

실행 환경(Orca · bg)과 상관없이 같은 방법으로 본다.
  세션 목록   `claude agents --json --all` — Orca 터미널 세션(interactive)과 bg 세션(background)이 모두 나온다.
              status 는 busy(작업 중) · waiting(waitingFor: permission prompt | input needed) · idle(턴을 마침)
  티켓 연결   ticket_link.py 연결 파일 (세션 id → 티켓)
  보고 내용   그 세션의 기록 파일 (transcript.py)
목록에 없는 세션(종료됨)도 연결 파일과 기록이 남아 있으면 마지막 보고를 보여 준다.

읽기만 한다. 할 일·세션 어느 쪽도 바꾸지 않는다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime

import todo as todo_mod  # 같은 scripts/ 폴더 — 할 일 읽기·번호 기준은 todo.py 하나로
from ticket_link import find_transcript, links
from transcript import last_state

HEADLINE_LEN = 100

# 작업 중일 때 마지막 도구로 지금 하는 일을 말한다
RESEARCH_TOOLS = {"Read", "Grep", "Glob", "LS", "WebSearch", "WebFetch", "LSP", "ToolSearch"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BUSY_LABEL = {"Bash": "명령을 실행하고 있습니다", "Agent": "서브에이전트에게 맡긴 일을 기다리고 있습니다",
              "Task": "서브에이전트에게 맡긴 일을 기다리고 있습니다", "AskUserQuestion": "질문을 준비하고 있습니다",
              "SendMessage": "다른 세션에 메시지를 보내고 있습니다"}


def load_agents() -> list[dict]:
    try:
        proc = subprocess.run(["claude", "agents", "--json", "--all"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"claude agents 실행 실패 — {exc}")
    if proc.returncode != 0:
        raise SystemExit(f"claude agents 실패 (코드 {proc.returncode}): {proc.stderr.strip()[:300]}")
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"claude agents 출력 파싱 실패 — {exc}")


def headline(message: str | None) -> str:
    for line in (message or "").splitlines():
        text = line.strip().lstrip("#>-* ").replace("**", "").strip()
        if text:
            return text if len(text) <= HEADLINE_LEN else text[:HEADLINE_LEN - 1] + "…"
    return ""


def fmt_time(iso: str | None) -> str:
    if not iso:
        return "-"
    at = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    return at.strftime("%H:%M") if at.date() == datetime.now().date() else at.strftime("%m-%d %H:%M")


def tool_detail(tool: dict | None) -> str:
    if not tool:
        return ""
    args = tool["input"]
    if tool["name"] == "AskUserQuestion":
        questions = args.get("questions") or [{}]
        return questions[0].get("question", "")
    detail = (args.get("description") or args.get("file_path") or args.get("command") or args.get("pattern")
              or args.get("query") or args.get("url") or args.get("prompt") or "")
    return headline(str(detail))


def activity(status: str, waiting_for: str | None, tool: dict | None) -> str:
    """세션이 지금 무엇을 하고 있는지 한 문장으로."""
    if status == "closed":
        return "세션이 종료됐습니다"
    if status == "idle":
        return "일을 마치고 다음 지시를 기다리고 있습니다"
    if status == "waiting":
        what = waiting_for or ""
        label = ("승인을 기다리고 있습니다" if "permission" in what else
                 "입력을 기다리고 있습니다" if "input" in what else f"기다리고 있습니다 ({what or '이유 모름'})")
    elif status == "busy":
        name = (tool or {}).get("name")
        label = ("답을 정리하고 있습니다" if not name else
                 "자료를 조사하고 있습니다" if name in RESEARCH_TOOLS else
                 "파일을 고치고 있습니다" if name in EDIT_TOOLS else
                 BUSY_LABEL.get(name) or f"{name} 도구를 쓰고 있습니다")
    else:
        return status
    detail = tool_detail(tool)
    return f"{label} — {detail}" if detail else label


def session_view(sid: str, agent: dict | None, *, full: bool) -> dict:
    path = find_transcript(sid)
    state = last_state(path) if path else {"answer": None, "at": None, "tool": None}
    # 살아 있는 세션은 status 가 busy·waiting·idle 이다. 멈춘 bg 세션은 목록에 남아도 status 가 비어 있다
    status = (agent or {}).get("status") or "closed"
    view = {
        "session": sid,
        "name": (agent or {}).get("name"),
        "id": (agent or {}).get("id"),
        "kind": (agent or {}).get("kind"),
        "status": status,
        "at": state["at"],
        "doing": activity(status, (agent or {}).get("waitingFor"), state["tool"] if status in ("busy", "waiting") else None),
        "headline": headline(state["answer"]) if status in ("idle", "closed") else "",
    }
    if full:
        view["message"] = state["answer"]
    return view


def build(records: list[dict], agents: list[dict], bound: dict[str, str], ref: str | None) -> list[dict]:
    rows = todo_mod.active_rows(records)
    numbered = [(n, r) for n, r in enumerate(rows, 1) if r["state"] == "in_progress"]
    if ref:
        target = todo_mod.find(records, ref)
        numbered = [(n, r) for n, r in numbered if r["id"] == target["id"]] or [(None, target)]
    live = {a.get("sessionId"): a for a in agents if a.get("sessionId")}
    items = []
    for no, rec in numbered:
        sids = [sid for sid, key in bound.items() if rec.get("jira") and key == rec["jira"].upper()]
        views = [session_view(sid, live.get(sid), full=bool(ref)) for sid in sids]
        # 살아 있는 세션을 앞에, 종료된 세션은 가장 최근 것 하나만
        running = [v for v in views if v["status"] != "closed"]
        closed = sorted((v for v in views if v["status"] == "closed"), key=lambda v: v["at"] or "", reverse=True)[:1]
        views = running or closed
        items.append({"no": no, "id": rec["id"], "jira": rec.get("jira"), "title": rec["title"],
                      "status": views[0]["status"] if len(views) == 1 else ("no_session" if not views else "multi"),
                      "sessions": views})
    return items


def render_session(s: dict, indent: str) -> list[str]:
    who = s["name"] or s["session"][:8]
    where = {"background": f" · claude attach {s['id']}", "interactive": " · 터미널(Orca 등)에서 실행 중"}.get(s["kind"] or "", "")
    lines = [f"{indent}{who} · {fmt_time(s['at'])}{where}", f"{indent}  ▶ {s['doing']}"]
    if "message" in s and s.get("message") and s["status"] in ("idle", "closed"):
        lines.append(f"{indent}  마지막 보고:")
        lines += [f"{indent}    {line}" for line in s["message"].splitlines()]
    elif s.get("headline"):
        lines.append(f"{indent}  └ 보고: {s['headline']}")
    return lines


def render(items: list[dict]) -> str:
    lines = []
    for item in items:
        no = f"{item['no']}." if item["no"] else "-"
        lines.append(f"{no} {item.get('jira') or '(티켓 없음)'} {item['title']}")
        if not item["sessions"]:
            lines.append("   ▶ 연결된 세션이 없습니다")
        for s in item["sessions"]:
            lines += render_session(s, "   ")
    return "\n".join(lines) or "진행 중인 할 일이 없습니다."


def main() -> None:
    parser = argparse.ArgumentParser(description="진행 중 할 일 ↔ 작업 세션 상태")
    parser.add_argument("ref", nargs="?", help="번호 · 할 일 id · 티켓 키 — 그 건만, 보고 전문 포함")
    args = parser.parse_args()
    print(render(build(todo_mod.load(), load_agents(), links(), args.ref)))


if __name__ == "__main__":
    main()
