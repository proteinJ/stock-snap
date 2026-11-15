# CI/CD 워크플로 최적화 전후 비교 리포트

- 대상 PR: [#37 ci: 워크플로 최적화 (재사용·캐싱·선택적 배포)](https://github.com/proteinJ/stock-snap/pull/37)
- 비교 기준: 최적화 전 `5166d54` (#36) / 최적화 후 `c596fce` (#37)
- 측정일: 2026-11-15, GitHub-hosted `ubuntu-latest`, Python 3.12

## 요약

| 항목 | 최적화 전 | 최적화 후 | 효과 |
|---|---|---|---|
| 환경 설정 + 의존성 설치 + pytest (3회 평균) | 15.2초 | 3.3초 | **78.1% 단축** (4.6배 빠름) |
| 워크플로에 직접 쓴 Python 설정 블록 | 4곳 | 0곳 (Composite Action 1개로 통합) | 중복 4곳 제거 |
| `ci.yml` 길이 | 58줄 | 35줄 | 39.7% 감소 |
| 테스트 OS | 2종 (ubuntu, macOS) | 3종 (+ Windows) | Matrix include/exclude로 조합 수 유지 |
| 배포 실행 조건 | main 푸시마다 항상 | 사이트 관련 파일이 바뀐 main 푸시만 | 불필요한 배포 제거 |

## 1. 캐싱 전후 실행 시간

### 측정 방법

[`cache-benchmark.yml`](../../.github/workflows/cache-benchmark.yml)이 같은 커밋, 같은 러너에서 두 job을 동시에 실행합니다.

- `no-cache`: 가상환경을 새로 만들고 `requirements.txt`를 설치한 뒤 pytest 실행
- `with-cache`: `actions/cache`로 `.venv`를 복원(캐시 적중 시 설치 생략)한 뒤 pytest 실행

두 job 모두 "Python 설치 → 의존성 준비 → pytest"를 처음부터 끝까지 잰 시간이고, `report` job이 개선률을 계산해 실행 요약에 출력합니다.

### 결과

| 회차 | 캐시 없음 (초) | 캐시 사용 (초) | cache-hit | 개선률 |
|---|---|---|---|---|
| 1 | 13.7 | 2.4 | true | 82.5% |
| 2 | 16.7 | 4.2 | true | 74.9% |
| 3 | 15.3 | 3.4 | true | 77.8% |
| **평균** | **15.2** | **3.3** | | **78.1%** |

개선률 = (캐시 없음 평균 − 캐시 사용 평균) / 캐시 없음 평균 × 100

실행 기록: [Actions → cache-benchmark](https://github.com/proteinJ/stock-snap/actions/workflows/cache-benchmark.yml)

### 왜 빨라졌나

이전에는 `setup-python`의 `cache: pip`로 **다운로드한 패키지 파일**만 캐시해서, 매번 `pip install`(설치·압축 해제)은 다시 실행했습니다. 이번에는 **설치가 끝난 가상환경(`.venv`) 전체**를 OS, CPU, Python 버전, `requirements.txt` 해시를 키로 캐시합니다. 캐시가 적중하면 `pip install` 단계를 아예 건너뜁니다. `requirements.txt`가 바뀌면 키가 달라져 자동으로 새로 설치합니다.

## 2. 중복 제거 (Composite Action, Reusable Workflow)

### Composite Action: `.github/actions/setup-python-env`

| 워크플로 | 최적화 전 | 최적화 후 |
|---|---|---|
| `ci.yml` (lint) | `setup-python` + `pip install` | `uses: ./.github/actions/setup-python-env` |
| `ci.yml` (test) | `setup-python` + `pip install` | Reusable Workflow로 이동 |
| `deploy.yml` (test) | `setup-python` + `pip install` | Reusable Workflow로 이동 |
| `dora.yml` | `setup-python` + `pip install` | `uses: ./.github/actions/setup-python-env` |

Python 버전이나 캐시 방식을 바꿀 때 고칠 곳이 4곳에서 1곳(`action.yml`)으로 줄었습니다.

### Reusable Workflow: `.github/workflows/reusable-test.yml`

`workflow_call`로 Matrix를 JSON 입력으로 받아 pytest를 실행합니다. 같은 테스트 정의를 두 워크플로가 공유합니다.

- `ci.yml`: 전체 Matrix 6개 조합
- `deploy.yml`: 배포 전 빠른 확인용 1개 조합 (ubuntu, 3.12)

## 3. Matrix 확장

```json
{
  "os": ["ubuntu-latest", "macos-latest"],
  "python-version": ["3.11", "3.12", "3.13"],
  "exclude": [{"os": "macos-latest", "python-version": "3.11"}],
  "include": [{"os": "windows-latest", "python-version": "3.12"}]
}
```

`exclude`로 우선순위가 낮은 조합(macOS 3.11)을 빼고, `include`로 Windows를 추가했습니다. 조합 수는 6개로 같고, 검증하는 OS는 2종에서 3종으로 늘었습니다.

실행 기록: [PR #37 ci 실행](https://github.com/proteinJ/stock-snap/actions/runs/43702398389)

## 4. 선택적 배포 (브랜치/PR 조건, 변경 파일 감지)

| 상황 | 최적화 전 | 최적화 후 |
|---|---|---|
| 사이트 관련 파일이 바뀐 main 푸시 | 배포 | 배포 |
| 문서, 테스트만 바뀐 main 푸시 | 배포 (불필요) | **deploy 워크플로 실행 안 됨** |
| PR | deploy 워크플로 없음 | build, test만 실행, **deploy job 건너뜀** |
| 수동 실행 (dora 워크플로가 호출) | 배포 | 배포 |

- **변경 파일 감지:** `on.push.paths`, `on.pull_request.paths`에 `site/**`, `metrics/**`, 배포 관련 워크플로와 Composite Action만 지정
- **브랜치/PR 조건:** deploy job에 `if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'`

실행 기록
- PR에서 deploy job이 건너뛰어진 실행: [PR #37 deploy 실행](https://github.com/proteinJ/stock-snap/actions/runs/43702398404)
- 문서만 바뀐 PR(이 리포트를 추가한 PR)에서는 deploy 워크플로가 실행되지 않음

## 관련 파일

- [`.github/actions/setup-python-env/action.yml`](../../.github/actions/setup-python-env/action.yml)
- [`.github/workflows/reusable-test.yml`](../../.github/workflows/reusable-test.yml)
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
- [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)
- [`.github/workflows/cache-benchmark.yml`](../../.github/workflows/cache-benchmark.yml)
