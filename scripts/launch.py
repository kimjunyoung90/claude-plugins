#!/usr/bin/env python3
"""할 일 하나를 맡을 작업 세션을 새 워크트리에 띄운다. /start 가 부른다.

    launch.py <ref> --repo <레포 경로> --base <기준 브랜치> --name <워크트리 이름> [--dry-run]

    ref     번호 · 할 일 id(T-NNNN) · 티켓 키 — 티켓이 붙은 할 일이어야 한다
    --name  워크트리·브랜치 이름. <KEY>-<짧은 영문 요약> 꼴을 권한다

실행 환경은 /start 를 부른 지휘 세션을 보고 고른다.
  orca  지휘 세션이 Orca 터미널 안에서 돌고 있고(환경변수 ORCA_WORKTREE_ID) 그 레포가 Orca 에 등록돼 있으면
        `orca worktree create` 로 띄운다.
        지휘 세션 워크트리 아래 「N 하위」로 묶여 사이드바에 보인다.
  bg    그 밖에는 `git worktree add` 로 <레포>/.claude/worktrees/<이름> 을 만들고 그 안에서 `claude --bg` 로 띄운다.
        agent view(`claude agents`)에 보이고 `claude attach <id>` 로 들어간다.
        `claude --bg -w` 는 기준 브랜치를 고를 수 없어 워크트리는 직접 만든다.
        Orca 앱이 켜져 있어도 지휘 세션이 일반 터미널이면 bg 로 띄운다 — 사용자가 보는 곳(agent view)에 세션이 생기게.

첫 지시문 첫 줄은 「<KEY> <제목>」이다 — Orca 사이드바·세션 이름이 이 줄을 따른다.
작업 세션은 지시문대로 ticket_link.py bind <KEY> 를 실행해 자기 세션을 티켓에 연결한다.
명령은 인자 목록으로 실행한다 — 제목·메모에 따옴표나 $ 가 있어도 셸이 해석하지 않는다.
결과는 마지막 줄들에 「실행: orca|bg」「워크트리: <경로>」「세션: <id>」. 실패하면 종료 코드 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import todo as todo_mod  # 같은 scripts/ 폴더

SCRIPTS = Path(__file__).resolve().parent
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}")


def run(cmd: list[str], cwd: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def orca_repos() -> set[str] | None:
    """Orca 가 쓸 수 있으면 등록된 레포 경로들, 아니면 None."""
    try:
        status = json.loads(run(["orca", "status", "--json"], timeout=15).stdout or "{}")
        if not (status.get("result") or {}).get("runtime", {}).get("reachable"):
            return None
        listed = json.loads(run(["orca", "repo", "list", "--json"], timeout=15).stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    repos = listed.get("result", listed)
    repos = repos.get("repos", []) if isinstance(repos, dict) else repos
    return {str(Path(r["path"]).resolve()) for r in repos if r.get("path")}


def build_prompt(rec: dict) -> str:
    lines = [f"{rec['jira']} {rec['title']}",
             f"이 작업은 {rec['jira']} 건이다. 시작 전에 python3 \"{SCRIPTS / 'ticket_link.py'}\" bind {rec['jira']} 를 실행한다."]
    if rec.get("note"):
        lines.append(f"메모: {rec['note']}")
    return "\n".join(lines)


def launch_orca(repo: Path, args, prompt: str) -> int:
    cmd = ["orca", "worktree", "create", "--repo", f"path:{repo}", "--name", args.name, "--agent", "claude",
           "--base-branch", args.base, "--prompt", prompt, "--json"]
    if args.dry_run:
        print("실행 환경: orca (Orca 사이드바의 지휘 세션 아래)")
        print(f"예정: orca worktree create --repo path:{repo} --name {args.name} --base-branch {args.base}")
        return 0
    proc = run(cmd)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        out = {}
    if proc.returncode != 0 or out.get("ok") is False:
        print(f"실패: orca worktree create — {out.get('error') or proc.stderr.strip()[:300]}")
        return 1
    worktree = (out.get("result") or {}).get("worktree") or out.get("result") or {}
    print("실행: orca")
    print(f"워크트리: {worktree.get('path', '?')}")
    print("세션: Orca 사이드바에서 연다 (지휘 세션 워크트리 아래 하위 항목)")
    return 0


def launch_bg(repo: Path, rec: dict, args, prompt: str) -> int:
    wt = repo / ".claude" / "worktrees" / args.name
    claude_cmd = ["claude", "--bg", "-n", f"{rec['jira']} {rec['title']}", prompt]
    if args.dry_run:
        print("실행 환경: bg (agent view — claude agents)")
        print(f"예정: git worktree add {wt} -b {args.name} {args.base}")
        print(f"예정: (그 안에서) claude --bg -n \"{rec['jira']} {rec['title']}\"")
        return 0
    if run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{args.name}"]).returncode == 0:
        print(f"실패: 브랜치 {args.name} 가 이미 있다 — 다른 --name 을 쓴다")
        return 1
    ignore_worktrees(repo)
    proc = run(["git", "-C", str(repo), "worktree", "add", str(wt), "-b", args.name, args.base])
    if proc.returncode != 0:
        print(f"실패: git worktree add — {proc.stderr.strip()[:300]}")
        return 1
    proc = run(claude_cmd, cwd=str(wt))
    output = proc.stdout + proc.stderr
    session = re.search(r"claude attach (\S+)", output)
    if proc.returncode != 0 or not session:
        # 세션이 안 떴으면 만든 워크트리를 걷어 낸다 — 빈 워크트리·브랜치가 남지 않게
        run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)])
        run(["git", "-C", str(repo), "branch", "-D", args.name])
        hint = " — 그 레포에서 claude 를 한 번 실행해 신뢰를 수락한 뒤 다시 한다" if "not trusted" in output else ""
        print(f"실패: claude --bg — {output.strip()[-300:]}{hint}")
        return 1
    print("실행: bg")
    print(f"워크트리: {wt}")
    print(f"세션: {session.group(1)} (claude attach {session.group(1)} · agent view 는 claude agents)")
    return 0


def ignore_worktrees(repo: Path) -> None:
    """.claude/worktrees/ 가 원래 체크아웃에 추적 안 된 파일로 보이지 않게 이 레포의 로컬 제외 목록에만 넣는다."""
    common = run(["git", "-C", str(repo), "rev-parse", "--git-common-dir"]).stdout.strip()
    if not common:
        return
    exclude = (repo / common if not Path(common).is_absolute() else Path(common)) / "info" / "exclude"
    try:
        text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        if ".claude/worktrees/" not in text.split():
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a", encoding="utf-8") as fh:
                fh.write(("" if text.endswith("\n") or not text else "\n") + ".claude/worktrees/\n")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ref", help="번호 · 할 일 id · 티켓 키")
    parser.add_argument("--repo", required=True, help="작업할 레포 경로")
    parser.add_argument("--base", required=True, help="기준 브랜치")
    parser.add_argument("--name", required=True, help="워크트리·브랜치 이름 (<KEY>-<짧은 영문 요약>)")
    parser.add_argument("--dry-run", action="store_true", help="띄우지 않고 실행 환경과 할 일만 보여 준다")
    args = parser.parse_args(argv)

    rec = todo_mod.find(todo_mod.load(), args.ref)
    if not rec.get("jira"):
        print(f"실패: {rec['id']} 에 티켓이 없다 — todo.py set {rec['id']} todo --jira <KEY> 로 붙인다")
        return 1
    if not NAME.fullmatch(args.name):
        print(f"실패: 워크트리 이름은 영문·숫자·. _ - 만 쓴다: {args.name}")
        return 1
    repo = Path(args.repo).expanduser().resolve()
    if run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"]).returncode != 0:
        print(f"실패: git 레포가 아니다: {repo}")
        return 1
    top = Path(run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"]).stdout.strip())

    prompt = build_prompt(rec)
    if os.environ.get("ORCA_WORKTREE_ID"):  # 지휘 세션이 Orca 터미널 안이다
        orca = orca_repos()
        if orca is not None and str(top) in orca:
            return launch_orca(top, args, prompt)
        reason = "Orca 에 연결할 수 없어" if orca is None else f"{top} 가 Orca 에 등록돼 있지 않아"
        print(f"참고: 지휘 세션은 Orca 안이지만 {reason} bg 세션으로 띄운다")
    return launch_bg(top, rec, args, prompt)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
