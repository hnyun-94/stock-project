# 📋 Stock-Project Codex 인수인계서 (Handover Document)

> 이 문서는 Codex(또는 후임 AI Agent)가 이 프로젝트를 이해하고 즉시 작업을 시작할 수 있도록
> 프로젝트의 전체 구조, 아키텍처, 개발 규칙, 운영 방식을 상세히 기술한 인수인계 문서입니다.
> 최종 갱신: 2026-03-07

---

## 1. 프로젝트 개요

### 1.1 목적

매일 한국 주식시장의 뉴스, 커뮤니티 반응, 시장 지수, 검색 트렌드를 자동으로 수집하고,
Google Gemini AI로 요약 분석한 후 사용자별 맞춤형 리포트를 이메일/텔레그램으로 발송하는
**완전 자동화 주식 리포트 시스템**입니다.

### 1.2 기술 스택

| 구분          | 기술                                                       |
| ------------- | ---------------------------------------------------------- |
| 런타임        | Python 3.13                                                |
| 패키지 관리   | uv (pyproject.toml + uv.lock)                              |
| AI            | Google Gemini API (google-genai SDK)                       |
| 크롤링        | aiohttp (비동기), BeautifulSoup4, Playwright (동적 페이지) |
| 데이터저장    | SQLite (WAL, `data/stock_project.db`)                      |
| 프롬프트 관리 | Notion API (동적 프롬프트 DB)                              |
| 사용자 관리   | Notion API (수신자 DB)                                     |
| 알림 채널     | Email (SMTP/Gmail), Telegram Bot                           |
| 피드백        | FastAPI 서버 (`src/apps/feedback_server.py`)               |
| 컨테이너      | Docker + Docker Compose                                    |
| CI/CD         | GitHub Actions (3시간 주기 cron)                           |
| 테스트        | pytest (70개 테스트, 0.3초)                                |

### 1.3 동작 흐름 (Pipeline)

```
[1] 공통 데이터 수집 (asyncio.gather 병렬)
    ├── 시장 지수 (KOSPI, KOSDAQ)
    ├── 뉴스 헤드라인 (네이버)
    ├── 커뮤니티 (DC갤, Reddit WSB)
    └── 검색 트렌드 (네이버 데이터랩)
        ↓
[2] AI 시장 시황 요약 (Gemini)
        ↓
[3] Notion에서 수신 대상자 조회
        ↓
[4] 사용자별 맞춤 데이터 생성 (루프)
    ├── 키워드 뉴스 수집 (TTL 캐시 적용)
    ├── 뉴스 중복 제거 (85% 유사도)
    ├── 뉴스 리드 문단 추출
    ├── 감정 지표 분석
    ├── 테마 AI 브리핑 (큐 기반)
    └── 포트폴리오 AI 분석
        ↓
[5] 채널별 알림 발송 (이메일/텔레그램)
```

---

## 2. 디렉토리 구조

```
stock-project/
├── .github/workflows/         # GitHub Actions CI/CD
│   └── report_scheduler.yml   # 3시간 주기 cron 실행
├── .agents/workflows/         # AI Agent용 워크플로우 가이드
├── .local/                    # Codex 인수인계 문서 (이 폴더)
├── .tmp/                      # 임시파일 (gitignore됨)
├── data/                      # SQLite DB 파일 위치
├── errorCase/                 # 프로덕션 에러 기록
├── logging/                   # 날짜별 작업 로그
├── requirements/              # 요구사항 문서 (Phase 1~6)
├── scripts/                   # 일회성 유틸리티 스크립트
├── task/                      # Task 명세서
├── tests/                     # 테스트 코드
│   ├── services/              # 서비스 단위 테스트 (8파일, 63개)
│   ├── test_e2e_dryrun.py     # E2E 통합 테스트 (7개)
│   ├── crawlers/              # 크롤러 테스트 (aiohttp 필요)
│   ├── mocked/                # VCR 기반 Mock 테스트
│   └── load/                  # 부하 테스트 (locust)
├── todo/                      # 작업 체크리스트
│   └── todo.md                # ← 항상 최신 상태 유지
├── src/
│   ├── models.py              # 공통 DTO (5개 dataclass)
│   ├── main.py                # 파이프라인 진입점
│   ├── alert_daemon.py        # 실시간 알림 데몬
│   ├── crawlers/              # 데이터 수집 모듈
│   │   ├── http_client.py     # aiohttp 싱글톤 세션 풀
│   │   ├── browser_pool.py    # Playwright 브라우저 풀
│   │   ├── market_index.py    # KOSPI/KOSDAQ 시장 지수
│   │   ├── naver_news.py      # 네이버 뉴스
│   │   ├── daum_news.py       # 다음 뉴스
│   │   ├── google_news.py     # 구글 뉴스 RSS
│   │   ├── community.py       # DC갤, Reddit WSB, 네이버 종토방
│   │   ├── google_trends.py   # 구글 트렌드
│   │   ├── naver_datalab.py   # 네이버 데이터랩
│   │   ├── article_parser.py  # 뉴스 본문 리드 문단 추출
│   │   └── dynamic_community.py # Playwright 기반 동적 크롤링
│   ├── services/              # 비즈니스 로직
│   │   ├── ai_summarizer.py   # Gemini AI 요약 (Circuit Breaker + Retry)
│   │   ├── prompt_manager.py  # Notion 동적 프롬프트 관리
│   │   ├── prompt_tuner.py    # 피드백 기반 자동 프롬프트 조정
│   │   ├── prompt_versioning.py # A/B 테스트 버전 관리
│   │   ├── user_manager.py    # Notion 사용자 조회
│   │   ├── feedback_manager.py # 별점 피드백 처리 (HMAC 서명)
│   │   ├── ai_tracker.py      # AI 예측 스냅샷 저장
│   │   ├── backtesting_scorer.py # 백테스팅 채점 정량화
│   │   └── notifier/          # 알림 발송 (Strategy 패턴)
│   │       ├── base.py        # 추상 SenderBase
│   │       ├── email.py       # SMTP 이메일 전송
│   │       ├── telegram.py    # Telegram Bot 전송
│   │       └── queue_worker.py # 비동기 메시지 큐
│   ├── utils/                 # 유틸리티
│   │   ├── logger.py          # 글로벌 로거 (파일+콘솔)
│   │   ├── database.py        # SQLite 래퍼 (싱글톤, WAL, ACID)
│   │   ├── cache.py           # TTL 인메모리 캐시
│   │   ├── deduplicator.py    # 뉴스 제목 유사도 중복 제거
│   │   ├── sentiment.py       # 한국어 감정 분석 (키워드 사전)
│   │   ├── circuit_breaker.py # 비동기 서킷 브레이커
│   │   ├── report_formatter.py # 마크다운→HTML 포맷터
│   │   └── auto_patcher.py    # AI 자동 버그 패치 (실험적)
│   ├── prompts/               # 프롬프트 템플릿 (Notion fallback)
│   │   ├── market_summary.md
│   │   ├── theme_briefing.md
│   │   └── portfolio_analysis.md
│   └── apps/
│       └── feedback_server.py # FastAPI 별점 피드백 수신 서버
├── pyproject.toml             # 의존성 정의
├── uv.lock                    # 락 파일
├── Dockerfile                 # 컨테이너 이미지 빌드
├── docker-compose.yml         # 멀티 서비스 구성
└── .env.template              # 환경변수 템플릿 (모든 키 설명 포함)
```

---

## 3. 핵심 아키텍처 패턴

### 3.1 데이터 모델 (DTO)

`src/models.py`에 5개의 `@dataclass` DTO가 정의되어 있습니다:

- `NewsArticle` — 뉴스 기사 (title, link, summary, date, publisher)
- `MarketIndex` — 시장 지수 (name, value, change, investor_summary)
- `CommunityPost` — 커뮤니티 게시글 (title, link, views, likes)
- `SearchTrend` — 검색 트렌드 (keyword, traffic, news_title, news_link)
- `User` — 수신 대상자 (name, email, keywords, telegram_id, channels, holdings)

### 3.2 비동기 처리

- 모든 크롤러는 `async/await` 기반
- `aiohttp.ClientSession` 싱글톤 (`http_client.py`)으로 커넥션 풀링
- `asyncio.gather()`로 병렬 크롤링
- Notion 동기 API는 `asyncio.to_thread()`로 래핑

### 3.3 장애 내성

| 패턴              | 파일                 | 설명                                         |
| ----------------- | -------------------- | -------------------------------------------- |
| Circuit Breaker   | `circuit_breaker.py` | 연속 5회 실패 시 AI 차단, 300초 후 Half-Open |
| Retry (Tenacity)  | `ai_summarizer.py`   | 지수 백오프 재시도 (3회, 5~30초)             |
| TTL Cache         | `cache.py`           | 같은 키워드 크롤링 결과 재사용 (기본 300초)  |
| Graceful Fallback | `community.py`       | Reddit 403 시 빈 리스트 반환                 |
| Timeout           | 전체                 | 모든 네트워크 호출에 타임아웃 설정           |

### 3.4 데이터 저장 (SQLite)

`src/utils/database.py` — 싱글톤 패턴, WAL 모드
3개 테이블:

1. `feedbacks` — 사용자 별점 피드백
2. `prediction_snapshots` — AI 예측 스냅샷 + accuracy_score
3. `prompt_usage_log` — A/B 테스트 프롬프트 사용 이력

### 3.5 알림 시스템

Strategy 패턴 (`notifier/base.py` → `email.py`, `telegram.py`)
비동기 큐 워커(`queue_worker.py`)로 발송 작업 비동기 처리

---

## 4. 환경 변수 (필수)

`.env.template` 파일에 전체 목록과 발급 방법이 기술되어 있습니다.

| 변수                     | 용도                                | 필수 |
| ------------------------ | ----------------------------------- | :--: |
| `GEMINI_API_KEY`         | Google Gemini AI API                |  ✅  |
| `NOTION_TOKEN`           | Notion Integration Token            |  ✅  |
| `NOTION_DATABASE_ID`     | 사용자 관리 DB                      |  ✅  |
| `NOTION_PROMPT_DB_ID`    | 프롬프트 관리 DB                    |  ✅  |
| `SENDER_EMAIL`           | Gmail 발신 계정                     |  ✅  |
| `SENDER_APP_PASSWORD`    | Gmail 앱 비밀번호                   |  ✅  |
| `WEBHOOK_SECRET`         | 피드백 HMAC 시크릿                  |  ✅  |
| `FEEDBACK_BASE_URL`      | 피드백 서버 URL                     |  ✅  |
| `TELEGRAM_BOT_TOKEN`     | Telegram Bot                        | 선택 |
| `ADMIN_TELEGRAM_CHAT_ID` | 관리자 알림                         | 선택 |
| `NAVER_CLIENT_ID`        | 네이버 데이터랩                     | 선택 |
| `NAVER_CLIENT_SECRET`    | 네이버 데이터랩                     | 선택 |
| `REDDIT_ENABLED`         | Reddit 크롤링 토글 (CI에서 `false`) | 선택 |

---

## 5. 개발 규칙 (MUST FOLLOW)

### 5.1 언어 규칙

- **모든 답변, 과정, 문서는 한국어**로 작성
- **코드, 변수명, 커밋 메시지 본문은 영어** (커밋 제목은 한/영 혼용 가능)
- 파일 상단에 항상 모듈 설명 docstring 포함

### 5.2 Git 규칙

- 모든 작업은 **feature 브랜치** → **PR** → **squash merge** → **delete branch** 흐름
- 브랜치 네이밍: `feat/기능명`, `fix/버그명`, `refactor/리팩토링명`, `test/테스트명`
- 커밋 메시지: Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`)
- 커밋 본문에 **변경 내용을 신입 개발자가 이해할 수 있는 수준으로 상세히 기술**
- PR body에 3관점 리뷰 포함 (개발자/검토자/운영자)

### 5.3 PR 워크플로우

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

# 4. Push + PR 생성 (body-file 사용 — hang 방지)
git push -u origin feat/기능명
# PR body를 .tmp/pr_body.md에 저장 후
gh pr create --base master --head feat/기능명 --title "..." --body-file .tmp/pr_body.md

# 5. Merge + 브랜치 삭제
gh pr merge N --squash --subject "..." --delete-branch

# 6. 임시파일 정리
rm -f .tmp/pr_body.md
```

### 5.4 테스트 규칙

- 새 모듈 추가 시 반드시 단위 테스트 함께 작성
- 테스트 파일 위치: `tests/services/test_모듈명.py`
- `sys.modules['src.utils.logger'] = MagicMock()`으로 로거 Mock
- 서비스 테스트 실행: `python -m pytest tests/services/ tests/test_e2e_dryrun.py -v`
- 크롤러 테스트는 `aiohttp` 설치 필요 (로컬 환경에서만)

### 5.5 로깅 규칙

- 작업 완료 시 `logging/YYYY-MM-DD.md`에 작업시간 + 내용 기록
- 에러 발생 시 `errorCase/YYYY-MM-DD_에러명.md`에 상황 + 조치 기록
- `todo/todo.md`는 항상 최신 상태 유지 (완료 시 `[x]` + PR 번호 표기)

### 5.6 임시파일 규칙

- 임시파일은 **프로젝트 내 `.tmp/` 디렉토리**에 생성
- 사용 후 즉시 삭제
- `/tmp/` 사용 금지
- `.tmp/`는 `.gitignore`에 등록됨

### 5.7 터미널 안전 규칙

- `gh pr create`는 반드시 `--body-file` 사용 (인라인 body → hang 위험)
- 대화형 명령 (`vi`, `nano`, `less`, `more`) 사용 금지
- 장시간 명령은 타임아웃 설정 필수

---

## 6. 테스트 현황

### 6.1 테스트 파일 목록 (70개)

| 파일                        | 테스트 수 | 내용                                         |
| --------------------------- | :-------: | -------------------------------------------- |
| `test_cache.py`             |     8     | TTLCache 동작, TTL 만료, 최대 크기, 덮어쓰기 |
| `test_database.py`          |     9     | SQLite CRUD, 스코어링, 적중률 통계           |
| `test_deduplicator.py`      |     9     | 제목 정규화, 유사도, 중복 제거               |
| `test_feedback_manager.py`  |     7     | HMAC 서명, 피드백 링크 생성                  |
| `test_notifier.py`          |     4     | Email/Telegram 발송, env 미설정              |
| `test_sentiment.py`         |    11     | 감정 점수, 레이블, 게이지 포맷               |
| `test_prompt_tuner.py`      |     5     | 자동 튜닝, 스타일 힌트                       |
| `test_prompt_versioning.py` |     6     | A/B 배정, 이력 기록, 통계                    |
| `test_e2e_dryrun.py`        |     7     | 데이터 흐름 통합, 캐시+중복제거              |
| **합계**                    |  **70**   | **0.3초**                                    |

### 6.2 실행 명령

```bash
# 서비스 레이어 + E2E (표준)
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 전체 (aiohttp 필요)
python -m pytest tests/ -v
```

---

## 7. CI/CD (GitHub Actions)

### 7.1 워크플로우

- 파일: `.github/workflows/report_scheduler.yml`
- 트리거: `push to master`, cron `0 */3 * * *` (매 3시간), `workflow_dispatch`
- 타임아웃: 5분
- 환경: Ubuntu, Python 3.13, uv

### 7.2 필요한 GitHub Secrets

```
GEMINI_API_KEY, NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_PROMPT_DB_ID,
SENDER_EMAIL, SENDER_APP_PASSWORD, WEBHOOK_SECRET,
NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
```

### 7.3 알려진 이슈

- Reddit API가 GitHub Actions IP에서 **403 Forbidden** 반환 → `REDDIT_ENABLED=false` 권장
- 워크플로우에 `REDDIT_ENABLED: false` 환경변수 추가하면 해결

---

## 8. 완료된 작업 이력 (Phase 1~6)

### Phase 1~5 (2026-02 초~중순)

- 기본 크롤러, AI 요약, 이메일 발송, Notion 통합, 피드백 시스템, Docker 배포

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

| 항목                    | 설명                                         | 난이도  |
| ----------------------- | -------------------------------------------- | :-----: |
| **REQ-P05**             | Gemini Batch 호출 (멀티 테마 일괄 분석)      | 🔴 높음 |
| **Structured Output**   | Gemini JSON Mode 도입                        | 🟡 중간 |
| **모니터링**            | Slack/Telegram 장애 알림                     | 🟡 중간 |
| **GitHub Actions 개선** | `REDDIT_ENABLED=false` 적용, 테스트 Job 분리 | 🟢 낮음 |

---

## 10. 프로덕션 알려진 이슈

### 10.1 Reddit 403 (errorCase/2026-03-04)

- **원인**: GitHub Actions IP가 Reddit 봇 탐지에 차단
- **해결**: `REDDIT_ENABLED=false` 환경변수로 CI에서 비활성화
- **상태**: 수정 완료 (PR #19)

### 10.2 Gemini ClientError + Circuit Breaker

- **원인**: 네트워크 불안정 → Retry 소진 → CB Open → 전체 AI 차단
- **해결**: CB 임계치 2→5, 복구 120→300초, Retry 전략 개선
- **상태**: 수정 완료 (PR #19), 운영 모니터링 필요

---

## 11. 새 세션 시작 시 체크리스트

Codex가 새 세션을 시작할 때 **반드시** 다음 순서로 상태를 확인합니다:

```bash
# 1. 진행 상태 확인
cat todo/todo.md

# 2. 최근 작업 로그 확인
ls -lt logging/ | head -3
cat logging/$(ls -t logging/ | head -1)

# 3. Git 상태 확인
git status
git branch
gh pr list

# 4. 테스트 통과 확인
python -m pytest tests/services/ tests/test_e2e_dryrun.py -q

# 5. 알려진 에러 확인
ls errorCase/
```

---

## 12. 참고 문서

| 문서            | 경로                                                  | 설명                        |
| --------------- | ----------------------------------------------------- | --------------------------- |
| 초기 분석       | `requirements/01_initial_analysis.md`                 | 프로젝트 분석 및 설계       |
| 상세 요구사항   | `requirements/02_detailed_requirements.md`            | Phase 1~4 요구사항          |
| 아키텍처 설계   | `requirements/03_architecture_and_ai_solution.md`     | 3-Tier 아키텍처             |
| 최적화 요구사항 | `requirements/04_phase6_optimization_requirements.md` | Phase 6 상세                |
| Task 명세       | `task/phase6_task.md`                                 | Phase 6 실행 계획           |
| 일반 Task       | `task/task.md`                                        | Phase 1~5 Task              |
| Todo            | `todo/todo.md`                                        | 전체 체크리스트 (최신)      |
| 환경변수 템플릿 | `.env.template`                                       | 모든 환경변수 + 발급 가이드 |
| 에러 기록       | `errorCase/`                                          | 프로덕션 에러 + 조치 방법   |
| 작업 로그       | `logging/`                                            | 날짜별 작업 내역            |
