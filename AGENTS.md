# AGENTS.md — Stock Report Automation Project

> OpenAI Codex 및 AI Agent가 이 프로젝트를 이해하고 작업하기 위한 최상위 지시서입니다.
> ⚠️ **Codex Agent 필수 확인:** 작업을 시작하기 전에 아래의 **[Codex Agent Configuration & Capabilities]** 섹션을 먼저 읽고 권한 및 스킬 환경을 셋업하세요.

---

## 🤖 Codex Agent Configuration & Capabilities

이 프로젝트는 Codex의 능력을 극대화하기 위해 다음과 같은 환경 설정을 권장합니다.

### 1. Sandbox Permissions & Auto Mode

- **권장 실행 모드**: `--full-auto` (또는 `sandbox-write` 허용 모드)
  - 이 프로젝트의 대부분의 작업(웹 크롤링, 외부 API 연동 등)은 네트워크 I/O를 수반합니다.
  - Codex는 로컬 테스트 실행(`python -m pytest`) 시 aiohttp 네트워크 요청이나 Notion/Gemini API 요청이 발생할 수 있음을 인지하고, **관련 네트워크 권한 요청 발생 시 승인(Approve)**하거나 `config.toml`에서 `[sandbox] network = "allow"`를 설정하세요.
- **Hang 주의 (Full-Auto Error Mode)**: `--full-auto` 상태라도 백그라운드로 실행되는 대화형 명령어(`gh pr create --body` 등)는 터미널 행(hang)을 유발합니다. 이 문서의 `Commands` 섹션에 명시된 안전한 우회 명령을 사용하세요.

### 2. Project-Specific Skills (Agent Skills)

이 프로젝트는 `.agents/skills/` 디렉토리에 Codex 전용 스킬을 제공합니다.
다음 작업을 수행할 때 내장된 스킬을 우선적으로 활용하세요:

- **`pr-creator`**: Hang 없이 안전하게 PR을 생성하고 머지하는 스킬
- **`test-coverage`**: 통합 테스트를 실행하고 커버리지를 분석하는 스킬

### 3. Hooks & Automations

- 프로젝트 레벨의 Git Hook 대신, Codex의 Automation 기능을 활용하여 `push` 전에 `tests/test_e2e_dryrun.py`가 성공하는지 확인하는 프로세스를 거칩니다.
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

### Git Flow & PR Creation (⚠️ CRITICAL - Hang 방지)

- 브랜치: `feat/`, `fix/`, `refactor/`, `test/`
- 커밋: Conventional Commits (`feat:`, `fix:` 등) 상세한 본문 작성 필수.
- **PR 생성 시 주의사항**: `gh pr create` 사용 시 `--body` 인라인 파라미터는 프롬프트 무한 대기를 유발합니다. 반드시 파일 기반으로 작성하세요.
  ```bash
  # 🟢 안전한 PR 생성 방법
  echo "PR 내용 상세" > .tmp/pr_body.md
  gh pr create --base master --head <BRANCH> --title "<TITLE>" --body-file .tmp/pr_body.md
  gh pr merge <PR_ID> --squash --delete-branch
  rm -f .tmp/pr_body.md
  ```

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
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 문법 오류 빠른 검증
python -c "import ast; ast.parse(open('src/main.py').read()); print('OK')"
```

## 🏗 Key Architecture

### Pipeline Flow (`main.py`)

1. `asyncio.gather` 병렬 크롤링 (시장지수, 뉴스, Reddit, 커뮤니티, 데이터랩)
2. Gemini API로 글로벌/국내 시황 도출
3. Notion API에서 구독자(`User`) 목록 조회
4. `for user in users:` 루프 내에서 키워드 추출, 캐시 조회, 뉴스 요약
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

# 3. 프로젝트 정상 상태(Green Build) 확인
python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
```

## 📚 Detailed Context Directories

더 깊은 문맥이 필요할 경우 파일을 읽어보세요:

- `.local/HANDOVER.md`: 프로젝트 전체 히스토리, DB 스키마, 알려진 버그.
- `.local/DEPENDENCY_MAP.md`: 리팩토링 시 수정 영향도가 가장 큰 파일 목록.
- `.local/CODEX_GUIDE.md`: 커밋 메시지 템플릿 등 세부 룰.
