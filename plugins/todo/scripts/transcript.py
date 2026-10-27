"""세션 기록(트랜스크립트, ~/.claude/projects/<경로>/<세션id>.jsonl) 읽기 — work-extract.py · check.py 가 같이 쓴다.

사람이 입력한 요청과 Claude 의 답변, subagent 보고만 골라낸다. 그 밖의 도구 결과·생각 과정·훅·시스템 안내는 뺀다.
"""
from __future__ import annotations

import json
import re
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


SUBAGENT_TOOLS = ("Agent", "Task")   # subagent 를 부르는 도구 — 이름이 바뀐 적이 있어 둘 다 본다


def subagent_reports(rec: dict, calls: set[str]) -> list[str]:
    """도구 결과 중 subagent 가 돌려준 보고만. 조사 결과를 요약한 글이라 작고 판단 근거가 많다.

    백그라운드 subagent 는 도구 결과가 「시작했다」 안내뿐이고, 보고는 끝날 때 오는 알림(task-notification)의 <result> 에 있다.
    """
    content = (rec.get("message") or {}).get("content")
    if (rec.get("origin") or {}).get("kind") == "task-notification":
        if not isinstance(content, str):
            return []
        use = re.search(r"<tool-use-id>(.*?)</tool-use-id>", content)
        result = re.search(r"<result>(.*?)</result>", content, re.S)
        return [result.group(1).strip()] if use and use.group(1) in calls and result and result.group(1).strip() else []
    out = []
    for b in content if isinstance(content, list) else []:
        if not (isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in calls):
            continue
        content = b.get("content")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
        # 백그라운드로 띄운 subagent 의 「시작했다」 안내는 보고가 아니다
        if isinstance(content, str) and content.strip() and not content.startswith("Async agent launched"):
            out.append(content)
    return out


def turns(transcript: Path) -> list[dict]:
    """요청 하나와 그 요청에 대한 답변 전부(중간 답변·subagent 보고 포함)를 한 묶음으로.

    다른 도구 결과는 넣지 않는다 — 기록 용량 대부분이고, 알아낸 것은 답변에 요약돼 있다.
    """
    out: list[dict] = []
    calls: set[str] = set()   # subagent 호출의 tool_use id — 그 결과가 보고다
    for line in transcript.open(encoding="utf-8"):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("timestamp")
        if not ts or rec.get("isSidechain"):
            continue
        if rec.get("type") == "user":
            if text := prompt_text(rec):
                day, hm = local_day(ts)
                out.append({"day": day, "time": hm, "prompt": text, "answers": []})
            elif out:
                out[-1]["answers"] += [f"(subagent 보고)\n{r}" for r in subagent_reports(rec, calls)]
        elif rec.get("type") == "assistant":
            for b in (rec.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in SUBAGENT_TOOLS:
                    calls.add(b.get("id"))
            if out and (text := answer_text(rec)):
                out[-1]["answers"].append(text)
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
