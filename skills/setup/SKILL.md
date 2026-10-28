---
name: setup
description: genius을 처음 쓰는 PC에서 환경을 점검하고 경로 설정(~/.claude/genius.json), 학습 폴더, 학습 로그, 정답 키 폴더를 준비하는 스킬. 사용자가 "genius 설정", "setup", "경로 바꾸기"를 요청하거나, test·question 스킬이 설정 파일이 없다고 안내했을 때 사용한다.
disable-model-invocation: false
---

genius(`test`, `question` 스킬과 질문 알림 hook)을 쓰기 전에 한 번 실행한다. 이미 설정된 PC에서 다시 실행하면 현재 상태를 보여 주고 바꿀 것만 바꾼다. **이미 있는 파일은 덮어쓰지 않는다.**

# 1. 환경 확인
아래를 확인하고 결과를 표로 보여 준다. 없는 것은 설치 방법만 알려 주고, 설치는 사용자가 원할 때 한다.

| 항목 | 확인 명령 | 쓰는 곳 | 없을 때 |
|---|---|---|---|
| macOS | `uname -s`가 `Darwin` | PDF 스크립트 전체 | test의 PDF 기능을 쓸 수 없다고 알림 |
| `swift` | `swift --version` | 시험지 PDF 변환, 필기 자르기 | `xcode-select --install` |
| `jq` | `command -v jq` | 질문 알림 hook | macOS 15 이상은 기본 포함(`/usr/bin/jq`). 그 아래면 `brew install jq` |

# 2. 경로 설정
`~/.claude/genius.json`에 세 경로를 둔다.

```json
{
  "notes_dir": "공부 노트(마크다운) 폴더",
  "study_dir": "학습 로그와 시험지 PDF 폴더",
  "answer_key_dir": "정답 키 폴더",
  "review_limit": 15
}
```

| 키 | 내용 | 권장 |
|---|---|---|
| `notes_dir` | 시험 문제의 범위이자 근거가 되는 공부 노트 폴더. 스킬은 읽기만 한다 | Obsidian vault 등 평소 노트를 쓰는 곳 |
| `study_dir` | `학습 로그.md`와 `시험/`, `복습/`, `오답/` | 태블릿 등 다른 기기에서도 열어 필기할 수 있는 동기화 폴더(iCloud Drive 등) |
| `answer_key_dir` | 시험별 정답 키와 `질문 기록.md` | 시험 전에 답이 눈에 띄지 않는 숨김 폴더(이름이 `.`으로 시작) |
| `review_limit` | `test review`가 한 번에 내는 복습 문제 수(선택) | 비워 두면 15 |

진행:
0. `~/.claude/genius.json`이 없고 예전 이름의 `~/.claude/study-kit.json`이 있으면, 그 내용을 보여 주고 `genius.json`으로 복사한다. 예전 파일은 지우지 않고, 지워도 된다고 한 줄로 알린다.
1. 파일이 있으면 현재 값과 각 경로가 실제로 있는지 보여 주고, 바꿀지 묻는다. 바꾸지 않으면 3번으로 간다.
2. 파일이 없으면 후보를 먼저 찾아 제시한다. 예: `~/Library/Mobile Documents/com~apple~CloudDocs/`(iCloud Drive), `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/*/`(iCloud Obsidian vault), `~/Documents` 아래의 `.obsidian` 폴더가 있는 곳. 세 경로를 한 번에 물어 받는다.
3. 다른 PC와 학습 로그를 같이 쓰려면 두 PC의 `study_dir`이 같은 동기화 폴더를 가리켜야 한다고 한 줄로 알린다.
4. `~`가 들어간 경로는 그대로 저장한다(PC마다 홈 폴더가 달라도 쓸 수 있게).

# 3. 폴더와 파일 준비
없는 것만 만든다.
- `<STUDY>/시험`, `<STUDY>/복습`, `<STUDY>/오답`
- `<STUDY>/학습 로그.md`: `<SKILL>/../../references/learning-log-format.md`의 "표 형식" 헤더로 만든다(`<SKILL>`은 이 스킬의 기본 폴더).
- `<KEYS>/`, `<KEYS>/질문 기록.md`: 아래 헤더로 만든다.

```markdown
# 질문 기록

학습 로그의 질문·이해 확인 행에 대한 답 요지. 복습 시험의 출제·채점 근거로 쓴다. 제목은 학습 로그 행의 `날짜 · 노트 · 문제`와 같다.
```

# 4. 중복 점검
플러그인과 같은 이름의 스킬이나 hook이 따로 깔려 있으면 두 벌로 작동한다. 아래가 있으면 보여 주고, 지울지 묻는다. 지우기 전에 스크래치패드에 백업한다.
- `~/.claude/skills/test`, `~/.claude/skills/question`, `~/.claude/skills/study-log`(question의 예전 이름)
- `~/.claude/settings.json`의 hooks에서 `question-reminder.sh`나 예전 이름 `study-log-reminder.sh`를 부르는 항목
- 예전 이름의 플러그인 `study-kit@kimjunyoung90`이 설치되어 있으면 `/plugin uninstall study-kit@kimjunyoung90`으로 지우라고 안내한다(사용자가 직접 실행).

# 5. 마무리
결과를 짧게 요약한다(환경, 경로, 만든 것, 지운 것). 시작 방법을 한 줄로 안내한다: `/genius:test <노트 이름>`으로 첫 시험지를 만든다.
