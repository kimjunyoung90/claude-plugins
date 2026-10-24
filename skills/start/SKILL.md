---
name: start
description: 할 일 목록의 건마다 그 일을 맡을 작업 세션을 새 워크트리에 띄우고, 할 일을 작업 중(in_progress)으로 바꾼다(지라 티켓은 자동으로 진행 중). /start 를 Orca 안에서 부르면 Orca 사이드바에, 일반 터미널에서 부르면 Claude Code 백그라운드 세션(agent view)으로 띄운다. "/start 1, 2, 3", "N번 처리", "N번 시작" 요청 시 사용. 티켓은 할 일을 추가할 때(/todo:add) 이미 붙어 있다. 완료는 /finish.
argument-hint: "<할 일 번호> [, <번호> ...]"
---

대상: `$ARGUMENTS` — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/todo.py" todo` 의 번호. 여러 개면 건마다 아래를 한다.
명령: `todo.py` = `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/todo.py"`, `launch.py` = `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/launch.py"`.

## 1. 대상 확인

- 이미 `in_progress`(「작업 중」)인 건은 작업 중이라고 알리고 건너뛴다.
- 티켓(`[KEY]`)이 없는 건은 시작하지 않고 알린다. 붙일 티켓이 있으면 `todo.py set <번호> todo --jira <KEY>` 로 붙인 뒤 다시 `/start` 한다.

## 2. 확인

건마다 정한다.

- 레포: 할 일 내용과 티켓으로 추정한 **레포 경로**. 모르겠으면 묻는다(Orca 를 쓰면 `orca repo list` 에 경로가 나온다).
- 기준 브랜치: 추정하고, 모르겠으면 묻는다.
- 워크트리 이름: `<KEY>-<짧은 영문 요약>` (예: `PROJ-1-login-timeout`). 브랜치 이름도 이것이 된다.

그리고 실행 환경과 상태 변화를 먼저 본다.

```bash
launch.py <번호> --repo <레포 경로> --base <기준 브랜치> --name <워크트리 이름> --dry-run
todo.py set <번호> in_progress --dry-run
```

대상 전부를 한 번에 보여 주고 승인을 받는다.

```
1. <할 일 제목>
   티켓: <KEY> (<지금 상태> → <진행 상태> | 이미 진행 중) · 레포: <레포> ← <기준 브랜치> · <orca | bg>
```

## 3. 세션 띄우기 · 상태 변경

세션을 먼저 띄우고, 뜬 건만 할 일을 `in_progress` 로 바꾼다 — 세션 없이 작업 중으로 남지 않게.

```bash
launch.py <번호> --repo <레포 경로> --base <기준 브랜치> --name <워크트리 이름>
todo.py set <번호> in_progress
```

- `launch.py` 가 실행 환경을 스스로 고른다: 이 세션이 Orca 터미널 안이고 그 레포가 Orca 에 등록돼 있으면 Orca, 아니면 bg. 작업 세션은 첫 지시대로 자기 세션을 티켓에 연결한다(`ticket_link.py bind`).
- `launch.py` 가 실패하면(신뢰하지 않은 레포·이미 있는 브랜치 등) 그 건은 상태를 바꾸지 않고 메시지를 그대로 전한다.
- `todo.py` 가 지라 티켓도 진행 중으로 옮긴다. 지라 전이가 실패해도 할 일 상태는 바뀐다 — 실패 메시지는 완료 보고에 그대로 적는다.

## 4. 끝나면 알림 받기

띄운 세션마다 다음에 쉬게 될 때 알려 달라고 구독한다 — `SendMessage` 에 `notify_when_idle: true`, 메시지 없이.
세션은 `ListAgents` 에서 찾는다: bg 는 이름이 `<KEY> <제목>`, Orca 는 작업 경로가 그 워크트리다. 아직 목록에 없으면 건너뛴다(`/check` 로 볼 수 있다).
알림은 한 번만 온다. 알림이 오면 `/check <번호>` 처럼 그 건의 보고를 정리해 알린다.

**완료 기준**: 건마다 티켓·지라 상태·실행 환경(orca/bg)·워크트리 경로를 한 줄씩 보고한다. bg 면 들어가는 방법(`claude attach <id>`, 또는 `claude agents`)을 덧붙인다.
