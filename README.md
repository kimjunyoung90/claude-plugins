# genius

공부 노트로 시험을 보고, 몰랐던 것을 학습 로그에 쌓아 간격 복습하는 Claude Code 플러그인입니다.

## 들어 있는 것

| 구성 | 하는 일 |
|---|---|
| `test` 스킬 | 노트로 손글씨용 PDF 시험지 만들기, 사전 테스트(`pre`), 대화형 시험(`chat`) |
| `grade` 스킬 | 손글씨로 푼 시험지 채점, 문제마다 해설이 붙은 해설지 만들기, 학습 로그 기록 |
| `note` 스킬 | 해설을 읽으며 적은 질문·이해 확인과 오답노트 만들기, 다 쓴 오답노트를 학습 로그로 옮기기(`save`) |
| `review` 스킬 | 복습일이 된 행만 골라 다른 각도로 다시 내는 복습 시험지 만들기 |
| `question` agent | Claude Code를 쓰다가 한 개념 질문, 자기 말 요약, 틀린 이해를 학습 로그에, 알게 된 내용을 TIL에 기록 |
| `UserPromptSubmit` hook | 질문이나 요약처럼 보이는 메시지마다 question agent를 부르라는 알림과 경로를 컨텍스트에 넣음 (`/`로 시작하는 명령은 건너뜀) |

## 요구 사항

- macOS: PDF 변환과 필기 자르기 스크립트가 Swift(WebKit, PDFKit)를 씁니다. Xcode Command Line Tools(`swift`)가 필요합니다.
- `jq`: hook 스크립트가 씁니다. macOS 15 이상은 기본으로 들어 있고(`/usr/bin/jq`), 그 아래면 `brew install jq`.

## 설치

개인 마켓플레이스 [kimjunyoung90/claude-plugins](https://github.com/kimjunyoung90/claude-plugins)로 배포합니다.

```
/plugin marketplace add kimjunyoung90/claude-plugins
/plugin install genius@kimjunyoung90
```

## 경로 설정

플러그인을 켤 때 Claude Code가 아래 값을 물어봅니다. 나중에는 `/config`에서 바꿉니다. 폴더와 학습 로그는 스킬이 처음 쓸 때 만듭니다.

| 설정 | 내용 |
|---|---|
| `notes_path` | TIL(오늘 알게 된 것)이 쌓이고 시험 문제가 나오는 노트 폴더. 예: Obsidian vault 안의 TIL 폴더 |
| `genius_path` | `학습 로그.md`, `시험/`, `복습/`, `오답/` PDF 폴더와 숨김 폴더 `.답안지/`. 여러 기기에서 열 수 있는 동기화 폴더 권장 |
| `review_limit` | 복습 시험 한 번에 낼 문제 수. 기본 15 |

## 하루 흐름

1. `/genius:test <노트>`로 시험지를 만들고 노트 없이 손으로 풉니다.
2. `/genius:grade`로 채점합니다. 문제마다 해설이 붙은 해설지가 생기고, 모든 문항이 학습 로그에 기록됩니다.
3. 해설을 읽으며 "질문·내 이해" 칸에 적고 `/genius:note`를 실행합니다. 적은 것을 확인받고 오답노트를 받습니다.
4. 시험지를 닫고 오답노트를 자기 말로 쓴 뒤, `/genius:note save`로 학습 로그에 옮깁니다.
5. 복습일에 `/genius:review`로 복습 시험지를 만들어 풀고, `/genius:grade`로 채점합니다. 밀린 복습이 많으면 `/genius:review 20`처럼 문제 수를 정할 수 있습니다. 복습 간격은 1·3·7·14·30·90·180일이고, 180일 복습까지 맞히면 졸업합니다.

시험이나 공부 중이 아니어도, Claude Code를 쓰다가 원리나 차이를 몰라서 한 질문은 question agent가 백그라운드에서 따로 기록합니다. 도구 사용법이나 찾아보면 끝나는 사실은 기록하지 않습니다. 질문은 학습 로그에, 알게 된 내용은 노트 폴더의 그날 TIL(`YYYY-MM-DD.md`)에 남겨서, 대화 중 질문도 시험과 복습에 나옵니다.
