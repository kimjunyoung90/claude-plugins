---
name: feedback
description: genius 플러그인에 대한 불편이나 문제를 개발자에게 보내는 스킬. 사용자의 말을 GitHub Issue 양식(문제 신고·개선 제안)에 맞게 정리하고, 공부 내용을 뺀 뒤 미리 채운 Issue 작성 화면을 브라우저로 연다. 제출은 사용자가 직접 한다. 사용자가 "피드백", "/genius:feedback", "개발자한테 알려줘", "이거 버그 같아"라고 하면 사용한다
argument-hint: "[피드백 내용]"
disable-model-invocation: false
---

플러그인을 쓰다 생긴 불편을 개발자에게 전하는 스킬이다. 개발자는 GitHub 저장소의 Issues로 피드백을 받는다. 이 스킬은 Issue를 대신 올리지 않고, 작성 화면을 미리 채워 열어 준다. 공개 저장소에 무엇이 올라가는지 사용자가 마지막에 눈으로 확인하고 제출하게 하기 위해서다.

# 경로
`<SKILL>`은 이 스킬의 기본 폴더, `<ROOT>`는 플러그인 루트(`<SKILL>/../..`)다.
- 저장소와 버전: `<ROOT>/.claude-plugin/plugin.json`의 `repository`, `version`
- Issue 양식: `<ROOT>/.github/ISSUE_TEMPLATE/bug.yml`(문제 신고), `feature.yml`(개선 제안). 칸의 `id`가 URL 매개변수 이름이다.

# 1. 내용 모으기
- 인자가 있으면 그것을 피드백으로 쓴다.
- 인자가 없으면 이 대화에서 genius를 쓰다 생긴 문제(잘못된 채점, 깨진 PDF, 노트에 없는 문제 등)를 찾아 그것으로 할지 한 줄로 묻는다. 대화에 없으면 무엇이 불편했는지 묻는다.
- 재현에 필요한데 빠진 것(어느 스킬에서, 무엇을 기대했는지)만 한 번에 묻는다. 모르면 비워 둔다.

# 2. 종류 나누기
| 종류 | 예 | 처리 |
|---|---|---|
| 문제 신고 | PDF가 깨짐, 스크립트 오류, 필기를 잘라내지 못함, 노트에 없는 내용을 물음 | `bug.yml` |
| 개선 제안 | 해설이 너무 김, 단답형이 많음, 복습 문제 수를 날마다 다르게 하고 싶음 | `feature.yml` |
| 내 기록 정정 | "3번 맞았는데 오답 처리됐어" | Issue로 보내지 않는다. 답안지와 노트를 다시 보고 판정을 바꿀 근거가 있으면 `<ROOT>/references/grading.md`에 따라 학습 로그 행을 고친다(`${user_config.genius_path}/학습 로그.md`). 같은 오판이 되풀이되면 채점 기준의 문제로 보고 개선 제안으로 보낼지 묻는다 |

# 3. 초안 만들기
1. 양식의 칸마다 내용을 채운다. 제목은 양식의 접두어(`[문제] `, `[제안] `) 뒤에 한 줄 요약을 붙인다.
2. **공부 내용과 개인 정보를 뺀다.** 노트 원문, 문제와 답안 원문, 학습 로그 내용, 로컬 경로, 사람 이름, 회사 이름은 넣지 않는다. "노트에 없는 개념을 물었다", "3문항 중 1문항의 필기가 잘렸다"처럼 일반화한다. 재현에 특정 개념 이름이 꼭 필요하면 넣어도 되는지 묻는다.
3. 버전과 환경은 직접 모은다: `plugin.json`의 `version`, `sw_vers -productVersion`, `claude --version`.
4. 초안을 대화창에 보여 준다.

# 4. 작성 화면 열기
URL은 `<repository>/issues/new?template=<양식 파일>&title=...&<칸 id>=...`이다. 값은 URL 인코딩한다.
```bash
python3 -c 'import sys, urllib.parse as u; base, tpl, *kv = sys.argv[1:]; print(base + "/issues/new?" + u.urlencode([("template", tpl)] + [tuple(x.split("=", 1)) for x in kv]))' \
  "<repository>" bug.yml "title=[문제] ..." "skill=..." "what=..." "expected=..." "steps=..." "version=..." "env=..."
open "<URL>"
```
- 사용자에게 "브라우저에서 내용을 확인하고 Submit new issue를 누르면 개발자에게 전달된다"고 알린다. GitHub 계정이 필요하다.
- URL이 너무 길면(약 6000자 넘음) 긴 칸은 비워서 열고, 그 칸에 붙여 넣을 본문을 대화창에 준다.
- `open`이 안 되는 환경이면 URL을 그대로 준다.

# 주의
- 응답은 한국어로 하고, 부연 설명에 em-dash(—)를 쓰지 않는다.
- Issue를 직접 올리지 않는다(`gh issue create` 금지). 제출은 항상 사용자가 브라우저에서 한다.
- 쓰기는 기록 정정일 때의 학습 로그에만 한다.
