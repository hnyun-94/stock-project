# AGENTS.md — Stock Report Automation Project

> 최상위 계약서입니다.
> 이 파일은 **핵심 규칙, 최소 작업 흐름, skill/hook 라우팅**만 담습니다.
> 상세 동작 절차와 예시는 `.agents/skills/`, `.githooks/`, `scripts/README.md`를 authoritative source로 사용합니다.

## 📌 Project Overview

한국 주식시장 데이터를 수집하고, AI 요약을 통해 사용자별 리포트를 생성·발송하는 자동화 프로젝트입니다.

- 아키텍처 상세: `README.md`
- 환경변수 기준: `.env.template`
- 현재 계획/이력: `todo/todo.md`, `task/`, `done/`

## 🛠 Tech Stack

- **Runtime**: Python 3.13
- **Package Manager**: uv (`pyproject.toml` + `uv.lock`)
- **AI**: Google Gemini (`google-genai` SDK)
- **Async HTTP**: aiohttp (싱글톤 세션 풀링)
- **Database**: SQLite (WAL mode, `data/stock_project.db`)
- **Prompt Base**: Notion API (동적 프롬프트 DB 조회)
- **Testing**: pytest
- **CI/CD**: GitHub Actions (3h cron)

## Start Here

새 세션이나 작업 시작 시 아래 순서를 따릅니다.

1. 이 파일을 읽습니다.
2. `scripts/session_bootstrap.sh` 또는 `scripts/session_bootstrap.sh --no-tests`를 실행합니다.
3. 작업 성격에 맞는 skill을 선택합니다.
4. 구현성 변경이면 계획서와 품질 게이트 경로를 먼저 확인합니다.

## Core Rules

### Language & Documentation

- 코드, 변수명은 **영어**로 작성합니다.
- 대화, 커밋 메시지 본문, 문서는 **한국어**로 작성합니다.
- 파일 상단에 반드시 **모듈 설명 docstring**을 포함하세요.

### Working Rules

- 임시 파일은 `.tmp/`에만 두고 작업 후 삭제합니다.
- 로컬 전용 산출물은 Git에 올리지 않습니다.
  - 예: `.env`, `data/`, `.local/`, `logging/`, `errorCase/`, `*.db*`, `*.log`
- 반복적으로 등장하는 요구는 ad-hoc으로 끝내지 말고 `AGENTS.md`, `skills`, `hooks`, `scripts`로 승격합니다.
- GitHub Actions, SQLite, cache, env path 같은 런타임 민감 변경은 반드시 `runtime-architecture-review` 기준으로 검토하고 health-check까지 포함합니다.

## Review Model

큰 작업이나 요구사항이 엮인 작업은 기본적으로 `review-driven-execution` 흐름을 사용합니다.

- 기본 검토 역할: PM / TPM / 기획자 / 시니어 개발자 / 개발자 / 품질 담당자 / 신입개발자 / 운영자 / 주식 전문가 / UI/UX 전문가 / 퍼블리셔 전문가
- 프롬프트/지시문/컨텍스트 구조를 다루는 작업은 추가로 아래 관점을 함께 봅니다.
  - 프롬프트 전문가
  - 컨텍스트 엔지니어
- 최소 3회 검토 라운드를 수행하고, 구현성 변경이면 `task/` 또는 `done/`에 근거와 종합 판단을 남깁니다.

## Delivery Flow

코드 변경이 있는 작업은 아래 흐름을 기본으로 따릅니다.

1. 계획서 작성 + 커밋 예산 산정
2. 테스트/문서 먼저 갱신
3. `scripts/run_quality_gate.sh --range origin/master..HEAD`
4. 커밋 + push
5. PR 생성 + 역할별 리뷰
6. `critical` 이슈 수정 후 재검증
7. 사용자가 머지 보류를 명시하지 않았다면 머지
8. `completion-context-triage` 기준으로 종료 context 정리

세부 절차는 아래 skill을 따릅니다.

- 계획/병렬 실행: `review-driven-execution`
- 커밋 예산/PR 운영: `pr-governance`
- PR 생성/머지: `pr-creator`
- 품질 게이트: `e2e-test-suite`
- 종료 시 context 정리: `completion-context-triage`

## Skill Map

작업마다 필요한 skill만 골라 사용합니다.

- `codex-session-setup`: 세션 초기화, 문서 로딩, hook/config 상태 확인
- `review-driven-execution`: 다중 관점 리뷰, 계획서, 병렬 스트림, 구현 전 검토
- `runtime-architecture-review`: Actions/SQLite/cache/workflow/runtime recovery 변경
- `command-permission-governance`: 승인 피로 완화, `uv`/`gh`/고위험 명령 경계 판단
- `e2e-test-suite`: 표준 품질 게이트 실행
- `pr-governance`: 커밋 400줄 정책, 커밋 예산, PR 리뷰 구조
- `pr-creator`: `gh pr create --body-file` 기반 안전한 PR 생성/머지
- `completion-context-triage`: 작업 종료 시 keep/compress/drop 판단과 handoff 정리

## Hooks And Scripts

- `core.hooksPath`는 `.githooks`여야 합니다.
- `pre-push`는 커밋 크기, 문맥 동기화, 리뷰 정책, 변경 Python lint, Git hygiene, `tests/services/` + `tests/test_e2e_dryrun.py`의 authoritative gate입니다.
- hook 우회용 skip 환경변수는 사용하지 않습니다.
- 세부 동작은 `.githooks/pre-push`와 `scripts/README.md`를 봅니다.

## Permission Summary

- 현재 repo 범위의 일반적인 `uv` 명령은 위임 범위입니다.
- 현재 repo 범위의 일반적인 `gh` 협업/조회 명령도 위임 범위입니다.
- 아래는 항상 재확인 대상입니다.
  - secret/credential/.env
  - destructive git
  - schema/data mutation
  - 서버/컨테이너 실행
  - 관리자급 GitHub 명령

정확한 경계는 `command-permission-governance`와 `.codex/config.toml`을 기준으로 합니다.

### Temporary Files

- 임시 분석이나 확인을 위한 파일은 반드시 `.tmp/` 경로 안에 생성하고, 작업 후 즉시 삭제합니다. (`/tmp/` 사용 금지)

## 📍 Session Initialization Steps (Codex MUST DO)

Codex가 새 세션을 시작할 때 다음 명령어를 우선 실행하십시오:

```bash
# 세션 시작
scripts/session_bootstrap.sh
scripts/session_bootstrap.sh --no-tests

# 표준 품질 게이트
scripts/run_quality_gate.sh --range origin/master..HEAD

# 메인 파이프라인 1회 실행
uv run python -m src.main

# 피드백 서버 실행
uv run python -m src.apps.feedback_server
```

## 📚 Project Management Context

더 깊은 문맥이 필요할 경우 파일을 읽어보세요:

- `README.md`: 아키텍처, 디렉토리 구조, 운영 흐름
- `.env.template`: 환경변수 기준선
- `todo/todo.md`: 현재 우선순위
- `task/`: 계획서와 검토 문서
- `done/`: 완료 기준선과 실행 보고
- `.agents/skills/`: 상세 작업 절차
- `.githooks/pre-push`: 실제 강제 규칙
- `scripts/README.md`: 반복 스크립트 설명
