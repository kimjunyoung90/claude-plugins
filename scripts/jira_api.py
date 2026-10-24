"""지라 REST 접속 — jira-create.py · todo.py(상태 동기화) · worklog-update.py 가 같이 쓴다.

주소·계정은 환경변수 TODO_JIRA_URL · TODO_JIRA_USERNAME · TODO_JIRA_API_TOKEN 에서 읽고 출력하지 않는다.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

TIMEOUT_SEC = 20


class JiraError(RuntimeError):
    pass


def load_jira() -> tuple[str, str]:
    base = os.environ.get("TODO_JIRA_URL", "").rstrip("/")
    user, token = os.environ.get("TODO_JIRA_USERNAME"), os.environ.get("TODO_JIRA_API_TOKEN")
    if not base or not user or not token:
        raise JiraError("지라 주소·계정이 없습니다 (환경변수 TODO_JIRA_URL · TODO_JIRA_USERNAME · TODO_JIRA_API_TOKEN)")
    auth = base64.b64encode(f"{user}:{token}".encode()).decode()
    return base, auth


def call(base: str, auth: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{base}/rest/api/2/{path}", data=data,
                                 method="POST" if body is not None else "GET")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise JiraError(f"http {e.code} {path} — {error_text(e.read())}") from None
    return json.loads(raw) if raw else {}


def error_text(raw: bytes) -> str:
    """지라 오류 응답(errorMessages · errors)을 한 줄로. 형식이 아니면 앞부분만."""
    try:
        body = json.loads(raw)
    except ValueError:
        return raw.decode("utf-8", "replace")[:200]
    parts = list(body.get("errorMessages") or [])
    parts += [f"{k}: {v}" for k, v in (body.get("errors") or {}).items()]
    return " · ".join(parts) or str(body)[:200]


# ── 상태 전이 ──
# 전이 id 는 프로젝트마다 달라 고정하지 않고 statusCategory 로 고른다.
# 진행(indeterminate)은 진행으로 가는 전이를 하나 탄다. 이미 진행 중·완료면 그대로 둔다.
# 완료(done)는 완료로 가는 전이를 먼저, 없으면 진행 전이를 최대 MAX_HOPS 번 타며 완료를 찾는다.
MAX_HOPS = 3


def status_of(base: str, auth: str, key: str) -> tuple[str, str]:
    st = call(base, auth, f"issue/{key}?fields=status")["fields"]["status"]
    return st["name"], st.get("statusCategory", {}).get("key", "")


def _category(t: dict) -> str:
    return t.get("to", {}).get("statusCategory", {}).get("key", "")


def move(key: str, target: str, dry_run: bool = False) -> tuple[bool, str]:
    """티켓을 target(indeterminate | done) 으로 옮긴다. (성공 여부, 한 줄 결과)."""
    base, auth = load_jira()
    name, cat = status_of(base, auth, key)
    if cat == target or (target == "indeterminate" and cat == "done"):
        return True, f"지라 그대로: {key} ({name})"

    path = [name]
    wanted = ("indeterminate",) if target == "indeterminate" else ("done", "indeterminate")
    for _ in range(1 if target == "indeterminate" else MAX_HOPS):
        transitions = call(base, auth, f"issue/{key}/transitions").get("transitions", [])
        t = next((t for w in wanted for t in transitions if _category(t) == w), None)
        if t is None:
            return False, f"지라 실패: {key} 「{name}」에서 갈 수 있는 전이가 없습니다"
        if dry_run:
            more = "" if _category(t) == target else " → (이어서 완료 전이)"
            return True, f"지라 예정: {key} {' → '.join(path)} → {t['to']['name']}{more}"
        call(base, auth, f"issue/{key}/transitions", {"transition": {"id": t["id"]}})
        name, cat = status_of(base, auth, key)
        path.append(name)
        if cat == target:
            return True, f"지라: {key} {' → '.join(path)}"
    return False, f"지라 실패: {key} {MAX_HOPS}번 전이해도 완료에 닿지 않았습니다 ({' → '.join(path)})"
