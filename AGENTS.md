# AGENTS.md — Stock Report Automation Project

> OpenAI Codex 및 AI Agent가 이 프로젝트를 이해하고 작업하기 위한 최상위 지시서입니다.
> ⚠️ **Codex Agent 필수 확인:** 작업을 시작하기 전에 아래의 **[Codex Agent Configuration & Capabilities]** 섹션을 먼저 읽고 권한 및 스킬 환경을 셋업하세요.

---

## 🤖 Codex Agent Configuration & Capabilities

이 프로젝트는 Codex의 능력을 극대화하기 위해 다음과 같은 환경 설정을 권장합니다.

### 1. Sandbox Permissions & Auto Mode

- **권장 실행 모드**: `--full-auto` (또는 `sandbox-write` 허용 모드)
  - 이 프로젝트의 대부분의 작업(웹 크롤링, 외부 API 연동 등)은 네트워크 I/O를 수반합니다.
  - Codex는 로컬 테스트 실행(`python -m pytest`) 시 aiohttp 네트워크 요청이나 Notion/Gemini API 요청이 발생할 수 있음을 인지하고, **관련 네트워크 권한 요청 발생 시 승인(Approve)**하거나 `.codex/config.toml`에서 `[sandbox] network = "allow"`를 설정하세요.
- **Hang 주의 (Full-Auto Error Mode)**: `--full-auto` 상태라도 백그라운드로 실행되는 대화형 명령어(`gh pr create --body` 등)는 터미널 행(hang)을 유발합니다. 이 문서의 `Commands` 섹션에 명시된 안전한 우회 명령을 사용하세요.

### 2. Project-Specific Skills (Agent Skills)

이 프로젝트는 `.agents/skills/` 디렉토리에 Codex 전용 스킬을 제공합니다.
다음 작업을 수행할 때 내장된 스킬을 우선적으로 활용하세요:

- **`pr-creator`**: Hang 없이 안전하게 PR을 생성하고 머지하는 스킬
- **`pr-governance`**: 기능 단위 PR 분리, 커밋 400줄 제한, 다중 관점 리뷰/머지 의사결정 스킬
- **`e2e-test-suite`**: 커밋/푸시 전 표준 품질 게이트 테스트를 실행하는 스킬
- **`codex-session-setup`**: 프로젝트 관리 문서 로딩 + 상태 점검 + 기준선 테스트를 수행하는 스킬
- **`review-driven-execution`**: PM/TPM/기획/개발/신입/운영 멀티롤 리뷰, 계획서 작성, 병렬 스트림 분리, 중간 로그 기록 후 구현하는 스킬
- **`runtime-architecture-review`**: GitHub Actions, SQLite, 캐시, workflow, 런타임 상태 저장/복구 구조를 검토하고 health-check까지 반영하는 스킬

### 3. Hooks & Automations

- Git hook은 `.githooks/`를 사용하며 `pre-push`에서 표준 품질 게이트(`tests/services/`, `tests/test_e2e_dryrun.py`)를 검증합니다.
- `pre-push`에서 **커밋당 변경량(추가+삭제) 400줄 초과 여부**를 함께 검증합니다.
- `pre-push`에서 `scripts/check_context_sync.sh`를 통해 문맥 동기화 경고(`logging/`, `task/`, `todo/`)와 런타임 상태 smoke check를 함께 수행합니다.
- `pre-push` 품질 게이트/커밋 크기 검증은 우회하지 않습니다. (skip 환경변수 사용 금지)
- `core.hooksPath`는 반드시 `.githooks`로 설정합니다: `git config core.hooksPath .githooks`
- 코드 수정 후 커밋을 생성하기 전, 반드시 테스트 코드를 먼저 갱신하는 것을 원칙으로 합니다.

---

## 📌 Project Overview

한국 주식시장의 뉴스/커뮤니티/시장지수를 자동 수집하고, Google Gemini AI로 요약 분석 후 사용자별 맞춤 리포트를 이메일, 텔레그램으로 발송하는 완전 자동화 파이프라인.

## 🛠 Tech Stack

- **Runtime**: Python 3.13
- **Package Manager**: uv (`pyproject.toml` + `uv.lock`)
- **AI**: Google Gemini (`google-genai` SDK)
- **Async HTTP**: aiohttp (싱글톤 세션 풀링)
- **Database**: SQLite (WAL mode, `data/stock_project.db`)
- **Prompt Base**: Notion API (동적 프롬프트 DB 조회)
- **Testing**: pytest
- **CI/CD**: GitHub Actions (3h cron)

## 🤝 Working Agreements

### Language & Documentation

- 코드, 변수명은 **영어**로 작성합니다.
- 대화, 커밋 메시지 본문, 문서는 **한국어**로 작성합니다.
- 파일 상단에 반드시 **모듈 설명 docstring**을 포함하세요.

### Recurring User Preferences (Structured)

- 사용자가 큰 작업을 요청하거나 요구사항이 엮여 있으면, 기본적으로 **PM / TPM / 기획자 / 개발자 / 신입개발자 / 운영자** 관점 리뷰를 먼저 수행합니다.
- 리뷰 결과는 `task/*.md` 계획서로 구조화하고, 구현 전 병렬 스트림/우선순위/수용 기준을 명시합니다.
- 작업 도중 중단될 수 있는 변경은 `logging/YYYY-MM-DD.md`에 중간 결과와 검증 상태를 남겨 재개 가능 상태를 유지합니다.
- GitHub Actions, SQLite, 캐시, workflow, env 기반 상태 저장이 엮인 변경은 항상 **런타임 아키텍처 검토 + health-check**까지 포함합니다.
- 같은 요구가 반복되면 ad-hoc 대응으로 끝내지 말고 `AGENTS.md`, `.agents/skills/`, `.githooks/`, `scripts/`로 승격하여 재사용 가능하게 만듭니다.

### Git Flow & PR Creation (⚠️ CRITICAL - Hang 방지)

- 브랜치: `feat/`, `fix/`, `refactor/`, `test/`
- 커밋: Conventional Commits (`feat:`, `fix:` 등) 상세한 본문 작성 필수.
- 커밋 크기: **커밋 1개당 변경량(추가+삭제) 400줄 이하** 유지 (기능 단위 분할 원칙).
- PR 본문: 아래 6개 관점 리뷰 섹션 필수
  - PM / TPM / 기획자 / 개발자 / 신입개발자 / 운영자
- 리뷰 정책:
  - `critical` 이슈는 **같은 PR에서 즉시 수정 후** 재리뷰
  - `major`, `minor`는 후속 PR 분리 가능(후속 범위 명시)
- **PR 생성 시 주의사항**: `gh pr create` 사용 시 `--body` 인라인 파라미터는 프롬프트 무한 대기를 유발합니다. 반드시 파일 기반으로 작성하세요.
  ```bash
  # 🟢 안전한 PR 생성 방법
  echo "PR 내용 상세" > .tmp/pr_body.md
  gh pr create --base master --head <BRANCH> --title "<TITLE>" --body-file .tmp/pr_body.md
  gh pr merge <PR_ID> --squash --delete-branch
  rm -f .tmp/pr_body.md
  ```

### Mandatory Delivery Workflow (Codex MUST)

코드 변경이 발생한 작업은 아래 단계가 **모두 완료되어야만 완료 처리**합니다.

1. 기능 단위 분할 및 우선순위 정리
2. 품질 게이트 실행 (`uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q`)
3. 커밋 크기 검증 (`scripts/check_commit_size.sh --range origin/master..HEAD --max-lines 400`)
4. 기능 단위 커밋 생성 (Conventional Commit)
5. 원격 브랜치 push
6. PR 생성 (`gh pr create --body-file`) + 6개 역할 리뷰 섹션 작성
7. 리뷰 이슈 분류/처리 (`critical`은 동일 PR 즉시 수정 후 재검증)
8. 머지 (`gh pr merge --squash --delete-branch`)
9. 후속 문서 갱신 (`todo/todo.md`, `logging/YYYY-MM-DD.md` 필요 시)

추가 규칙:
- Codex는 기본적으로 위 1~9 단계를 순차 수행합니다.
- 사용자가 “머지 보류”를 명시하지 않는 한, 코드 작업 완료의 기본 종료점은 **머지 완료**입니다.
- 단계 중 하나라도 실패하면 다음 단계로 진행하지 않습니다.

### Temporary Files

- 임시 분석이나 확인을 위한 파일은 반드시 `.tmp/` 경로 안에 생성하고, 작업 후 즉시 삭제합니다. (`/tmp/` 사용 금지)

## 💻 Essential Commands

```bash
# 의존성 동기화
uv sync --frozen

# 메인 파이프라인 1회 실행
uv run python -m src.main

# 피드백 수집 서버 실행
uv run python -m src.apps.feedback_server

# 안전한 단위 테스트 실행 (네트워크 불필요)
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 런타임 상태(SQLite/Actions 대응) 점검
uv run python scripts/check_runtime_state.py --db-path .tmp/runtime/stock_project.db --label local-check

# 문맥 동기화/런타임 smoke check
scripts/check_context_sync.sh --range origin/master..HEAD

# Git hook 경로 확인
git config --get core.hooksPath

# 문법 오류 빠른 검증
python -c "import ast; ast.parse(open('src/main.py').read()); print('OK')"
```

## 🏗 Key Architecture

### Pipeline Flow (`main.py`)

1. `asyncio.gather` 병렬 크롤링 (시장지수, 뉴스, Reddit, 커뮤니티, 데이터랩)
2. Gemini API로 글로벌/국내 시황 도출
3. Notion API에서 구독자(`User`) 목록 조회
4. `for user in users:` 루프 내에서 키워드 추출, 캐시 조회, 배치 AI 요약
5. AI 포트폴리오 맞춤 분석 후 마크다운 포맷팅
6. Email / Telegram 비동기 큐(`queue_worker.py`)를 통해 발송

### Resilience Patterns

- **Circuit Breaker**: `src/utils/circuit_breaker.py` (5회 실패 시 차단, 300초 복구)
- **Retry**: `tenacity`를 이용한 `ai_summarizer.py` (3회 지수 백오프)
- **TTL Cache**: 동일 키워드 검색 중복 방지 (`src/utils/cache.py`)

## 🔑 Environment Variables

`.env.template`을 참고하세요. 필수 로컬 테스트 시 `.env` 구성:
`GEMINI_API_KEY`, `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `NOTION_PROMPT_DB_ID`, `WEBHOOK_SECRET`, `SENDER_EMAIL`, `SENDER_APP_PASSWORD`.

## 📍 Session Initialization Steps (Codex MUST DO)

Codex가 새 세션을 시작할 때 다음 명령어를 우선 실행하십시오:

```bash
# 1. 태스크 및 상태 파악
cat todo/todo.md
ls -t logging/ | head -1 | xargs -I{} cat logging/{}

# 2. 형상 관리 상태 확인
git status && git branch

# 3. 훅/설정 상태 확인
git config --get core.hooksPath

# 4. 프로젝트 정상 상태(Green Build) 확인
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
```

## 📚 Project Management Context

더 깊은 문맥이 필요할 경우 파일을 읽어보세요:

- `todo/todo.md`: 현재 우선순위/완료 상태 체크리스트.
- `done/phase6_task.md`: 최적화 단계 Task 상세 명세.
- `task/task.md`: 일반 개발 Task 명세.
- `done/e2e_incident_response_plan.md`: E2E 장애 대응 작업계획서.
- `done/e2e_incident_execution_report.md`: E2E 검증 실행 결과/누락점 체크.
- `done/github_actions_gemini_404_improvement_plan.md`: GitHub Actions Gemini 404 개선 계획.
- `done/github_actions_gemini_404_execution_report.md`: 개선 실행 결과 및 검증 기록.
- `task/github_actions_runtime_review_and_execution_plan.md`: GitHub Actions/SQLite/runtime 상태 유지 검토 및 실행 계획.
- `logging/YYYY-MM-DD.md`: 최근 작업 이력.
- `.agents/skills/`: 에이전트 자동화 스킬(PR 생성, 테스트 자동화 등) 모음.
