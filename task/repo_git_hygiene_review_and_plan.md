# Git 추적 범위 및 민감정보 위생 검토/실행 계획서

작성일: 2026-03-07

## 요청 요약

- 현재 저장소에서 Git으로 관리해야 할 것과 관리하지 말아야 할 것을 구분한다.
- 사용자 개인정보, 운영 흔적, 프로젝트 민감정보가 Git 이력에 남지 않도록 정비한다.
- 여러 차례 검토를 거쳐 추적 대상 기준과 향후 검증 절차를 구조화한다.

## 1차 검토: 현재 위험 노출 지점

### PM 관점

- 사용자/운영 흔적이 섞인 로그와 인수인계 임시 문서는 제품 가치보다 리스크가 크다.
- Git에는 재현 가능한 코드와 정제된 문서만 남고, 세션 중간 흔적은 로컬에 머무는 것이 맞다.

### TPM 관점

- `git ls-files` 기준으로 `.local/`, `logging/`, `errorCase/`가 일부 추적 중이다.
- `.gitignore`에 `logging/`, `errorcase/`는 있으나 이미 추적된 파일은 그대로 남아 있어 정책과 실제 상태가 어긋난다.
- `data/`가 ignore에 없어 SQLite 런타임 DB가 향후 실수로 add될 위험이 있다.

### 기획자 관점

- 장기 보존이 필요한 문맥은 `task/`, `done/`, `requirements/`처럼 정제된 문서면 충분하다.
- 날짜별 로컬 로그/에러 원문은 Git에 들어오지 않아도 된다.

### 개발자 관점

- 로컬 전용 산출물과 repo-managed 문서를 혼용하면 hook와 리뷰 기준이 흐려진다.
- `pre-push`에서 repo hygiene를 검사해야 재발을 막을 수 있다.

### 신입개발자 관점

- "어떤 파일을 커밋하면 안 되는지"가 명시되어 있지 않으면 `.local/`, `data/`, `logging/`을 실수로 올리기 쉽다.

### 운영자 관점

- 로그/에러 파일에는 향후 사용자 이름, 발송 히스토리, 민감 커뮤니티 원문, 절대 경로, 운영 타임라인이 섞일 수 있다.
- 이런 파일은 Git보다 로컬 아카이브가 적절하다.

## 2차 검토: 추적 대상 분류

### Git으로 관리할 것

- `src/`, `tests/`, `.github/`, `.githooks/`
- `AGENTS.md`, `README.md`, `pyproject.toml`, `uv.lock`
- `task/`, `done/`, `requirements/`, `todo/`의 정제된 문서
- `.codex/config.toml`처럼 비밀값이 없는 프로젝트 공통 설정
- `.agents/skills/`, `.agent/workflows/` 같은 재사용 규칙

### Git으로 관리하지 않을 것

- `.env`, `data/`, `*.db`, `*.db-wal`, `*.db-shm`
- `.local/` 인수인계/개인 메모 문서
- `logging/`의 날짜별 작업 로그와 실행 로그
- `errorCase/`, `errorcase/`의 원문 에러 아카이브
- `.tmp/`, 로컬 PR 본문, 로컬 캐시, 생성 산출물

## 3차 검토: 실행 방안

### Round 1

- ignore 규칙과 실제 추적 상태를 맞춘다.
- 이미 추적 중인 `.local/`, `logging/`, `errorCase/`는 `git rm --cached`로 저장소에서만 제거한다.

### Round 2

- 문서/훅 규칙을 로컬 전용 로그 구조에 맞게 갱신한다.
- `check_context_sync.sh`는 더 이상 `logging/`을 Git 문서 동기화 기준으로 요구하지 않게 조정한다.

### Round 3

- `pre-push`에 repo hygiene 스크립트를 추가해 금지 경로, 절대 경로, 실제 이메일 노출을 검사한다.

## 종합 판단

- `.local/`, `logging/`, `errorCase/`는 Git에서 제거하는 것이 타당하다.
- 대신 공유가 필요한 문맥은 `task/`나 `done/`에 정제해서 남긴다.
- 민감정보 재유입 방지를 위해 ignore + hygiene script + hook 3단 방어가 필요하다.

## 구현 범위

1. `.gitignore` 강화 (`.local/`, `errorCase/`, `data/`, `*.db*`)
2. 추적 중인 로컬 전용 파일 untrack
3. `scripts/check_git_hygiene.sh` 추가
4. `.githooks/pre-push`, `scripts/README.md`, `AGENTS.md`, 관련 docs 갱신
5. 로그가 아닌 정제 문서 기준으로 문맥 동기화 규칙 조정

## 수용 기준

- `git ls-files`에 `.local/`, `logging/`, `errorCase/`, `data/`가 남지 않는다.
- `pre-push`가 repo hygiene를 자동 검사한다.
- 로컬 절대 경로나 실제 이메일이 추적 파일에 들어오면 검출된다.
- 표준 테스트와 commit-size 게이트가 모두 통과한다.
