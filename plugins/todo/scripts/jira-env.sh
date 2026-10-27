#!/usr/bin/env bash
# 플러그인 설정(userConfig)의 지라 주소·계정을 이 세션의 Bash 환경변수로 넘긴다. SessionStart hook 이 부른다.
#
# userConfig 값은 hook 에만 CLAUDE_PLUGIN_OPTION_<KEY> 로 들어오고, Claude 가 Bash 로 돌리는 스크립트에는 닿지 않는다.
# CLAUDE_ENV_FILE 에 export 줄을 쓰면 이 세션의 이후 Bash 명령마다 실행되어
# jira_api.py 가 TODO_JIRA_URL · TODO_JIRA_USERNAME · TODO_JIRA_API_TOKEN 으로 읽는다.
# 환경 파일은 세션의 모든 Bash 명령·다른 플러그인과 같이 쓰므로 TODO_ 를 붙여 이름이 겹치지 않게 한다.
# 비어 있는 값은 쓰지 않는다 — settings.json 의 env 에 둔 값이 있으면 그대로 쓰인다.
# 값을 stdout 으로 흘리지 않는다.

[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0

[ -n "${CLAUDE_PLUGIN_OPTION_JIRA_URL:-}" ] && printf 'export TODO_JIRA_URL=%q\n' "$CLAUDE_PLUGIN_OPTION_JIRA_URL" >>"$CLAUDE_ENV_FILE"
[ -n "${CLAUDE_PLUGIN_OPTION_JIRA_USERNAME:-}" ] && printf 'export TODO_JIRA_USERNAME=%q\n' "$CLAUDE_PLUGIN_OPTION_JIRA_USERNAME" >>"$CLAUDE_ENV_FILE"
[ -n "${CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN:-}" ] && printf 'export TODO_JIRA_API_TOKEN=%q\n' "$CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN" >>"$CLAUDE_ENV_FILE"

exit 0
