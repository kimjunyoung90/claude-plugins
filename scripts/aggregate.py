"""Claude Code 세션 기록(트랜스크립트)을 지라 작업 내역(worklog) 페이로드로 집계한다 — 날짜별 1건씩.
worklog-update.py 가 build_entries() 를 부른다.

세션 기록(~/.claude/projects/<경로>/<세션id>.jsonl)에 시각·도구 호출·파일 경로가 이미 전부 남는다.
같은 걸 따로 적을 이유가 없어 여기서 직접 읽는다.

시간은 이벤트 사이 간격의 합으로 잡는다. idle_gap 보다 긴 공백은 자리를 비운 것으로 보고
통째로 뺀다. 그래야 점심 먹고 온 2시간이 작업시간으로 둔갑하지 않는다.
작업 시간에는 모든 도구 호출을 넣는다. 조사 세션은 MCP 도구만 쓰는 구간이 길어, 빼면 유휴 기준에 걸린다.

**날짜별로 쪼갠다.** 세션 하나가 며칠씩 이어지는 게 흔한데, 통째로 1건을 올리면
첫날에 시간이 몰리고 나머지 날은 기록이 빈다. 그래서 달력 날짜가 집계 단위다.

**이미 올린 날은 posted 로 빼낸다.** 세션을 이어 쓰면 기록 전체를 매번 다시 읽으므로,
빼지 않으면 같은 날이 중복 등록된다. 같은 날에 작업이 더 쌓였으면 차이만큼만 올린다.

**파일을 고치지 않은 세션도 올린다.** 확인 요청·조사·회신도 티켓 업무다.
"""

import json
import os
from datetime import datetime, timezone

# 마지막 이벤트도 순간이 아니므로 꼬리 시간을 얹는다
TAIL_SECONDS = 60
MAX_FILES = 20

EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Claude 설정·스크래치패드 편집은 업무 기록이 아니다
EXCLUDED_PREFIXES = (
    os.path.expanduser("~/.claude/"),
    "/private/tmp/claude-",
    "/tmp/claude-",
)

# 토큰·키·비밀번호 등 민감 파일은 작업 내역의 수정 파일 목록에서 제외한다
SENSITIVE_PATTERNS = (
    ".env", ".key", ".pem", ".p12", ".pfx", "id_rsa", "id_ed25519", "credentials", "secret"
)


def is_sensitive_path(path: str) -> bool:
    name = os.path.basename(path).lower()
    return any(p in name for p in SENSITIVE_PATTERNS)


def parse_ts(raw):
    """트랜스크립트의 ISO8601(Z) 타임스탬프를 epoch 초로."""
    if not raw:
        return None
    try:
        return int(
            datetime.fromisoformat(raw.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .timestamp()
        )
    except (ValueError, AttributeError):
        return None


def is_user_prompt(entry):
    """사용자가 실제로 친 메시지인지.

    tool_result 도 type=='user' 로 들어오기 때문에 구분이 필요하다.
    문자열 content 나 text 블록으로 시작하면 실제 프롬프트, tool_result 블록이면 도구 응답이다.
    """
    if entry.get("type") != "user":
        return False
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list) and content:
        return content[0].get("type") == "text"
    return False


def tool_uses(entry):
    if entry.get("type") != "assistant":
        return []
    content = entry.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    return [c for c in content if isinstance(c, dict) and c.get("type") == "tool_use"]


def read_events(path):
    """트랜스크립트에서 시각이 찍힌 활동만 뽑아낸다."""
    events = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue

                ts = parse_ts(entry.get("timestamp"))
                if ts is None:
                    continue
                cwd = entry.get("cwd", "")

                if is_user_prompt(entry):
                    events.append({"ts": ts, "kind": "prompt", "cwd": cwd})
                    continue

                for call in tool_uses(entry):
                    name = call.get("name")
                    args = call.get("input") or {}
                    if name in EDIT_TOOLS:
                        target = args.get("file_path") or args.get("notebook_path")
                        if (
                            target
                            and not target.startswith(EXCLUDED_PREFIXES)
                            and not is_sensitive_path(target)
                        ):
                            events.append(
                                {"ts": ts, "kind": "edit", "detail": target, "cwd": cwd}
                            )
                        else:
                            events.append({"ts": ts, "kind": "tool", "cwd": cwd})
                    elif name:
                        # Bash 및 기타 도구 호출도 일한 시간으로 잡는다. 명령어 원문은 코멘트에 남기지 않는다.
                        events.append({"ts": ts, "kind": "tool", "cwd": cwd})
    except OSError:
        return []
    events.sort(key=lambda e: e["ts"])
    return events


def active_seconds(events, idle_gap):
    """유휴 구간을 제외한 실작업 시간."""
    total = 0
    for prev, curr in zip(events, events[1:]):
        gap = curr["ts"] - prev["ts"]
        if 0 < gap <= idle_gap:
            total += gap
    return total + TAIL_SECONDS if events else 0


def shorten(path, cwd):
    """리포 기준 상대경로로 줄인다. 밖이면 홈 기준 ~ 표기."""
    if cwd and path.startswith(cwd.rstrip("/") + "/"):
        return path[len(cwd.rstrip("/")) + 1:]
    home = os.path.expanduser("~")
    if path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path


def dedupe(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def group_by_day(events):
    """로컬 달력 날짜별로 이벤트를 묶는다. 집계 단위가 날짜이므로 여기서 갈린다."""
    days = {}
    for event in events:
        key = datetime.fromtimestamp(event["ts"]).strftime("%Y-%m-%d")
        days.setdefault(key, []).append(event)
    return days


def build_comment(events, seconds, day_index, day_total, is_extra):
    cwd = next((e.get("cwd") for e in reversed(events) if e.get("cwd")), "")
    files = dedupe(
        shorten(e["detail"], cwd) for e in events if e.get("kind") == "edit" and e.get("detail")
    )

    lines = ["h4. Claude Code 작업 기록", ""]

    if files:
        lines.append("*수정 파일* ({}건)".format(len(files)))
        lines += ["* {}".format(f) for f in files[:MAX_FILES]]
        if len(files) > MAX_FILES:
            lines.append("* _… 외 {}건_".format(len(files) - MAX_FILES))
        lines.append("")

    # 같은 날 안의 구간이므로 끝 시각에는 날짜를 붙이지 않는다
    start = datetime.fromtimestamp(events[0]["ts"])
    end = datetime.fromtimestamp(events[-1]["ts"])
    notes = ""
    if day_total > 1:
        notes += " · 세션 {}일 중 {}일째".format(day_total, day_index)
    if is_extra:
        notes += " · 같은 날 추가분"
    lines.append(
        "_{} ~ {} · 유휴 제외 {}분{} · Claude Code 자동 기록_".format(
            start.strftime("%Y-%m-%d %H:%M"),
            end.strftime("%H:%M"),
            round(seconds / 60),
            notes,
        )
    )
    return "\n".join(lines)


def build_entries(transcript, idle_gap, min_seconds, posted):
    """날짜별 작업 내역 [{day, total_seconds, payload}]. 올릴 게 없으면 빈 목록.
    posted 는 {날짜: 이미 올린 초} — worklog-update.py 의 장부."""
    events = read_events(transcript)
    if not events:
        return []

    days = group_by_day(events)
    ordered = sorted(days)

    entries = []
    for index, day in enumerate(ordered, start=1):
        day_events = days[day]
        total = active_seconds(day_events, idle_gap)

        # 이미 올린 만큼은 빼고 차이만 올린다 — 중복 등록 방지
        already = posted.get(day, 0)
        remaining = total - already
        if remaining < min_seconds:
            continue

        # Jira 는 60초 미만을 받지 않는다
        seconds = max(60, round(remaining / 60) * 60)
        started = datetime.fromtimestamp(day_events[0]["ts"]).astimezone()

        entries.append(
            {
                "day": day,
                # 성공 시 호출부가 장부에 적을 누적값. 다음 실행의 posted 가 된다.
                "total_seconds": total,
                "payload": {
                    "timeSpentSeconds": seconds,
                    "started": started.strftime("%Y-%m-%dT%H:%M:%S.000%z"),
                    "comment": build_comment(
                        day_events, seconds, index, len(ordered), already > 0,
                    ),
                },
            }
        )

    return entries
