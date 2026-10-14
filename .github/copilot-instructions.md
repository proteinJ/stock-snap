# stock-snap 작업 규칙

- 언어: Python 3.12. 의존성은 requirements.txt에 버전 고정으로 추가한다.
- 디렉터리: 수집/분석 코드는 src/, 워크플로용 스크립트는 scripts/, 정적 사이트는 site/, 테스트는 tests/.
- GitHub API 호출은 환경변수 GITHUB_TOKEN을 사용하고, 토큰을 코드나 로그에 출력하지 않는다.
- 새 함수에는 pytest 테스트를 함께 추가하고, 외부 API는 테스트에서 모킹한다.
- 워크플로의 permissions는 필요한 최소 권한만 명시한다.
- 커밋 메시지는 Conventional Commits(feat:, fix:, ci:, docs:, chore:) 형식을 따른다.
- PR 본문에 변경 요약, 테스트 방법, 관련 이슈 번호(Closes #N)를 적는다.
