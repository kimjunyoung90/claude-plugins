#!/usr/bin/env python3
"""티켓에 연결된 세션들의 작업 시간과 정리를 지라 티켓에 작업 내역으로 기록한다 (날짜별 1건). /finish 가 부른다.

    worklog-update.py --issue <KEY> [--summary-file <파일>]

    --summary-file  work-summary 정리를 오늘 작업 내역 설명란 맨 위에 넣는다.
                    같은 날 작업 내역이 여럿이면(세션이 여럿) 첫 건에만 넣는다.

결과는 stdout 에 한 줄씩 알린다. 실패한 날이 있으면 종료 코드 1 — /finish 가 거기서 멈춘다.

세션이 며칠 걸치면 날짜별로 나눠 올린다(집계는 aggregate.py). 이미 올린 날은 장부(<세션id>.posted)로
걸러 같은 날을 두 번 올리지 않는다. 장부는 연결 파일과 따로 둔다 — 연결 파일은 재연결 때 새로 쓰여서,
거기 담으면 기록이 날아가 같은 날을 또 올린다.
지라는 응답이 들쭉날쭉하고 503 을 뱉기도 한다. 실패한 날은 장부에 적히지 않아 다음 실행 때 다시 올라간다.
지라 주소·계정은 jira_api.py 가 읽는다.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
from datetime import date, datetime
from pathlib import Path

from aggregate import build_entries  # 같은 scripts/ 폴더
from jira_api import JiraError, call, load_jira
from ticket_link import STATE_DIR, find_transcript, sanitize_id, sessions_for
from todo import TODO_DATA_DIR

LOG_FILE = TODO_DATA_DIR / "jira/worklog.log"

# 이보다 긴 공백은 자리를 비운 것으로 보고 작업시간에서 뺀다
IDLE_GAP_SEC = 900
# 하루 작업 시간(이미 올린 날이면 추가분)이 이 미만(1분)이면 작업 내역을 남기지 않는다
MIN_WORKLOG_SEC = 60

LOG_MAX_BYTES = 65536
LOG_KEEP_LINES = 300


def log_failure(message: str) -> None:
    """실패만 남긴다. 정상이면 하루 0줄이다. 64KB 를 넘으면 최근 300줄만 남긴다."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")
        if LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
            LOG_FILE.write_text("".join(lines[-LOG_KEEP_LINES:]), encoding="utf-8")
    except OSError:
        pass


# ── 장부 ──
# `<날짜>\t<누적초>` 한 줄씩 덧붙인다. 같은 날짜가 여러 줄이면 마지막 줄이 유효하다.
def ledger_file(session_id: str) -> Path:
    return STATE_DIR / f"{sanitize_id(session_id)}.posted"


def posted_days(session_id: str) -> dict[str, int]:
    seen: dict[str, int] = {}
    try:
        for line in ledger_file(session_id).read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    seen[parts[0]] = max(0, int(parts[1]))
                except ValueError:
                    continue
    except OSError:
        pass
    return seen


def mark_posted(session_id: str, day: str, total: int) -> None:
    try:
        with ledger_file(session_id).open("a", encoding="utf-8") as fh:
            fh.write(f"{day}\t{total}\n")
    except OSError:
        pass


def posted_before(entry: dict) -> bool:
    """aggregate.py 가 같은 날 추가분이면 코멘트 끝에 표시한다."""
    return "같은 날 추가분" in entry["payload"]["comment"]


class Run:
    def __init__(self, issue: str, summary: str | None):
        self.issue = issue
        self.summary = summary
        self.summary_used = False
        self.failed = False
        self.today = date.today().isoformat()
        self.jira: tuple[str, str] | None = None

    def apply_summary(self, entries: list[dict]) -> None:
        """정리를 오늘 작업 내역 설명란 맨 위에 붙인다. 자동 기록(수정 파일 목록)은 아래에 참고로 남긴다."""
        if self.summary is None or self.summary_used:
            return
        for entry in entries:
            if entry["day"] == self.today:
                entry["payload"]["comment"] = f"{self.summary}\n\n----\n{entry['payload']['comment']}"
                self.summary_used = True
                return

    def sync_session(self, session_id: str) -> None:
        transcript = find_transcript(session_id)
        if transcript is None:
            return
        try:
            entries = build_entries(str(transcript), IDLE_GAP_SEC, MIN_WORKLOG_SEC, posted_days(session_id))
        except Exception as e:  # noqa: BLE001 — 기록 하나가 깨져도 다른 세션은 올린다
            log_failure(f"집계 실패 session={session_id}: {e}")
            return
        if not entries:  # 기준 미달이거나 전부 이미 올린 날
            return

        self.apply_summary(entries)

        if self.jira is None:
            try:
                self.jira = load_jira()
            except JiraError:
                print(f"실패 {self.issue}: 지라 주소·계정이 없음 "
                      "(환경변수 TODO_JIRA_URL · TODO_JIRA_USERNAME · TODO_JIRA_API_TOKEN)")
                log_failure(f"지라 주소·계정 없음 session={session_id}")
                self.failed = True
                return
        base, auth = self.jira

        # 날짜별로 따로 보낸다. 한 건이 실패해도 나머지는 올리고, 성공한 날만 장부에 적는다.
        # 실패한 날은 장부에 없으므로 다음 실행 때 다시 올라간다.
        for entry in entries:
            day, total = entry["day"], entry["total_seconds"]
            try:
                call(base, auth, f"issue/{self.issue}/worklog", entry["payload"])
            except (urllib.error.URLError, JiraError, ValueError) as e:
                print(f"실패 {self.issue} {day} ({e}) — 다음 실행 때 다시 올라간다")
                log_failure(f"작업 내역 기록 실패 {self.issue} {day} ({e}) session={session_id}")
                self.failed = True
                continue
            mark_posted(session_id, day, total)
            extra = " (같은 날 추가분)" if posted_before(entry) else ""
            print(f"등록 {self.issue} {day} {entry['payload']['timeSpentSeconds'] // 60}분{extra}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--issue", required=True, help="티켓 키")
    parser.add_argument("--summary-file", help="오늘 작업 내역 맨 위에 넣을 정리")
    args = parser.parse_args(argv)

    summary = None
    if args.summary_file:
        try:
            summary = Path(args.summary_file).read_text(encoding="utf-8")
        except OSError:
            print(f"정리 파일을 읽지 못함: {args.summary_file}", file=sys.stderr)
            return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    run = Run(args.issue.upper(), summary)
    for session_id in sessions_for(run.issue, auto_bind_current=True):
        run.sync_session(session_id)

    if summary is not None and not run.summary_used:
        print(f"정리를 넣을 {run.today} 작업 내역이 없음 (이미 올렸거나 작업 시간이 기준 미달)")
    return 1 if run.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
