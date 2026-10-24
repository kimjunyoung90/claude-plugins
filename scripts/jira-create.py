#!/usr/bin/env python3
"""지라 티켓을 만든다. /todo:add 가 할 일을 추가할 때 부른다.

    jira-create.py <PROJECT> --summary "<제목>" [--type <유형>]
    jira-create.py <PROJECT> --summary "<제목>" --dry-run   만들 내용과 고를 수 있는 유형만 보여 준다

담당자는 나(접속 계정)로 정한다.
유형을 안 주면 「작업」·Task 를, 둘 다 없으면 하위 작업이 아닌 첫 유형을 쓴다.

결과는 마지막 줄에 「생성: <KEY>」. 종료 코드: 0 생성(또는 dry-run) · 1 실패
지라 주소·계정은 jira_api.py 가 읽는다.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error

from jira_api import JiraError, call, load_jira  # 같은 scripts/ 폴더

DEFAULT_TYPES = ("작업", "Task")

EXIT_OK, EXIT_FAIL = 0, 1


def choose_type(types: list[dict], wanted: str | None) -> dict:
    """하위 작업 유형은 고르지 않는다 — 부모 없이 만들 수 없다."""
    candidates = [t for t in types if not t.get("subtask")]
    if wanted:
        for t in candidates:
            if t["name"].lower() == wanted.lower():
                return t
        raise JiraError(f"유형 「{wanted}」 이 없습니다 — 고를 수 있는 유형: {names(candidates)}")
    for name in DEFAULT_TYPES:
        for t in candidates:
            if t["name"] == name:
                return t
    if not candidates:
        raise JiraError("이 프로젝트에 만들 수 있는 유형이 없습니다")
    return candidates[0]


def names(types: list[dict]) -> str:
    return ", ".join(t["name"] for t in types if not t.get("subtask")) or "(없음)"


def assignee_of(me: dict) -> dict:
    """클라우드는 accountId, 서버·데이터센터는 name 으로 담당자를 지정한다."""
    return {"accountId": me["accountId"]} if me.get("accountId") else {"name": me["name"]}


def run(args) -> int:
    base, auth = load_jira()
    project = args.project.upper()
    info = call(base, auth, f"project/{project}")
    issue_type = choose_type(info.get("issueTypes") or [], args.type)
    me = call(base, auth, "myself")
    who = me.get("displayName") or me.get("name") or "나"

    if args.dry_run:
        print(f"예정: {project} 「{issue_type['name']}」 담당 {who} · {args.summary}")
        print(f"고를 수 있는 유형: {names(info.get('issueTypes') or [])}")
        return EXIT_OK

    fields = {"project": {"key": project}, "issuetype": {"id": issue_type["id"]}, "summary": args.summary,
              "assignee": assignee_of(me)}
    created = call(base, auth, "issue", {"fields": fields})
    print(f"생성: {created['key']}")
    return EXIT_OK


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", help="프로젝트 키")
    parser.add_argument("--summary", required=True, help="티켓 제목")
    parser.add_argument("--type", help="이슈 유형 이름. 없으면 작업·Task")
    parser.add_argument("--dry-run", action="store_true", help="만들지 않고 예정만 보여 준다")
    args = parser.parse_args(argv)
    if not args.summary.strip():
        print("실패: 제목이 비어 있습니다", file=sys.stderr)
        return EXIT_FAIL
    try:
        return run(args)
    except (urllib.error.URLError, JiraError, KeyError, ValueError) as e:
        print(f"실패: {args.project} {e}")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
