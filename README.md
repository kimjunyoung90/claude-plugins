# claude-plugins

Kim Junyoung의 개인 Claude Code 플러그인 마켓플레이스입니다. 플러그인 코드는 각자의 저장소에 있고, 이 저장소에는 목록(`.claude-plugin/marketplace.json`)만 둡니다.

## 추가

```
/plugin marketplace add kimjunyoung90/claude-plugins
```

## 플러그인

| 플러그인 | 설명 | 설치 |
|---|---|---|
| [genius](https://github.com/kimjunyoung90/genius) | 공부 노트로 손글씨 PDF 시험을 보고, 몰랐던 것을 학습 로그에 쌓아 간격 복습 | `/plugin install genius@kimjunyoung90` |

## 플러그인 추가하는 법

`marketplace.json`의 `plugins`에 항목을 하나 추가합니다. 플러그인 저장소 루트에 `.claude-plugin/plugin.json`이 있으면 `source`를 `{"source": "url", "url": "https://github.com/<owner>/<repo>.git"}`로, 저장소의 하위 폴더에 있으면 `{"source": "git-subdir", "url": "...", "path": "plugins/<name>"}`로 적습니다.
