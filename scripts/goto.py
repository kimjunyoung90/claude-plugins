#!/usr/bin/env python3
"""할 일 하나의 작업 세션으로 간다 — /todo 화면에서 Enter 가 부른다.

    goto.py <ref> [--switch]

    ref       번호 · 할 일 id(T-NNNN) · 티켓 키
    --switch  Orca 세션이면 Orca 화면을 그 세션 탭으로 바꾼다 (없으면 찾기만 한다)

결과는 JSON 한 줄이다.
  {"action": "start", "no": N}            아직 시작하지 않은 할 일 — /start N 으로 시작한다
  {"action": "orca", "title": "..."}      Orca 터미널에서 도는 작업 세션 — 그 탭으로 옮겼다(--switch)
  {"action": "bg", "id": "..."}           bg 세션 — 같은 창으로는 옮길 수 없어 claude attach <id> 로 들어간다
  {"action": "none", "reason": "..."}     갈 세션이 없다

세션 찾기는 check.py 와 같다: 티켓 → 연결된 세션(ticket_link) → `claude agents` 의 살아 있는 세션.
Orca 탭은 세션의 작업 폴더와 같은 폴더의 Orca 터미널이다. 여럿이면 제목에 티켓 키가 있는 것을 고른다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import todo as todo_mod  # 같은 scripts/ 폴더
from check import load_agents
from ticket_link import links


def orca_terminals() -> list[dict]:
    try:
        proc = subprocess.run(["orca", "terminal", "list", "--json"], capture_output=True, text=True, timeout=15)
        result = json.loads(proc.stdout or "{}").get("result") or {}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    return result.get("terminals", []) if isinstance(result, dict) else result


def same_dir(a: str | None, b: str | None) -> bool:
    return bool(a and b) and os.path.realpath(a) == os.path.realpath(b)


def find_tab(cwd: str, key: str) -> dict | None:
    tabs = [t for t in orca_terminals() if t.get("connected") and same_dir(t.get("worktreePath"), cwd)]
    return next((t for t in tabs if key in (t.get("title") or "")), tabs[0] if tabs else None)


def switch(handle: str) -> bool:
    try:
        proc = subprocess.run(["orca", "terminal", "switch", "--terminal", handle, "--json"],
                              capture_output=True, text=True, timeout=15)
        return proc.returncode == 0 and json.loads(proc.stdout or "{}").get("ok") is not False
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def decide(ref: str, do_switch: bool) -> dict:
    records = todo_mod.load()
    rec = todo_mod.find(records, ref)
    if rec["state"] == "todo":
        rows = todo_mod.active_rows(records)
        no = next((n for n, r in enumerate(rows, 1) if r["id"] == rec["id"]), None)
        return {"action": "start", "no": no}
    key = (rec.get("jira") or "").upper()
    if not key:
        return {"action": "none", "reason": "티켓이 없는 할 일이다"}
    sids = {sid for sid, k in links().items() if k == key}
    live = [a for a in load_agents() if a.get("sessionId") in sids and a.get("status")]
    if not live:
        return {"action": "none", "reason": f"{key} 에 연결된 세션이 없거나 모두 끝났다"}
    agent = max(live, key=lambda a: a.get("startedAt") or 0)
    if agent.get("kind") == "background":
        return {"action": "bg", "id": agent.get("id"), "name": agent.get("name")}
    tab = find_tab(agent.get("cwd") or "", key)
    if not tab:
        return {"action": "none", "reason": "세션이 Orca 밖 터미널에서 돌고 있다"}
    if do_switch and not switch(tab["handle"]):
        return {"action": "none", "reason": "Orca 탭 전환에 실패했다"}
    return {"action": "orca", "title": (tab.get("title") or "").lstrip("◐◑◒◓✳✶·* ").strip() or Path(agent.get("cwd") or "").name}


def main() -> None:
    parser = argparse.ArgumentParser(description="할 일의 작업 세션으로 가기")
    parser.add_argument("ref", help="번호 · 할 일 id · 티켓 키")
    parser.add_argument("--switch", action="store_true", help="Orca 세션이면 그 탭으로 옮긴다")
    args = parser.parse_args()
    try:
        out = decide(args.ref, args.switch)
    except SystemExit as exc:  # todo.find · load_agents 의 실패 메시지
        out = {"action": "none", "reason": str(exc)}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
