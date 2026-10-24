---
name: finish
description: 티켓 작업을 완료 처리한다 — 작업 내용 정리, 지라 작업 내역 기록, 할 일 done(지라 티켓은 자동으로 완료). 사용자가 결과를 확인하고 "완료", "끝났어", "완료 처리해줘"라고 할 때 사용. "N번 처리"·"N번 시작"은 /start 다.
argument-hint: "[티켓 키]"
---

대상 티켓: `$ARGUMENTS`. 비어 있으면 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ticket_link.py" status` 로 이 세션에 연결된 티켓을 확인하고, 연결이 없으면 묻는다. 대상 티켓이 주어졌는데 이 세션이 아직 연결되지 않았으면 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ticket_link.py" bind <티켓>` 으로 자동 연결한다.

## 1. 정리

`work-summary` 서브에이전트(Agent 도구, `subagent_type: todo:work-summary`)에 티켓 키를 넘겨 금일 한 일을 정리받는다.

## 2. 확인

사용자 확인 없이 지라에 올리지 않는다. 먼저 상태가 어떻게 바뀔지 본다. 할 일을 `done` 으로 바꾸면 지라 티켓도 완료로 따라간다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/todo.py" set <티켓> done --dry-run
```

아래를 보여 주고 진행 여부를 묻는다.

```
티켓: <티켓>
작업 내역: <날짜> <시간>
지라 상태: <dry-run 결과 — 예정 경로 / 이미 완료>
<1단계 정리>
```

## 3. 지라 작업 내역 기록

1단계 정리를 파일로 저장하고 넘긴다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worklog-update.py" --issue <티켓> --summary-file <정리 파일>
```

실패하면 다음 단계로 가지 않고 멈춘다.

## 4. 할 일 done

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/todo.py" set <티켓> done
```

`todo.py` 가 지라 티켓을 먼저 완료로 옮긴다(바로 가는 전이가 없으면 「진행중」 등을 거친다). 지라 전이가 실패하면 할 일도 `done` 으로 바꾸지 않고 멈춘다 — 메시지를 그대로 전한다.

세션↔티켓 연결 파일(`~/.claude/todo/jira/state/*.json`)은 지우지 않는다 — 기록으로 남긴다.

**완료 기준**: 기록한 작업 내역(날짜·시간), 지라 상태 변경(완료 경로 / 이미 완료), 할 일 상태 변경 결과를 한 줄씩 보고한다.
