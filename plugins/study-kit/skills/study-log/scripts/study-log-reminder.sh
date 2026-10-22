#!/bin/sh
# UserPromptSubmit: 공부 개념 질문·자기 말 요약처럼 보이는 메시지면 study-log 스킬 알림을 컨텍스트에 넣는다.
prompt=$(jq -r '.prompt // ""')
case "$prompt" in /*) exit 0 ;; esac
if printf '%s' "$prompt" | grep -Eq '\?|뭐야|뭔데|뭐지|무슨|인가|건가|거야|거지|맞지|맞아|아니야|구나|이해했|왜 '; then
  jq -n '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:"[study-log] 이 메시지가 공부 개념 질문이거나, 답을 듣고 자기 말로 정리한 것이거나, 틀린 이해가 드러난 것이면 study-log 스킬을 따라 학습 로그에 기록한다. 도구·설정·스킬 사용법 질문이면 무시한다."}}'
fi
exit 0
