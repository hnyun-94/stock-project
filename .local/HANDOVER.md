# 📋 Stock-Project Codex 인수인계서 (Handover Document)

> 이 문서는 Codex(또는 후임 AI Agent)가 이 프로젝트를 이해하고 즉시 작업을 시작할 수 있도록
> 프로젝트의 전체 구조, 아키텍처, 개발 규칙, 운영 방식을 상세히 기술한 인수인계 문서입니다.
> Codex 표준 가이드는 프로젝트 루트의 `AGENTS.md`를 참조합니다.
> 최종 갱신: 2026-03-07

---

## 1. 프로젝트 개요

### 1.1 목적

매일 한국 주식시장의 뉴스, 커뮤니티 반응, 시장 지수, 검색 트렌드를 자동으로 수집하고,
Google Gemini AI로 요약 분석한 후 사용자별 맞춤형 리포트를 이메일/텔레그램으로 발송하는
**완전 자동화 주식 리포트 시스템**입니다.

### 1.2 기술 스택

| 구분          | 기술                                                                         |
| ------------- | ---------------------------------------------------------------------------- |
| 런타임        | Python 3.13                                                                  |
| 패키지 관리   | uv (pyproject.toml + uv.lock)                                                |
| AI            | Google Gemini API (google-genai SDK, 모델: `gemini-1.5-flash`)               |
| 크롤링        | aiohttp (비동기), BeautifulSoup4, Playwright (동적 페이지), feedparser (RSS) |
| 데이터저장    | SQLite (WAL mode, `data/stock_project.db`) — 런타임에 자동 생성              |
| 프롬프트 관리 | Notion API (동적 프롬프트 DB) + 로컬 fallback (`src/prompts/`)               |
| 사용자 관리   | Notion API (수신자 DB)                                                       |
| 알림 채널     | Email (SMTP/Gmail), Telegram Bot                                             |
| 피드백        | FastAPI 서버 (`src/apps/feedback_server.py`) — `GET /api/feedback`           |
| 컨테이너      | Docker + Docker Compose (2 services: feedback-server, crawler-pipeline)      |
| CI/CD         | GitHub Actions (3시간 주기 cron, `report_scheduler.yml`)                     |
| 테스트        | pytest (70개 테스트, 0.3초)                                                  |
| Lint          | ruff (PEP8 + isort + pydocstyle Google style)                                |

### 1.3 동작 흐름 (Pipeline)

`src/main.py` → `run_pipeline()` → `main_with_timeout()` (전체 300초 타임아웃)

```
[0] Notion에서 프롬프트 캐싱 (asyncio.to_thread 래핑)
    + Message Queue Worker 시작 (3개 스레드)
        ↓
[1] 공통 데이터 수집 (asyncio.gather 5개 병렬)
    ├── get_market_indices()        → List[MarketIndex]
    ├── get_market_news()           → List[NewsArticle]
    ├── get_dc_stock_gallery(3)     → List[CommunityPost]
    ├── get_reddit_wallstreetbets(3) → List[CommunityPost]
    └── get_naver_datalab_trends()  → List[SearchTrend]
        ↓
[2] AI 시장 시황 요약 (Gemini) → market_summary_md: str
        ↓
[3] Notion에서 수신 대상자 조회 (asyncio.to_thread)
    → users: List[User]
        ↓
[3.5] 공통 테마 브리핑 생성
    ├── generate_theme_briefing("글로벌+국내 시장 민심")
    ├── analyze_sentiment() → 감정 지표
    └── generate_backtesting_report() → 적중률 분석
        ↓
[4] 사용자별 맞춤 루프 (for user in users):
    ├── 키워드 뉴스 수집 (캐시 체크 → 미스만 병렬 크롤링)
    │   ├── search_news_by_keyword()       (네이버)
    │   ├── search_daum_news_by_keyword()  (다음)
    │   └── search_google_news_by_keyword() (구글 RSS)
    ├── deduplicate_news() → 85% 유사도 필터
    ├── enrich_news_with_leads() → 본문 리드 문단 추출
    ├── crawl_cache.set() → TTL 캐시 저장
    ├── generate_theme_briefing() × 키워드 수 → 병렬 AI 분석
    ├── generate_personalized_portfolio_analysis() → (보유 종목 있을 때)
    ├── record_prediction_snapshot() → DB 저장
    ├── build_markdown_report() → 최종 리포트 조합
    └── generate_feedback_links_html() → HMAC 서명 별점 링크
        ↓
[5] 채널별 발송 (큐 워커)
    ├── EmailSender.send()     → SMTP/Gmail
    └── TelegramSender.send()  → Bot API (현재 비활성화)
        ↓
[6] 정리
    ├── global_message_queue.join() → 모든 발송 완료 대기
    ├── close_session()            → aiohttp 세션 닫기
    └── BrowserPool.cleanup()      → Playwright 정리
```

### 1.4 실행 방법

```bash
# 로컬 실행 (파이프라인)
uv run python -m src.main

# 로컬 실행 (피드백 서버)
uv run python -m src.apps.feedback_server

# Docker 실행
docker-compose up --build

# GitHub Actions (자동)
# push to master 또는 3시간 cron 또는 수동 workflow_dispatch
```

---

## 2. 디렉토리 구조

```
stock-project/
├── AGENTS.md                  # ⭐ Codex 표준 가이드 (프로젝트 루트)
├── .github/workflows/
│   └── report_scheduler.yml   # 3시간 주기 cron + push + manual
├── .agents/workflows/         # Antigravity Agent 워크플로우
│   ├── context-management.md
│   └── safe-terminal.md
├── .local/                    # Codex 인수인계 문서 (이 폴더)
│   ├── HANDOVER.md            # ← 이 문서 (프로젝트 전체 맥락)
│   ├── CODEX_GUIDE.md         # 실행 가이드/템플릿
│   └── DEPENDENCY_MAP.md      # 모듈 의존성/영향도
├── .tmp/                      # 임시파일 (gitignore됨)
├── data/                      # SQLite DB (런타임 자동 생성, gitignore됨)
├── errorCase/                 # 프로덕션 에러 기록 (날짜별)
├── logging/                   # 작업 로그 (날짜별)
├── requirements/              # 요구사항 문서 (4개, Phase 1~6)
├── scripts/                   # 일회성 유틸리티 스크립트 (Notion 검증, DB 테스트 등)
├── task/                      # Task 명세서 (task.md, phase6_task.md)
├── tests/                     # 테스트 코드
│   ├── services/              # 서비스 단위 테스트 (8파일, 63개)
│   ├── test_e2e_dryrun.py     # E2E 통합 테스트 (7개)
│   ├── crawlers/              # 크롤러 테스트 (aiohttp 라이브 필요)
│   ├── mocked/                # VCR 기반 Mock 테스트
│   └── load/                  # 부하 테스트 (locust)
├── todo/
│   └── todo.md                # ⭐ 작업 체크리스트 (항상 최신 유지)
├── src/
│   ├── models.py              # 공통 DTO (5개 dataclass)
│   ├── main.py                # 파이프라인 진입점 (asyncio.run)
│   ├── alert_daemon.py        # 실시간 알림 데몬 (실험적, 미사용)
│   ├── crawlers/              # 비동기 데이터 수집 (11개 모듈)
│   ├── services/              # 비즈니스 로직 (9개 모듈 + notifier 4개)
│   ├── utils/                 # 인프라 유틸리티 (8개 모듈)
│   ├── prompts/               # 프롬프트 템플릿 3개 (Notion fallback)
│   └── apps/
│       └── feedback_server.py # FastAPI 별점 수신 서버
├── pyproject.toml             # 의존성 정의
├── uv.lock                    # uv 락 파일
├── Dockerfile
├── docker-compose.yml         # 2 services: feedback-server, crawler-pipeline
└── .env.template              # ⭐ 환경변수 템플릿 (모든 키 + 발급 가이드)
```

---

## 3. 핵심 아키텍처 패턴

### 3.1 데이터 모델 (DTO)

`src/models.py`에 5개의 `@dataclass` DTO:

- `NewsArticle` — 뉴스 기사 `(title, link, summary?, date?, publisher?)`
- `MarketIndex` — 시장 지수 `(name, value, change, investor_summary="")`
- `CommunityPost` — 커뮤니티 게시글 `(title, link, views?, likes?)`
- `SearchTrend` — 검색 트렌드 `(keyword, traffic?, news_title?, news_link?)`
- `User` — 수신 대상자 `(name, email, keywords, telegram_id?, channels=["email"], holdings=[], alert_threshold?)`

### 3.2 비동기 처리

- 모든 크롤러는 `async/await` 기반
- `aiohttp.ClientSession` 싱글톤 (`http_client.py`)으로 커넥션 풀링
- `asyncio.gather()`로 병렬 크롤링 (return_exceptions=True)
- Notion 동기 API는 `asyncio.to_thread()`로 래핑
- Gemini 동시 호출은 `asyncio.Semaphore(2)`로 제한

### 3.3 장애 내성 패턴 (상세)

| 패턴              | 파일                 | 설정                  | 동작                                                          |
| ----------------- | -------------------- | --------------------- | ------------------------------------------------------------- |
| Circuit Breaker   | `circuit_breaker.py` | fail=5, recovery=300s | 5회 연속 실패 → Open → 300초 후 Half-Open → 1회 성공 시 Close |
| Retry (Tenacity)  | `ai_summarizer.py`   | 3회, exp(3, 5~30s)    | 실패 시 5→15→30초 대기 후 재시도, before_sleep 로그           |
| Semaphore         | `ai_summarizer.py`   | 2 concurrent          | Gemini API 분당 요청 제한 방어                                |
| TTL Cache         | `cache.py`           | 300s, max_size=128    | 동일 키워드 크롤링 결과 재사용                                |
| Graceful Fallback | `community.py`       | REDDIT_ENABLED env    | 403 시 빈 리스트 반환 + WARNING 로그                          |
| Global Timeout    | `main.py` L227       | 300s                  | 전체 파이프라인 5분 제한                                      |
| Request Timeout   | 각 크롤러            | 10~30s                | 개별 HTTP 요청 타임아웃                                       |

### 3.4 데이터 저장 (SQLite)

`src/utils/database.py` — 싱글톤 패턴, WAL 모드, `data/stock_project.db`

3개 테이블:

```sql
-- 사용자 별점 피드백
feedbacks (id INTEGER PRIMARY KEY, timestamp TEXT, user_name TEXT, score INTEGER, comment TEXT)

-- AI 예측 스냅샷 + 적중률
prediction_snapshots (id INTEGER PRIMARY KEY, timestamp TEXT, user_name TEXT, holdings TEXT,
                      analysis_snip TEXT, accuracy_score REAL)

-- A/B 테스트 프롬프트 사용 이력
prompt_usage_log (id INTEGER PRIMARY KEY, user_name TEXT, prompt_type TEXT,
                  version TEXT, timestamp TEXT)
```

Database API 주요 메서드:

- `get_db()` → 싱글톤 인스턴스 반환 (스레드 안전)
- `insert_feedback(user, score, comment)` / `get_recent_feedbacks(days)` / `get_average_score(days)`
- `insert_snapshot(user, holdings, text)` / `get_recent_snapshots(limit)`
- `update_snapshot_score(id, score)` / `get_average_accuracy(days)` / `get_unscored_snapshots(limit)`

### 3.5 알림 시스템

Strategy 패턴 (`notifier/base.py` → `email.py`, `telegram.py`)
비동기 큐 워커(`queue_worker.py`)로 발송 작업 비동기 처리 (3개 워커 스레드)

현재 상태:

- ✅ Email (SMTP/Gmail) — 활성화
- ⏸️ Telegram — 코드 존재하지만 `main.py`에서 비활성화 (주석 처리)

### 3.6 프롬프트 시스템

3단계 프롬프트 파이프라인:

1. **Notion DB 동적 프롬프트** (우선): `prompt_manager.py` → `fetch_prompts_from_notion()`
   - `NOTION_PROMPT_DB_ID`에서 프롬프트 조회 → 메모리 캐시
2. **로컬 fallback 템플릿**: `src/prompts/*.md`
   - `market_summary.md` — 변수: `{context_indices}`, `{context_news}`, `{context_trends}`
   - `theme_briefing.md` — 변수: `{keyword}`, `{context_news}`, `{context_community}`
   - `portfolio_analysis.md` — 변수: `{holdings}`, `{market_summary}`, `{theme_briefings}`
3. **자동 튜닝** (`prompt_tuner.py`): 최근 30일 평균 별점 기반
   - 3.5점 이하 → temperature 상향 + "분석 비중↑" 스타일 힌트
   - 4.5점 이상 → 현재 설정 유지

### 3.7 피드백 서버 API

FastAPI 기반 (`src/apps/feedback_server.py`)

```
GET /api/feedback?user={name}&score={1-5}&signature={hmac_sha256}
```

동작:

1. `WEBHOOK_SECRET`으로 HMAC-SHA256 서명 검증 (`user:score` 형식)
2. 유효 → `database.insert_feedback()` 저장
3. HTML 응답 ("소중한 의견 감사합니다!")
4. 무효 → 403 응답 ("잘못된 접근")

⚠️ 서버 시작 시 `WEBHOOK_SECRET` 미설정이면 RuntimeError로 즉시 중단

---

## 4. 환경 변수 (필수)

`.env.template` 파일에 전체 목록과 **발급 방법이 상세히** 기술되어 있습니다.

| 변수                     | 용도                                           | 필수 |
| ------------------------ | ---------------------------------------------- | :--: |
| `GEMINI_API_KEY`         | Google Gemini AI API                           |  ✅  |
| `NOTION_TOKEN`           | Notion Integration Token (`secret_...`)        |  ✅  |
| `NOTION_DATABASE_ID`     | 사용자 관리 Notion DB (32자리)                 |  ✅  |
| `NOTION_PROMPT_DB_ID`    | 프롬프트 관리 Notion DB (32자리)               |  ✅  |
| `SENDER_EMAIL`           | Gmail 발신 계정                                |  ✅  |
| `SENDER_APP_PASSWORD`    | Gmail 앱 비밀번호 (16자리)                     |  ✅  |
| `WEBHOOK_SECRET`         | 피드백 HMAC 시크릿 (`openssl rand -hex 32`)    |  ✅  |
| `FEEDBACK_BASE_URL`      | 피드백 서버 외부 URL                           |  ✅  |
| `TELEGRAM_BOT_TOKEN`     | Telegram Bot API                               | 선택 |
| `ADMIN_TELEGRAM_CHAT_ID` | Telegram 관리자 Chat ID                        | 선택 |
| `NAVER_CLIENT_ID`        | 네이버 데이터랩 API                            | 선택 |
| `NAVER_CLIENT_SECRET`    | 네이버 데이터랩 API                            | 선택 |
| `REDDIT_ENABLED`         | Reddit 크롤링 토글 (CI: `false`, 기본: `true`) | 선택 |

---

## 5. 개발 규칙 (MUST FOLLOW)

### 5.1 언어 규칙

- **모든 답변, 과정, 문서는 한국어**로 작성
- **코드, 변수명은 영어** (커밋 제목은 한/영 혼용 가능)
- 파일 상단에 항상 모듈 설명 docstring 포함

### 5.2 Git 규칙

- 모든 작업은 **feature 브랜치** → **PR** → **squash merge** → **delete branch** 흐름
- 브랜치 네이밍: `feat/기능명`, `fix/버그명`, `refactor/리팩토링명`, `test/테스트명`
- 커밋 메시지: Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`)
- 커밋 body에 **변경 내용을 신입 개발자가 이해할 수 있는 수준으로 상세히 기술**
- PR body에 3관점 리뷰 포함 (개발자/검토자/운영자)

### 5.3 PR 워크플로우 (⚠️ hang 방지 필수)

```bash
# 1. 브랜치 생성
git checkout -b feat/기능명

# 2. 코드 작성 + 테스트 통과 확인
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 3. 커밋 (상세 메시지)
git add 파일들 && git commit -m "feat: 한줄 설명 [Task x.x, REQ-xxx]

## 변경 내용
### 신규/수정: 파일경로
- 변경 내용 상세"

# 4. Push + PR 생성 (⚠️ 반드시 body-file 사용)
git push -u origin feat/기능명
echo "PR 내용" > .tmp/pr_body.md
gh pr create --base master --head feat/기능명 --title "..." --body-file .tmp/pr_body.md

# 5. Merge + 브랜치 삭제
gh pr merge N --squash --subject "..." --delete-branch

# 6. 임시파일 정리
rm -f .tmp/pr_body.md
```

### 5.4 테스트 규칙

- 새 모듈 추가 시 반드시 단위 테스트 함께 작성
- 테스트 파일 위치: `tests/services/test_모듈명.py`
- 로거 Mock 패턴 (테스트 파일 상단에 반드시 포함):
  ```python
  import sys
  from unittest.mock import MagicMock
  sys.modules['src.utils.logger'] = MagicMock()
  ```
- 서비스 테스트: `python -m pytest tests/services/ tests/test_e2e_dryrun.py -v`
- 크롤러 테스트: `python -m pytest tests/crawlers/ -v` (aiohttp 라이브 필요)

### 5.5 로깅 규칙

- 작업 완료 시 `logging/YYYY-MM-DD.md`에 작업시간 + 내용 기록
- 에러 발생 시 `errorCase/YYYY-MM-DD_에러명.md`에 상황 + 조치 기록
- `todo/todo.md`는 항상 최신 상태 유지 (완료 시 `[x]` + PR 번호 표기)

### 5.6 임시파일 규칙

- 임시파일은 **프로젝트 내 `.tmp/` 디렉토리**에 생성
- 사용 후 즉시 삭제
- `/tmp/` 사용 금지
- `.tmp/`는 `.gitignore`에 등록됨

### 5.7 터미널 안전 규칙 (⚠️ Codex 필수)

- `gh pr create`는 반드시 `--body-file` 사용 (인라인 `--body` → **hang 원인**)
- 대화형 명령 (`vi`, `nano`, `less`, `more`) **절대 사용 금지**
- 장시간 명렁은 타임아웃 설정 필수
- Python REP 실행 금지 (코드 검증은 `python -c "import ast; ..."` 사용)

---

## 6. 테스트 현황

### 6.1 테스트 파일 목록 (70개)

| 파일                        | 테스트 수 | 내용                                         |
| --------------------------- | :-------: | -------------------------------------------- |
| `test_cache.py`             |     8     | TTLCache 동작, TTL 만료, 최대 크기, 덮어쓰기 |
| `test_database.py`          |     9     | SQLite CRUD, 스코어링, 적중률 통계           |
| `test_deduplicator.py`      |     9     | 제목 정규화, 유사도, 중복 제거               |
| `test_feedback_manager.py`  |     7     | HMAC 서명 생성/검증, 피드백 링크             |
| `test_notifier.py`          |     4     | Email/Telegram 발송, env 미설정              |
| `test_sentiment.py`         |    11     | 감정 점수, 레이블, 게이지 포맷               |
| `test_prompt_tuner.py`      |     5     | 자동 튜닝, 스타일 힌트                       |
| `test_prompt_versioning.py` |     6     | A/B 그룹 배정, 이력 기록, 통계               |
| `test_e2e_dryrun.py`        |     7     | 데이터 흐름 통합, 캐시+중복제거              |
| **합계**                    |  **70**   | **실행 시간: 0.3초**                         |

### 6.2 실행 명령

```bash
# 표준 (서비스 + E2E)
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 전체 (aiohttp/playwright 라이브 필요)
python -m pytest tests/ -v

# 특정 파일
python -m pytest tests/services/test_cache.py -v

# 문법 검증만 (테스트 없이)
python -c "import ast; ast.parse(open('파일경로').read()); print('OK')"
```

---

## 7. CI/CD (GitHub Actions)

### 7.1 워크플로우 상세 (`report_scheduler.yml`)

```yaml
name: Stock Report Automation (Every 3 Hours)
on:
  push: { branches: [main, master] }
  schedule: [{ cron: "0 */3 * * *" }] # KST: 00,03,06,...,21시
  workflow_dispatch: {} # 수동 실행
jobs:
  build-and-run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - checkout@v4
      - setup-python@v5 (3.13)
      - uv 설치 + uv sync --frozen
      - uv run python -m src.main (env: 9개 Secrets 주입)
```

### 7.2 필요한 GitHub Secrets

```
GEMINI_API_KEY, NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_PROMPT_DB_ID,
SENDER_EMAIL, SENDER_APP_PASSWORD, WEBHOOK_SECRET,
NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
```

### 7.3 알려진 이슈 및 TODO

- ❌ `REDDIT_ENABLED: false` 미적용 (워크플로우에 환경변수 추가 필요)
- ❌ `FEEDBACK_BASE_URL`, `ADMIN_TELEGRAM_CHAT_ID` 미주입
- ❌ 테스트 Job 미분리 (현재 파이프라인만 실행)

### 7.4 Docker Compose 구성

```yaml
services:
  feedback-server: # FastAPI 피드백 수신 (8000 포트)
    command: uv run python -m src.apps.feedback_server
    ports: ["8000:8000"]
    env_file: .env

  crawler-pipeline: # 리포트 생성 파이프라인
    command: uv run python -m src.main
    env_file: .env
```

---

## 8. 완료된 작업 이력 (Phase 1~6)

### Phase 1~5 (2026-02 초~중순)

- 크롤러 개발, Gemini AI 요약, 이메일/텔레그램 발송, Notion 통합
- 피드백 시스템, Docker 배포, 실시간 알림 데몬 (실험적)

### Phase 6: 성능 및 기능 최적화 (2026-03-02 ~ 03-05)

| PR  | 내용                             | 카테고리        |
| :-: | -------------------------------- | --------------- |
| #1  | HMAC 서명 + 타임아웃 + 보안 강화 | 🔧 Bugfix       |
| #2  | aiohttp 세션 풀링                | ⚡ Performance  |
| #3  | Gemini 싱글톤                    | ⚡ Performance  |
| #4  | Docker env_file                  | 🔧 Infra        |
| #5  | 크롤링 병렬화                    | ⚡ Performance  |
| #6  | BrowserPool 해제                 | 🔧 Infra        |
| #7  | 루트 스크립트 정리               | 🧹 Cleanup      |
| #8  | TTL 캐시                         | ⚡ Performance  |
| #9  | 뉴스 중복 제거                   | 📊 Data Quality |
| #10 | Notion 비동기화                  | ⚡ Performance  |
| #11 | 뉴스 리드 문단                   | 📊 Feature      |
| #12 | 서비스 테스트 28개               | ✅ Quality      |
| #13 | E2E 드라이런 7개                 | ✅ Quality      |
| #14 | 감정 지표                        | 📊 Feature      |
| #15 | JSON→SQLite                      | ⚡ Data         |
| #16 | 백테스팅 정량화                  | 📊 Feature      |
| #17 | 자동 프롬프트 튜닝               | 🤖 AI           |
| #18 | A/B 테스트                       | 🤖 AI           |
| #19 | Gemini/Reddit 장애 대응          | 🔧 Hotfix       |

---

## 9. 미완료 Task / 향후 과제

| 항목                  | 설명                                                        | 난이도  | 구현 힌트                                                    |
| --------------------- | ----------------------------------------------------------- | :-----: | ------------------------------------------------------------ |
| **REQ-P05**           | Gemini Batch 호출 (멀티 테마 일괄 분석)                     | 🔴 높음 | `main.py` L163-170의 per-keyword 호출을 단일 프롬프트로 통합 |
| **Structured Output** | Gemini JSON Mode (`response_mime_type: "application/json"`) | 🟡 중간 | `ai_summarizer.py`의 `GenerateContentConfig`에 추가          |
| **모니터링**          | Slack/Telegram 장애 알림                                    | 🟡 중간 | `circuit_breaker.py`의 Open 이벤트에 hook 추가               |
| **GitHub Actions**    | `REDDIT_ENABLED=false` 적용, 테스트 Job 분리                | 🟢 낮음 | `report_scheduler.yml`에 env 추가                            |
| **Telegram 활성화**   | `main.py` L201의 주석 해제 + 테스트                         | 🟢 낮음 | `TelegramSender()` 주석 해제                                 |

---

## 10. 프로덕션 알려진 이슈

### 10.1 Reddit 403 (errorCase/2026-03-04)

- **원인**: GitHub Actions IP가 Reddit 봇 탐지에 차단
- **해결**: `REDDIT_ENABLED=false` 환경변수로 CI에서 비활성화
- **근본 원인**: Reddit API 인증 없이 스크래핑 → 향후 PRAW(Reddit API 라이브러리) 도입 검토
- **상태**: ✅ 수정 완료 (PR #19)

### 10.2 Gemini ClientError + Circuit Breaker

- **원인**: 네트워크 불안정 → Retry 소진 → CB Open → 전체 AI 차단
- **해결**: CB 임계치 2→5, 복구 120→300초, Retry 전략 개선
- **근본 원인**: Gemini API의 일시적 불안정 + retry 시간 누적이 CB threshold에 비해 적었음
- **상태**: ✅ 수정 완료 (PR #19), 운영 모니터링 필요

---

## 11. 새 세션 시작 시 체크리스트

Codex가 새 세션을 시작할 때 **반드시** 다음 순서로 상태를 확인합니다:

```bash
# 1. Codex 가이드 및 인수인계서 확인
cat AGENTS.md

# 2. 진행 상태 확인
cat todo/todo.md

# 3. 최근 작업 로그 확인
ls -t logging/ | head -1 | xargs -I{} cat logging/{}

# 4. Git 상태 확인
git status && git branch && gh pr list

# 5. 테스트 통과 확인
python -m pytest tests/services/ tests/test_e2e_dryrun.py -q

# 6. 알려진 에러 확인
ls errorCase/
```

---

## 12. scripts/ 디렉토리 설명

`scripts/` 폴더에는 Phase 5 이전에 사용된 일회성 유틸리티 스크립트가 있습니다.
이들은 프로덕션 코드가 아니며, Notion DB 설정/검증/마이그레이션 용도입니다.
수정하거나 의존하지 마세요.

| 파일                                | 용도                      |
| ----------------------------------- | ------------------------- |
| `check_notion.py`                   | Notion DB 연결 테스트     |
| `update_notion_db.py`               | Notion DB 스키마 업데이트 |
| `update_notion_schema.py`           | Notion 속성 변경          |
| `update_notion_user.py`             | 사용자 데이터 업데이트    |
| `test_notion.py`                    | Notion API 통합 테스트    |
| `test_gemini.py`, `test_gemini2.py` | Gemini API 테스트         |
| `test_async_gemini.py`              | Gemini 비동기 호출 테스트 |
| `test_db.py`                        | DB 마이그레이션 검증      |
| `add_columns.py`                    | DB 컬럼 추가 유틸         |

---

## 13. 참고 문서

| 문서              | 경로                                                  | 설명                             |
| ----------------- | ----------------------------------------------------- | -------------------------------- |
| Codex 표준 가이드 | `AGENTS.md`                                           | ⭐ Codex가 최초로 읽어야 할 파일 |
| 인수인계서        | `.local/HANDOVER.md`                                  | 전체 프로젝트 맥락 (이 문서)     |
| 실행 가이드       | `.local/CODEX_GUIDE.md`                               | 템플릿 + 주의사항                |
| 의존성 맵         | `.local/DEPENDENCY_MAP.md`                            | 모듈 수정 영향도                 |
| 초기 분석         | `requirements/01_initial_analysis.md`                 | 프로젝트 분석 및 설계            |
| 상세 요구사항     | `requirements/02_detailed_requirements.md`            | Phase 1~4 요구사항               |
| 아키텍처 설계     | `requirements/03_architecture_and_ai_solution.md`     | 3-Tier 아키텍처                  |
| 최적화 요구사항   | `requirements/04_phase6_optimization_requirements.md` | Phase 6 상세                     |
| Task 명세         | `task/phase6_task.md`                                 | Phase 6 실행 계획                |
| 일반 Task         | `task/task.md`                                        | Phase 1~5 Task                   |
| Todo              | `todo/todo.md`                                        | 전체 체크리스트 (최신)           |
| 환경변수 템플릿   | `.env.template`                                       | 모든 환경변수 + 발급 가이드      |
| 에러 기록         | `errorCase/`                                          | 프로덕션 에러 + 조치 방법        |
| 작업 로그         | `logging/`                                            | 날짜별 작업 내역                 |
