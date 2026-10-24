---
name: start
description: 할 일 목록의 건마다 할 일을 작업 중(in_progress)으로 바꾸고(지라 티켓은 자동으로 진행 중), 그 건을 처리할 새 세션을 Orca 로 열어 티켓과 연결한다. "/start 1, 2, 3", "N번 처리", "N번 시작" 요청 시 사용. 티켓은 할 일을 추가할 때(/todo:add) 이미 붙어 있다. 완료는 /finish.
argument-hint: "<할 일 번호> [, <번호> ...]"
---

대상: `$ARGUMENTS` — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/todo.py" todo` 의 번호. 여러 개면 건마다 아래를 한다.

## 1. 대상 확인

- 이미 `in_progress`(「작업 중」)인 건은 작업 중이라고 알리고 건너뛴다.
- 티켓(`[KEY]`)이 없는 건은 시작하지 않고 알린다. 붙일 티켓이 있으면 `todo.py set <번호> todo --jira <KEY>` 로 붙인 뒤 다시 `/start` 한다.

## 2. 확인

건마다 상태가 어떻게 바뀔지 먼저 본다. 할 일을 `in_progress` 로 바꾸면 지라 티켓도 진행 중으로 따라간다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/todo.py" set <번호> in_progress --dry-run
```

대상 전부를 한 번에 보여 주고 승인을 받는다. 레포와 기준 브랜치는 할 일 내용과 티켓으로 추정하고, 모르겠으면 `orca repo list` 를 보여 주고 여기서 묻는다.

```
1. <할 일 제목>
   티켓: <KEY> (<지금 상태> → <진행 상태> | 이미 진행 중) · 레포: <레포> ← <기준 브랜치>
```

## 3. 상태 변경 · 세션 실행 · 티켓 연결

할 일을 `in_progress` 로 바꾼다. `todo.py` 가 지라 티켓도 진행 중으로 옮긴다. 지라 전이가 실패해도(지라 응답 없음·전이 없음) 할 일 상태와 세션 열기는 그대로 한다 — 실패 메시지는 완료 보고에 그대로 적는다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/todo.py" set <번호> in_progress
orca worktree create --repo name:<레포> --name <워크트리 이름> --agent claude --base-branch <기준 브랜치> \
  --prompt "이 작업은 <KEY> 건이다. 시작 전에 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ticket_link.py bind <KEY> 를 실행한다.
<할 일 제목과 메모>"
```

**완료 기준**: 건마다 티켓·지라 상태·워크트리 이름을 한 줄씩 보고한다.
