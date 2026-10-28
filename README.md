# genius

공부 노트로 시험을 보고, 몰랐던 것을 학습 로그에 쌓아 간격 복습하는 Claude Code 플러그인입니다.

## 들어 있는 것

| 구성 | 하는 일 |
|---|---|
| `setup` 스킬 | 처음 쓰는 PC에서 환경 점검, 경로 설정, 학습 폴더·학습 로그·정답 키 폴더 준비, 예전 방식으로 깔린 스킬과의 중복 점검 |
| `test` 스킬 | 노트로 손글씨용 PDF 시험지 만들기, 채점(`grade`), 해설 확인(`check`), 오답노트, 간격 복습(`review`), 사전 테스트(`pre`) |
| `question` 스킬 | Claude Code를 쓰다가 한 개념 질문, 자기 말 요약, 틀린 이해를 학습 로그에 기록 |
| `UserPromptSubmit` hook | 질문이나 요약처럼 보이는 메시지마다 question 스킬을 쓰라는 알림을 컨텍스트에 넣음 (`/`로 시작하는 명령은 건너뜀) |

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

설치한 뒤 `/genius:setup`을 한 번 실행합니다. PC마다 다른 경로는 `~/.claude/genius.json` 한 곳에만 두고, setup이 물어보고 만듭니다.

```json
{
  "notes_dir": "~/path/to/notes",
  "study_dir": "~/path/to/study",
  "answer_key_dir": "~/path/to/notes/.answer-keys",
  "review_limit": 15
}
```

| 키 | 내용 |
|---|---|
| `notes_dir` | 공부 노트(마크다운) 폴더. 예: Obsidian vault |
| `study_dir` | `학습 로그.md`와 `시험/`, `복습/`, `오답/` PDF 폴더. 여러 기기에서 열 수 있는 동기화 폴더 권장 |
| `answer_key_dir` | 시험별 정답 키와 `질문 기록.md`(질문의 답 요지). 시험 전에 눈에 띄지 않게 숨김 폴더 권장 |
| `review_limit` | 복습 시험 한 번에 낼 문제 수. 생략하면 15 |

예전 이름(study-kit)으로 쓰던 PC는 `/genius:setup`을 실행하면 `~/.claude/study-kit.json`을 `~/.claude/genius.json`으로 복사합니다.

## 하루 흐름

1. `/genius:test <노트>`로 시험지를 만들고 노트 없이 손으로 풉니다.
2. `/genius:test grade`로 채점합니다. 문제마다 해설이 붙은 채점 시험지와 오답노트가 생기고, 모든 문항이 학습 로그에 기록됩니다.
3. 해설을 읽으며 "질문·내 이해" 칸에 적고 `/genius:test check`로 확인받습니다.
4. 시험지를 닫고 오답노트를 자기 말로 씁니다.
5. 복습일에 `/genius:test review`로 복습 시험을 봅니다. 밀린 복습이 많으면 `/genius:test review 20`처럼 문제 수를 정할 수 있습니다. 복습 간격은 1·3·7·14·30·90·180일이고, 180일 복습까지 맞히면 졸업합니다.

시험이나 공부 중이 아니어도, Claude Code를 쓰다가 원리나 차이를 몰라서 한 질문은 question 스킬이 따로 기록합니다. 도구 사용법이나 찾아보면 끝나는 사실은 기록하지 않습니다. 질문은 학습 로그에, 답 요지는 정답 키 폴더의 `질문 기록.md`에 남겨서, 노트에 정리하지 않은 질문도 복습 시험에 나옵니다.
