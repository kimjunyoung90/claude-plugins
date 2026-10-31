#!/bin/sh
# UserPromptSubmit: 개념 질문·자기 말 요약처럼 보이는 메시지면 question agent 호출 알림과 경로를 컨텍스트에 넣는다.
prompt=$(jq -r '.prompt // ""')
case "$prompt" in /*) exit 0 ;; esac
if printf '%s' "$prompt" | grep -Eq '뭐야|뭔데|뭐지|무슨|인가|건가|거야|거지|맞지|맞아|아니야|구나|이해했|왜 |차이가|원리'; then
  if [ -z "$CLAUDE_PLUGIN_OPTION_NOTES_PATH" ] || [ -z "$CLAUDE_PLUGIN_OPTION_GENIUS_PATH" ]; then
    jq -n '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:"[question] genius 경로 설정이 없어 기록할 수 없다. 기록할 메시지라면 폴더를 추측해 쓰지 말고, 경로가 설정되지 않았다고 한 줄로 알린다."}}'
    exit 0
  fi
  jq -n --arg notes "$CLAUDE_PLUGIN_OPTION_NOTES_PATH" --arg genius "$CLAUDE_PLUGIN_OPTION_GENIUS_PATH" '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:("[question] 이 메시지가 개념 질문이거나, 답을 듣고 자기 말로 정리한 것이거나, 틀린 이해가 드러난 것이면, 답한 뒤 genius:question agent를 백그라운드로 불러 기록한다. 학습 로그와 TIL을 직접 읽거나 쓰지 않는다. 프롬프트에는 사용자 문장 원문(고치지 않고), 상황, 답의 핵심 1~3문장, 틀린 이해면 무엇을 잘못 알았는지, 노트 폴더 \($notes), genius 폴더 \($genius)를 넣는다. 앞선 question agent가 아직 돌고 있으면 끝난 뒤 부른다. 기록 결과는 사용자에게 한 줄로만 알린다. 도구·설정·스킬 사용법이나 찾아보면 끝나는 사실 질문이면 무시한다.")}}'
fi
exit 0
