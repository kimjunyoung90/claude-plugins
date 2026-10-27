# claude-plugins

Kim Junyoung의 개인 Claude Code 플러그인 마켓플레이스입니다. 플러그인 코드는 모두 이 저장소의 `plugins/` 아래에 있습니다.

## 추가

```
/plugin marketplace add kimjunyoung90/claude-plugins
```

## 플러그인

| 플러그인 | 설명 | 설치 |
|---|---|---|
| [genius](plugins/genius) | 공부 노트로 손글씨 PDF 시험을 보고, 몰랐던 것을 학습 로그에 쌓아 간격 복습 | `/plugin install genius@kimjunyoung90` |
| [todo](plugins/todo) | 지라 기반 할 일 관리 — 할 일 추가·시작·완료와 작업 내역 기록 | `/plugin install todo@kimjunyoung90` |

## 플러그인 추가하는 법

`plugins/<name>/`에 플러그인을 만들고(`.claude-plugin/plugin.json` 포함), `marketplace.json`의 `plugins`에 `{"name": "<name>", "source": "./plugins/<name>"}` 항목을 추가합니다.
