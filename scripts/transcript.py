"""세션 기록(트랜스크립트, ~/.claude/projects/<경로>/<세션id>.jsonl) 읽기 — work-extract.py · check.py 가 같이 쓴다.

사람이 입력한 요청과 Claude 의 답변만 골라낸다. 도구 결과·생각 과정·훅·시스템 안내는 뺀다.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


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


def last_state(transcript: Path) -> dict:
    """기록의 마지막 모습 — 마지막 답변, 마지막 활동 시각, 마지막 줄이 도구 호출이면 그 도구 {name, input}(지금 하는 일)."""
    state: dict = {"answer": None, "at": None, "tool": None}
    for line in transcript.open(encoding="utf-8"):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not rec.get("timestamp") or rec.get("type") not in ("user", "assistant") or rec.get("isSidechain"):
            continue
        state["at"] = rec["timestamp"]
        if rec["type"] == "user":
            if prompt_text(rec):
                state["answer"] = None   # 새 요청이 오면 앞의 답변은 지난 보고다
            continue
        if text := answer_text(rec):
            state["answer"] = text
        uses = [b for b in (rec.get("message") or {}).get("content") or []
                if isinstance(b, dict) and b.get("type") == "tool_use"]
        state["tool"] = {"name": uses[-1].get("name"), "input": uses[-1].get("input") or {}} if uses else None
    return state
