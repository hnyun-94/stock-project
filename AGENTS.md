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
- **`command-permission-governance`**: 승인 피로를 줄이기 위한 명령 위험도 분류, wrapper script 도입, 권한 정책 구조화 스킬

### 3. Hooks & Automations

- Git hook은 `.githooks/`를 사용하며 `pre-push`에서 표준 품질 게이트(`tests/services/`, `tests/test_e2e_dryrun.py`)를 검증합니다.
- `pre-push`에서 **커밋당 변경량(추가+삭제) 400줄 초과 여부**를 함께 검증합니다.
- `pre-push`에서 `scripts/check_changed_python_lint.sh`로 **변경한 Python 파일만** Ruff 기본 린트(F/I)를 검사합니다.
- `pre-push`에서 `scripts/check_context_sync.sh`를 통해 문맥 동기화 경고(`task/`, `todo/`, `done/`, `README.md`, `AGENTS.md`)와 런타임 상태 smoke check를 함께 수행합니다.
- `pre-push`에서 `scripts/check_review_policy.sh`로 역할별 검토/근거/판단 문서화가 누락되지 않았는지 검사합니다.
- `pre-push`에서 `scripts/check_git_hygiene.sh`로 금지 경로, 절대 경로, 실제 이메일 노출 여부를 검사합니다.
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
- 모든 비단순 작업은 최소 3회 이상 검토합니다.
  - 1차: 요구사항/가치/범위 검토
  - 2차: 기술/런타임/운영 리스크 검토
  - 3차: 검증 결과/잔여 리스크/대안 기각 사유 검토
- 리뷰 결과는 `task/*.md` 계획서로 구조화하고, 구현 전 병렬 스트림/우선순위/수용 기준을 명시합니다.
- 최종 답변과 공유 문서에는 가능한 한 아래 항목을 명시합니다.
  - 무엇을 선택했는지
  - 왜 그렇게 판단했는지
  - 어떤 근거로 판단했는지
  - 어떤 대안을 검토했고 왜 기각했는지
  - 남은 리스크가 무엇인지
- 작업 도중 중단될 수 있는 변경은 로컬 `logging/YYYY-MM-DD.md`에 중간 결과를 남기되, Git으로 공유가 필요한 내용은 `task/`, `done/`, `README.md`, `AGENTS.md` 같은 정제 문서로 승격합니다.
- GitHub Actions, SQLite, 캐시, workflow, env 기반 상태 저장이 엮인 변경은 항상 **런타임 아키텍처 검토 + health-check**까지 포함합니다.
- 같은 요구가 반복되면 ad-hoc 대응으로 끝내지 말고 `AGENTS.md`, `.agents/skills/`, `.githooks/`, `scripts/`로 승격하여 재사용 가능하게 만듭니다.

### Evidence-Based Review Policy

- 이 프로젝트에서 Codex는 **검토 없는 즉흥 구현**을 하지 않습니다.
- 사용자의 질문/요청에 대한 답변도 가능하면 검토 결과와 판단 근거가 보이도록 작성합니다.
- 구현성 변경이 있으면 `task/` 또는 `done/` 문서에 최소한 다음이 남아 있어야 합니다.
  - 역할별 검토
  - 근거 또는 이유
  - 종합 판단
- 위 규칙은 일시적 요청이 아니라 프로젝트 상시 규칙으로 취급합니다.

### Git Hygiene Policy

- Git에는 코드, 테스트, CI 설정, 템플릿, 정제된 계획/완료 문서만 남깁니다.
- 아래 경로는 **로컬 전용**으로 취급하며 force-add 하지 않습니다.
  - `.env`, `data/`, `.local/`, `logging/`, `errorCase/`, `errorcase/`, `.tmp/`
  - `*.db`, `*.db-wal`, `*.db-shm`, `*.log`, 운영 산출 JSON
- 로컬 로그/에러 원문에는 사용자 정보, 운영 타임라인, 민감 커뮤니티 원문이 섞일 수 있으므로 Git 밖에 둡니다.
- 공유가 필요한 운영 교훈은 원문 로그 대신 `task/` 또는 `done/`에 정제해서 남깁니다.

### Command Permission Policy

이 프로젝트는 live secret(`.env`), 외부 발송, Notion/GitHub write 권한이 함께 있으므로 승인 정책을 무턱대고 완화하지 않습니다.

- **Safe / 기본 자동 실행 대상**
  - `scripts/session_bootstrap.sh`
  - `scripts/run_quality_gate.sh --range origin/master..HEAD`
  - `rg`, `sed`, `cat`, `ls`, `git status`, `git branch`, `git config --get core.hooksPath`
  - `python -m py_compile ...`
  - `scripts/check_commit_size.sh`, `scripts/check_context_sync.sh`, `scripts/check_runtime_state.py`
- **Caution / 조건부 사용**
  - `uv sync --frozen`
  - `git switch -c`, `git add`, `git commit`, `git push -u origin`
  - `gh pr create --body-file`, `gh pr view`, `gh pr merge --squash --delete-branch`
  - 위 명령은 품질 게이트 통과 후 사용하고, hang 방지 규칙을 지킵니다.
- **Delegated uv Commands / 상시 위임 범위**
  - 사용자가 명시적으로 위임한 범위로 간주하고, 별도 재확인 없이 진행합니다.
  - `uv sync`
  - `uv lock`, `uv export`
  - `uv run ...`
  - `uv tool ...`
  - 전제 조건:
    - 실행 목적과 영향 범위를 작업 맥락 안에서 설명할 수 있어야 함
    - 실행 결과와 실패 여부를 최종 응답에 명시해야 함
    - `uv` 바깥의 별도 고위험 명령을 함께 묶지 않아야 함
- **Delegated GitHub Collaboration / 상시 위임 범위**
  - 아래 명령은 일반적인 GitHub 협업 흐름으로 간주하고, 별도 사용자 재확인 없이 진행합니다.
  - `git push origin <branch>`, `git push -u origin <branch>`
  - `gh pr create --body-file`, `gh pr view`, `gh pr checks`, `gh pr merge --squash --delete-branch`
  - `gh run view`, `gh run watch`, `gh workflow view`, `gh repo view`
  - 전제 조건:
    - 로컬 변경 의도와 목적이 명확해야 함
    - 품질 게이트 또는 `pre-push` 자동 검증을 통과해야 함
    - force push, destructive option, 관리자급 설정 변경이 아니어야 함
- **Always Review / 항상 재확인**
  - `.env`, secret, credential, mail account, webhook secret 관련 명령
  - `docker-compose up` 같은 서버/컨테이너 실행
  - `scripts/update_notion_*`, `scripts/provision_prompt_db.py`, schema/data mutation
  - `rm`, `git reset --hard`, `git checkout --`, 대량 삭제/복구
  - `git push --force`, remote branch 삭제, `gh api`, `gh auth`, `gh secret`, `gh variable`
  - repo/admin setting 변경, mass edit, release 삭제 같은 관리자급 GitHub 작업

판단 원칙:

- 승인 피로는 **안전한 명령군을 번들링**하여 줄이고, 고위험 명령의 승인 경계는 유지합니다.
- `.codex/config.toml`은 `workspace-write + network=allow + ask-for-approval=on-request`를 기본으로 유지합니다.
- 사용자가 명시적으로 위임한 `uv` prefix는 반복 작업 비용 절감을 위해 상시 위임 범위로 취급합니다.
- 더 넓은 권한이 필요할 때는 broad allow보다 **좁은 prefix approval** 또는 wrapper script를 우선 고려합니다.

### Git Flow & PR Creation (⚠️ CRITICAL - Hang 방지)

- 브랜치: `feat/`, `fix/`, `refactor/`, `test/`
- 커밋: Conventional Commits (`feat:`, `fix:` 등) 상세한 본문 작성 필수.
- 커밋 크기: **커밋 1개당 변경량(추가+삭제) 400줄 이하** 유지 (기능 단위 분할 원칙).
- 큰 작업은 **계획서 단계에서 커밋 예산(commit budget)** 을 먼저 잡습니다.
  - 각 스트림/커밋 후보별 예상 변경 줄수를 미리 적습니다.
  - 목표치는 400줄보다 낮은 `300~350줄 내외`로 잡아 편집 중 증분을 흡수합니다.
  - 실제 커밋 시에는 이 예산 기준으로 분할하고, 별도 수동 `check_commit_size` 실행은 기본 필수가 아닙니다.
  - 다만 편집 중 범위가 크게 늘었거나 예산 초과가 의심되면 수동 검증을 사용합니다.
- 최종 강제 검증은 `pre-push`와 `run_quality_gate.sh`가 담당합니다.
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

1. 기능 단위 분할, 우선순위 정리, 커밋 예산 산정
2. 품질 게이트 실행 (`uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q`)
  - `scripts/check_changed_python_lint.sh --range origin/master..HEAD`도 함께 고려합니다.
3. 기능 단위 커밋 생성 (Conventional Commit)
  - 커밋은 계획서의 커밋 예산에 맞춰 분리합니다.
  - 수동 `scripts/check_commit_size.sh`는 drift 의심 시에만 사용합니다.
4. 원격 브랜치 push
  - `pre-push`에서 커밋 크기 정책이 자동 검증됩니다.
5. PR 생성 (`gh pr create --body-file`) + 6개 역할 리뷰 섹션 작성
6. 리뷰 이슈 분류/처리 (`critical`은 동일 PR 즉시 수정 후 재검증)
7. 머지 (`gh pr merge --squash --delete-branch`)
8. 후속 문서 갱신 (`todo/todo.md`, `task/*.md`, `done/*.md` 필요 시, 로컬 `logging/YYYY-MM-DD.md`는 선택)

추가 규칙:
- Codex는 기본적으로 위 1~9 단계를 순차 수행합니다.
- 사용자가 “머지 보류”를 명시하지 않는 한, 코드 작업 완료의 기본 종료점은 **머지 완료**입니다.
- 단계 중 하나라도 실패하면 다음 단계로 진행하지 않습니다.

### Temporary Files

- 임시 분석이나 확인을 위한 파일은 반드시 `.tmp/` 경로 안에 생성하고, 작업 후 즉시 삭제합니다. (`/tmp/` 사용 금지)

## 💻 Essential Commands

```bash
# 세션 시작 상태 점검 번들
scripts/session_bootstrap.sh

# 의존성 동기화
uv sync --frozen

# 표준 품질 게이트 번들
scripts/run_quality_gate.sh --range origin/master..HEAD

# 변경한 Python 파일 기본 린트
sh scripts/check_changed_python_lint.sh --range origin/master..HEAD

# 메인 파이프라인 1회 실행
uv run python -m src.main

# 피드백 수집 서버 실행
uv run python -m src.apps.feedback_server

# 런타임 상태(SQLite/Actions 대응) 점검
uv run python scripts/check_runtime_state.py --db-path .tmp/runtime/stock_project.db --label local-check

# 문맥 동기화/런타임 smoke check
scripts/check_context_sync.sh --range origin/master..HEAD

# Git 추적 대상 위생 점검
sh scripts/check_git_hygiene.sh

# 역할별 리뷰/근거 문서화 점검
sh scripts/check_review_policy.sh --range origin/master..HEAD

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
# 기본 세션 초기화
scripts/session_bootstrap.sh

# 빠른 문서/상태 확인만 필요할 때
scripts/session_bootstrap.sh --no-tests
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
- `logging/YYYY-MM-DD.md`: 로컬 전용 작업 이력. Git 공유가 필요한 내용은 `task/` 또는 `done/`으로 승격.
- `.agents/skills/`: 에이전트 자동화 스킬(PR 생성, 테스트 자동화 등) 모음.
