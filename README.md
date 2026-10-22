# study-kit

공부 노트로 시험을 보고, 몰랐던 것을 학습 로그에 쌓아 간격 복습하는 Claude Code 플러그인입니다.

## 들어 있는 것

| 구성 | 하는 일 |
|---|---|
| `test` 스킬 | 노트로 손글씨용 PDF 시험지 만들기, 채점(`grade`), 해설 확인(`check`), 오답노트, 간격 복습(`review`), 사전 테스트(`pre`) |
| `study-log` 스킬 | 공부 중 개념 질문, 자기 말 요약, 틀린 이해를 학습 로그에 기록. 학습 로그 형식의 기준 |
| `UserPromptSubmit` hook | 질문이나 요약처럼 보이는 메시지마다 study-log를 쓰라는 알림을 컨텍스트에 넣음 (`/`로 시작하는 명령은 건너뜀) |

## 요구 사항

- macOS: PDF 변환과 필기 자르기 스크립트가 Swift(WebKit, PDFKit)를 씁니다. Xcode Command Line Tools(`swift`)가 필요합니다.
- `jq`: hook 스크립트가 씁니다 (`brew install jq`).

## 설치

```
/plugin marketplace add kimjunyoung90/study-kit
/plugin install study-kit@study-kit-marketplace
```

## 경로 설정

PC마다 다른 경로는 `~/.claude/study-kit.json` 한 곳에만 둡니다. 없으면 스킬을 처음 쓸 때 물어보고 만듭니다.

```json
{
  "notes_dir": "~/path/to/notes",
  "study_dir": "~/path/to/study",
  "answer_key_dir": "~/path/to/notes/.answer-keys"
}
```

| 키 | 내용 |
|---|---|
| `notes_dir` | 공부 노트(마크다운) 폴더. 예: Obsidian vault |
| `study_dir` | `학습 로그.md`와 `시험/`, `복습/`, `오답/` PDF 폴더. 여러 기기에서 열 수 있는 동기화 폴더 권장 |
| `answer_key_dir` | 정답 키 폴더. 시험 전에 눈에 띄지 않게 숨김 폴더 권장 |

## 하루 흐름

1. `/study-kit:test <노트>`로 시험지를 만들고 노트 없이 손으로 풉니다.
2. `/study-kit:test grade`로 채점합니다. 문제마다 해설이 붙은 채점 시험지와 오답노트가 생기고, 모든 문항이 학습 로그에 기록됩니다.
3. 해설을 읽으며 "질문·내 이해" 칸에 적고 `/study-kit:test check`로 확인받습니다.
4. 시험지를 닫고 오답노트를 자기 말로 씁니다.
5. 복습일에 `/study-kit:test review`로 복습 시험을 봅니다.

시험 밖에서 공부하다 한 질문은 study-log가 따로 기록합니다.
