# 기여 가이드

stock-snap은 GitHub Flow로 작업합니다. `main`은 항상 배포 가능한 상태로 두고, 모든 변경은 브랜치와 PR을 거쳐 들어옵니다.

## 작업 흐름
1. 이슈를 만들거나 고른다. 라벨은 유형 1개 + 우선순위 1개 + 영역 1개.
2. `main`에서 브랜치를 만든다.
3. Conventional Commits 형식으로 커밋하고 푸시한다.
4. PR을 열고 템플릿을 채운다. 본문에 `Closes #이슈번호`를 적는다.
5. 리뷰를 받고 `[MUST]` 코멘트를 모두 해결한다.
6. Squash and merge로 머지한다. PR 제목이 main의 커밋 메시지가 된다.

## 브랜치 이름
`<type>/<이슈번호>-<짧은-설명>`

| 예시 | 용도 |
|---|---|
| `feat/12-watchlist` | 새 기능 |
| `fix/21-dashboard-null` | 버그 수정 |
| `docs/20-collab-guide` | 문서 |
| `ci/9-pytest` | 워크플로, CI |

Copilot 코딩 에이전트가 만드는 브랜치는 `copilot/*` 이름을 그대로 쓴다.

## 커밋 메시지 (Conventional Commits)
`<type>: <요약>` 형식. 요약은 짧게, 마침표 없이.

| type | 언제 |
|---|---|
| feat | 새 기능 |
| fix | 버그 수정 |
| docs | 문서만 변경 |
| ci | 워크플로, CI 설정 |
| test | 테스트 추가, 수정 |
| refactor | 동작 변화 없는 코드 정리 |
| chore | 그 밖의 작업 (의존성, 설정) |

예: `feat: 관심 종목 로더 추가`, `ci: PR마다 pytest 실행`

## PR 규칙
- PR 제목도 Conventional Commits 형식으로 쓴다. Squash 머지 시 커밋 메시지가 된다.
- PR 하나는 이슈 하나만 다룬다.
- CI(`test`)가 통과해야 머지한다.

## 리뷰
리뷰 방법과 코멘트 태그는 [docs/REVIEW_GUIDE.md](docs/REVIEW_GUIDE.md)를 따른다.