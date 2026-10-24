#!/usr/bin/env python3
"""할 일 목록 — 할 일을 읽고 쓰는 유일한 창구. 위치는 $TODO_DATA_DIR/todo.jsonl (없으면 ~/.claude/todo).

    todo.py [todo] [--all]                   할 일 목록 (번호는 /todo 화면과 같다). --all 이면 끝난 일까지
    todo.py add --title "<제목>" [--jira <KEY>] [--note "<메모>"]
    todo.py set <ref> <상태> [--jira <KEY>] [--title ..] [--note ..] [--dry-run] [--no-jira]
                                             ref 는 번호 · 할 일 id(T-NNNN) · 티켓 키
                                             in_progress·done 으로 바꾸면 지라 티켓도 진행 중·완료로 옮긴다
    todo.py goal                             이번 주 목표 (이번 ISO 주 + 끝나지 않은 지난 목표는 이월)
    todo.py goal <ref> ... [--week YYYY-Www] 이번 주 목표로 표시
    todo.py goal --clear <ref> ...           목표 표시 해제
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

TODO_DATA_DIR = Path(os.environ.get("TODO_DATA_DIR") or "~/.claude/todo").expanduser()
TODO_FILE = TODO_DATA_DIR / "todo.jsonl"

# ── 할 일 형식 (todo.jsonl) ──
# JSON Lines — 할 일 1건 = 1줄. save() 가 created 순으로 다시 써서 저장한다.
#   id         T-NNNN                 할 일 id. 일련번호, 다시 쓰지 않는다
#   created    YYYY-MM-DDTHH:MM       추가한 시각 — 번호 순서·경과일·「오늘」 표시의 기준
#   title      문자열                 할 일 제목
#   state      todo · in_progress · done   todo(할 일) → in_progress(작업 중, /start) → done(완료, /finish)
#   jira       <KEY> · null           연결 티켓
#   note       문자열 · null          기한·배경 같은 메모
#   done_at    YYYY-MM-DD · null      완료한 날
#   goal       YYYY-Www · null        목표로 정한 ISO 주. 참/거짓이 아니라 주라서, 주가 바뀌면 저절로 이월로 갈린다
# 번호는 state 가 todo·in_progress 인 건을 created 오름차순으로 센 순서다 — 화면(hooks/format.ts)도 같은 기준.
# 형식을 바꿀 때는 이 파일(쓰기)과 hooks/format.ts · types/index.d.ts(읽기)를 같이 고친다.
FIELDS = ("id", "created", "title", "state", "jira", "note", "done_at", "goal")
# todo(할 일) → in_progress(작업 중) → done(완료)
STATES = ("todo", "in_progress", "done")
ACTIVE = ("todo", "in_progress")            # 할 일 목록 — 화면과 같은 범위
TICKET = re.compile(r"[A-Z][A-Z0-9]+-\d+")
TODO_ID = re.compile(r"T-\d{4,}")           # 티켓 키 모양이라 TICKET 보다 먼저 본다
WEEK = re.compile(r"\d{4}-W\d{2}")          # 목표 주 — ISO 주 (YYYY-Www)


def load() -> list[dict]:
    if not TODO_FILE.exists():
        return []
    out = []
    for n, line in enumerate(TODO_FILE.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{TODO_FILE}:{n} 파싱 실패 — {exc}")
    return out


def save(records: list[dict]) -> None:
    """임시 파일에 쓰고 rename — 중간에 죽어도 목록이 깨지지 않는다."""
    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(records, key=lambda r: (r["created"], r["id"]))
    fd, tmp = tempfile.mkstemp(dir=str(TODO_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for rec in rows:
                fh.write(json.dumps({k: rec.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")
        os.replace(tmp, TODO_FILE)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def next_id(records: list[dict]) -> str:
    used = [int(r["id"][2:]) for r in records if TODO_ID.fullmatch(r.get("id") or "")]
    return f"T-{max(used, default=0) + 1:04d}"


def new_todo(records: list[dict], *, title: str, jira: str | None = None, note: str | None = None) -> dict:
    """새 할 일 한 건. records 는 바꾸지 않는다 — 저장은 부르는 쪽이 한다."""
    return {
        "id": next_id(records), "created": datetime.now().strftime("%Y-%m-%dT%H:%M"), "title": title,
        "state": "todo", "jira": jira, "note": note, "done_at": None, "goal": None,
    }


def active_rows(records: list[dict]) -> list[dict]:
    """할 일 목록 순서 — 접수 시각 순 todo·in_progress. 화면 번호와 같은 기준."""
    return sorted((r for r in records if r["state"] in ACTIVE), key=lambda r: (r["created"], r["id"]))


def find(records: list[dict], ref: str) -> dict:
    """번호, 할 일 id, 티켓 키 중 하나로 한 건을 집는다."""
    if ref.isdigit():
        rows = active_rows(records)
        n = int(ref)
        if not 1 <= n <= len(rows):
            raise SystemExit(f"{n}번 할 일이 없습니다 (할 일 {len(rows)}건)")
        return rows[n - 1]
    if TODO_ID.fullmatch(ref.upper()):
        hits = [r for r in records if r["id"] == ref.upper()]
        if not hits:
            raise SystemExit(f"없는 할 일: {ref}")
        return hits[0]
    if TICKET.fullmatch(ref.upper()):
        return find_by_ticket(records, ref.upper())
    raise SystemExit(f"할 일을 찾을 수 없습니다: {ref} — 번호 · 할 일 id(T-NNNN) · 티켓 키로 지정하세요")


def find_by_ticket(records: list[dict], ticket: str) -> dict:
    """그 티켓이 연결된 할 일. 끝난 일보다 진행 중인 일을 먼저 본다."""
    target_key = ticket.upper()
    linked = [r for r in records if (r.get("jira") or "").upper() == target_key]
    hits = [r for r in linked if r["state"] in ACTIVE] or linked
    if not hits:
        raise SystemExit(f"{ticket} 이 연결된 할 일이 없습니다")
    if len(hits) > 1:
        raise SystemExit(f"{ticket} 이 {len(hits)}건에 연결돼 있습니다 — 할 일 id 로 지정하세요:\n  " +
                         "\n  ".join(f"{r['id']}  ({r['state']}) {r['title']}" for r in hits[:10]))
    return hits[0]


def cmd_set(args) -> None:
    records = load()
    rec = find(records, args.ref)
    changes = {"state": args.state}
    changes.update({f: getattr(args, f) for f in ("jira", "note", "title")
                    if getattr(args, f) is not None})
    changes["done_at"] = (rec.get("done_at") or date.today().isoformat()) if args.state == "done" else None
    if not sync_jira(rec, args) or args.dry_run:
        return
    save([{**r, **changes} if r["id"] == rec["id"] else r for r in records])
    print(f"{rec['id']}  {rec['state']} → {args.state}  {rec['title']}")


# 할 일 상태와 지라 상태를 같이 옮긴다 — 할 일 상태를 쓰는 곳이 이 파일뿐이라 여기서 맞춘다.
JIRA_TARGET = {"in_progress": "indeterminate", "done": "done"}


def sync_jira(rec: dict, args) -> bool:
    """상태가 바뀌면 지라도 옮긴다. False 면 할 일을 저장하지 않는다.
    done 은 지라가 실패하면 멈춘다(보드와 어긋나지 않게). in_progress 는 지라가 실패해도 할 일은 바꾼다."""
    key = args.jira or rec.get("jira")
    target = JIRA_TARGET.get(args.state)
    if args.no_jira or not key or not target or rec["state"] == args.state:
        if args.dry_run:
            print(f"예정: {rec['id']}  {rec['state']} → {args.state}  (지라는 바꾸지 않음)")
        return True
    import urllib.error
    from jira_api import JiraError, move  # 같은 scripts/ 폴더 — 지라를 쓸 때만 불러온다
    try:
        ok, message = move(key, target, dry_run=args.dry_run)
    except (urllib.error.URLError, JiraError, KeyError, ValueError) as e:
        ok, message = False, f"지라 실패: {key} {e}"
    print(message)
    if args.dry_run:
        print(f"예정: {rec['id']}  {rec['state']} → {args.state}")
        return True
    if not ok and args.state == "done":
        raise SystemExit(f"{rec['id']} 는 done 으로 바꾸지 않았습니다 — 지라 완료 전이 실패. 지라 없이 바꾸려면 --no-jira")
    return True


def cmd_add(args) -> None:
    records = load()
    rec = new_todo(records, title=args.title, jira=args.jira, note=args.note)
    save(records + [rec])
    print(f"추가: {rec['id']} {rec['title']}")


def this_week(today: date | None = None) -> str:
    y, w, _ = (today or date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def check_week(week: str) -> None:
    """YYYY-Www 꼴이고 그 해에 실제로 있는 주인지. W00·W54 같은 오타를 막는다."""
    try:
        if not WEEK.fullmatch(week):
            raise ValueError
        date.fromisocalendar(int(week[:4]), int(week[6:]), 1)
    except ValueError:
        raise SystemExit(f"주는 YYYY-Www 꼴의 실제 있는 ISO 주로 씁니다: {week}")


# 목표는 할 일의 칸(goal)이다 — 목표 파일을 따로 두지 않는다. 이번 주 목표는 이름 없이 한 묶음이다.
# 주 계산은 이 파일(date.isocalendar())과 화면(format.ts isoWeek())이 같은 값을 낸다.
def is_goal(rec: dict, week: str) -> bool:
    """이번 주 목표이거나 이월 — 화면 ★ 와 같은 기준. 미래 주 목표는 아직 아니다."""
    return bool(rec.get("goal")) and rec["goal"] <= week


def goal_rows(records: list[dict], week: str) -> list[dict]:
    """이번 주 목표인 할 일 — 끝나지 않은 할 일만, 목록 번호 순.
    이월(지난 주에 목표였는데 아직 안 끝난 건)도 넣는다. 미래 주 목표는 아직 넣지 않는다."""
    return [rec for rec in active_rows(records) if is_goal(rec, week)]


def row_lines(n: int, rec: dict, today: str) -> tuple[str, str]:
    """할 일 한 건의 두 줄 — todo·goal 목록이 같은 모양을 쓴다."""
    new = " (새)" if rec["created"][:10] == today else ""
    jira = f" [{rec['jira']}]" if rec.get("jira") else ""
    md = f"{int(rec['created'][5:7])}/{int(rec['created'][8:10])}"
    doing = "▶ " if rec["state"] == "in_progress" else ""
    note = f" · {rec['note']}" if rec.get("note") else ""
    return (f"{n:>2}. {doing}{rec['title']}{jira}{new}", f"    {md} 접수 · {rec['id']}{note}")


def print_goals(rows: list[dict], numbers: dict[str, int], today: str, week: str) -> None:
    print("★ 이번 주 목표")
    for rec in rows:
        first, second = row_lines(numbers[rec["id"]], rec, today)
        carried = f" (이월 {rec['goal']})" if rec["goal"] != week else ""
        print(f"{first}{carried}\n{second}")


def cmd_goal(args) -> None:
    week = args.week or this_week()
    check_week(week)
    if args.clear is not None and args.refs:
        raise SystemExit("표시와 해제(--clear)는 따로 실행하세요")
    records = load()
    refs = args.clear if args.clear is not None else args.refs
    if refs:
        # 번호는 바꾸기 전 목록 기준이므로 먼저 전부 id 로 바꾼다
        targets = [find(records, ref) for ref in refs]
        closed = [r for r in targets if r["state"] not in ACTIVE] if args.clear is None else []
        if closed:
            raise SystemExit("끝난 할 일은 목표로 정할 수 없습니다: " + ", ".join(r["id"] for r in closed))
        ids = [r["id"] for r in targets]
        change = {"goal": None} if args.clear is not None else {"goal": week}
        save([{**r, **change} if r["id"] in ids else r for r in records])
        for rec in targets:
            print(f"{rec['id']}  {'목표 해제' if change['goal'] is None else f'★ 이번 주 목표 ({week})'}  {rec['title']}")
        return
    goals = goal_rows(records, week)
    numbers = {r["id"]: n for n, r in enumerate(active_rows(records), 1)}
    print(f"■ 이번 주 목표 ({week}) {len(goals)}건")
    if goals:
        print_goals(goals, numbers, date.today().isoformat(), week)


def cmd_todo(args) -> None:
    """todo·in_progress 전체. 이번 주 목표(★)를 먼저, 나머지는 구분선 아래로. 번호는 접수 순 그대로.
    --all 이면 끝난 일을 번호 없이 뒤에 붙인다 (/todo:add 가 비슷한 일의 티켓 프로젝트를 볼 때)."""
    records = load()
    rows = active_rows(records)
    if args.all:
        done = sorted((r for r in records if r["state"] == "done"), key=lambda r: (r["created"], r["id"]))
    if not rows and not args.all:
        print("할 일 없음")
        return
    today = date.today().isoformat()
    numbers = {r["id"]: n for n, r in enumerate(rows, 1)}
    week = this_week()
    goals = goal_rows(records, week)
    grouped = {rec["id"] for rec in goals}
    print(f"■ 할 일 {len(rows)}건")
    if goals:
        print_goals(goals, numbers, today, week)
        if len(grouped) < len(rows):
            print("──")
    for rec in rows:
        if rec["id"] not in grouped:
            print("\n".join(row_lines(numbers[rec["id"]], rec, today)))
    if args.all and done:
        print(f"── 끝난 일 {len(done)}건")
        for rec in done:
            jira = f" [{rec['jira']}]" if rec.get("jira") else ""
            print(f"  · {rec['title']}{jira}  ({rec.get('done_at') or '-'} 완료 · {rec['id']})")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="끝난 일까지")
    parser.set_defaults(func=cmd_todo)
    subs = parser.add_subparsers()

    p = subs.add_parser("set", help="상태 변경")
    p.add_argument("ref", help="번호 · 할 일 id(T-NNNN) · 티켓 키")
    p.add_argument("state", choices=STATES)
    p.add_argument("--jira")
    p.add_argument("--note", help="메모를 바꾼다")
    p.add_argument("--title", help="제목을 바로잡는다")
    p.add_argument("--dry-run", action="store_true", help="바꾸지 않고 할 일·지라 상태가 어떻게 바뀔지만 보여 준다")
    p.add_argument("--no-jira", action="store_true", help="지라 상태는 그대로 두고 할 일만 바꾼다")
    p.set_defaults(func=cmd_set)

    p = subs.add_parser("add", help="할 일 추가")
    p.add_argument("--title", required=True)
    p.add_argument("--jira")
    p.add_argument("--note")
    p.set_defaults(func=cmd_add)

    p = subs.add_parser("todo", help="할 일 목록")
    p.add_argument("--all", action="store_true", help="끝난 일까지")
    p.set_defaults(func=cmd_todo)

    p = subs.add_parser("goal", help="목표 보기·표시·해제")
    p.add_argument("refs", nargs="*", help="목표로 표시할 할 일 — 번호 · 할 일 id · 티켓 키")
    p.add_argument("--week", help="ISO 주 YYYY-Www (없으면 이번 주)")
    p.add_argument("--clear", nargs="+", metavar="REF", help="목표 표시 해제")
    p.set_defaults(func=cmd_goal)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
