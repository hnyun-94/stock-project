# AGENTS.md — Stock Report Automation Project

> Codex가 이 프로젝트를 이해하고 작업하기 위한 최상위 가이드입니다.
> 상세 문서는 `.local/` 디렉토리를 참조합니다.

## Overview

한국 주식시장의 뉴스/커뮤니티/시장지수를 자동 수집하고, Google Gemini AI로 요약 분석 후 사용자별 맞춤 리포트를 이메일/텔레그램으로 발송하는 완전 자동화 시스템입니다.

## Tech Stack

- **Runtime**: Python 3.13
- **Package Manager**: uv (`pyproject.toml` + `uv.lock`)
- **AI**: Google Gemini (`google-genai` SDK)
- **Async HTTP**: aiohttp (싱글톤 세션 풀링)
- **Database**: SQLite (WAL mode, `data/stock_project.db`)
- **Prompt Source**: Notion API (동적 프롬프트 DB) + 로컬 fallback (`src/prompts/`)
- **Test**: pytest (70 tests, <1s)
- **CI/CD**: GitHub Actions (3h cron)
- **Container**: Docker + Docker Compose

## Working Agreements

### Language

- 모든 대화, 문서, 커밋 설명은 **한국어**
- 코드, 변수명은 **영어**
- 파일 상단에 반드시 **모듈 설명 docstring** 포함

### Git Flow

- 브랜치: `feat/`, `fix/`, `refactor/`, `test/`, `docs/`, `chore/`
- PR → squash merge → delete branch
- 커밋: Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`)
- 커밋 body는 **신입 개발자가 이해할 수 있을 정도로 상세히** 기술

### PR Creation (CRITICAL — hang 방지)

```bash
# PR body를 반드시 파일로 저장 후 --body-file 사용
echo "PR 내용" > .tmp/pr_body.md
gh pr create --base master --head BRANCH --title "TITLE" --body-file .tmp/pr_body.md
gh pr merge N --squash --subject "TITLE" --delete-branch
rm -f .tmp/pr_body.md
```

⚠️ `--body` 인라인 사용 금지 (터미널 hang 원인)

### Testing

```bash
# 표준 테스트 (서비스 + E2E, aiohttp 불필요)
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 전체 테스트 (aiohttp/playwright 필요)
python -m pytest tests/ -v
```

- 새 모듈 추가 시 반드시 `tests/services/test_모듈명.py` 동시 작성
- 로거 Mock: `sys.modules['src.utils.logger'] = MagicMock()`

### Logging

- 작업 완료: `logging/YYYY-MM-DD.md` 기록
- 에러 발생: `errorCase/YYYY-MM-DD_에러명.md` 기록
- 진행상태: `todo/todo.md` 항상 최신 유지

### Temp Files

- 임시파일은 `.tmp/` 디렉토리에 생성, 사용 후 즉시 삭제
- `/tmp/` 사용 금지

## Commands

```bash
# 의존성 설치
uv sync --frozen

# 파이프라인 실행
uv run python -m src.main

# 피드백 서버 실행
uv run python -m src.apps.feedback_server

# 테스트
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 문법 검증
python -c "import ast; ast.parse(open('파일경로').read()); print('OK')"

# Docker
docker-compose up --build
```

## Project Structure

```
src/
├── main.py                 # 파이프라인 진입점 (asyncio.run)
├── models.py               # DTO: NewsArticle, MarketIndex, CommunityPost, SearchTrend, User
├── alert_daemon.py         # 실시간 알림 데몬 (실험적)
├── crawlers/               # 비동기 데이터 수집 (aiohttp)
│   ├── http_client.py      # 싱글톤 ClientSession 풀
│   ├── market_index.py     # KOSPI/KOSDAQ
│   ├── naver_news.py       # 네이버 뉴스
│   ├── daum_news.py        # 다음 뉴스
│   ├── google_news.py      # 구글 뉴스 RSS
│   ├── community.py        # DC갤러리, Reddit WSB, 네이버 종토방
│   ├── naver_datalab.py    # 네이버 데이터랩 트렌드
│   ├── google_trends.py    # 구글 트렌드
│   ├── article_parser.py   # 뉴스 본문 리드 문단 추출
│   ├── browser_pool.py     # Playwright 브라우저 풀
│   └── dynamic_community.py # Playwright 동적 크롤링
├── services/               # 비즈니스 로직
│   ├── ai_summarizer.py    # Gemini AI 요약 (CB + Retry + Semaphore)
│   ├── prompt_manager.py   # Notion 프롬프트 캐싱
│   ├── prompt_tuner.py     # 피드백 기반 자동 프롬프트 조정
│   ├── prompt_versioning.py # A/B 테스트 버전 관리
│   ├── user_manager.py     # Notion 사용자 DB 조회
│   ├── feedback_manager.py # HMAC 서명 피드백 링크
│   ├── ai_tracker.py       # AI 예측 스냅샷 DB 저장
│   ├── backtesting_scorer.py # 백테스팅 적중률 채점
│   └── notifier/           # 알림 발송 (Strategy 패턴)
│       ├── base.py, email.py, telegram.py, queue_worker.py
├── utils/                  # 인프라 유틸리티
│   ├── database.py         # SQLite 래퍼 (싱글톤, WAL, 3 tables)
│   ├── cache.py            # TTL 인메모리 캐시
│   ├── deduplicator.py     # 뉴스 제목 유사도 중복 제거 (85%)
│   ├── sentiment.py        # 한국어 감정 분석 (키워드 사전 기반)
│   ├── circuit_breaker.py  # 비동기 서킷 브레이커
│   ├── logger.py           # 글로벌 로거 (파일 + 콘솔)
│   └── report_formatter.py # 마크다운 → HTML 변환
├── prompts/                # 프롬프트 템플릿 (Notion fallback용)
│   ├── market_summary.md   # 변수: {context_indices}, {context_news}, {context_trends}
│   ├── theme_briefing.md   # 변수: {keyword}, {context_news}, {context_community}
│   └── portfolio_analysis.md # 변수: {holdings}, {market_summary}, {theme_briefings}
└── apps/
    └── feedback_server.py  # FastAPI 별점 수신 서버 (GET /api/feedback)
```

## Key Architecture

### Pipeline Flow (main.py)

```
[1] asyncio.gather → 시장지수 + 뉴스 + DC갤 + Reddit + 데이터랩 (병렬)
[2] Gemini → 시장 시황 요약
[3] asyncio.to_thread → Notion 사용자 조회 (동기→비동기 래핑)
[4] for user: 키워드 뉴스 (캐시→병렬크롤링→중복제거→리드추출) → AI 테마 브리핑
[5] 포트폴리오 AI 분석 → 리포트 포맷 → 이메일/텔레그램 발송 (큐)
* 전체 타임아웃: 300초 (main_with_timeout)
```

### Resilience Patterns

| Pattern          | Config                | Location               |
| ---------------- | --------------------- | ---------------------- |
| Circuit Breaker  | fail=5, recovery=300s | `ai_summarizer.py` L42 |
| Retry (tenacity) | 3x, exp backoff 5~30s | `ai_summarizer.py` L43 |
| Semaphore        | 2 concurrent          | `ai_summarizer.py` L20 |
| TTL Cache        | 300s default          | `cache.py`             |
| Global Timeout   | 300s                  | `main.py` L227         |

### Database Schema (SQLite, `data/stock_project.db`)

```sql
-- 사용자 별점 피드백
feedbacks (id, timestamp, user_name, score, comment)

-- AI 예측 스냅샷 + 적중률
prediction_snapshots (id, timestamp, user_name, holdings, analysis_snip, accuracy_score)

-- A/B 테스트 프롬프트 사용 이력
prompt_usage_log (id, user_name, prompt_type, version, timestamp)
```

### Feedback Server API

```
GET /api/feedback?user={name}&score={1-5}&signature={hmac_sha256}
→ HMAC-SHA256 검증 (WEBHOOK_SECRET)
→ SQLite에 별점 저장
→ HTML 응답 렌더링
```

### Prompt System

1. **Notion DB** (우선): `fetch_prompts_from_notion()` → 메모리 캐시
2. **로컬 fallback**: `src/prompts/*.md` → `{변수}` 포맷 치환
3. **자동 튜닝**: 평균 별점 기반 temperature/스타일 조정 (`prompt_tuner.py`)

## Environment Variables

`.env.template`에 전체 목록과 발급 방법이 기술되어 있습니다.

| Variable                 | Purpose                   | Required |
| ------------------------ | ------------------------- | :------: |
| `GEMINI_API_KEY`         | Google Gemini AI          |    ✅    |
| `NOTION_TOKEN`           | Notion Integration        |    ✅    |
| `NOTION_DATABASE_ID`     | 사용자 관리 DB            |    ✅    |
| `NOTION_PROMPT_DB_ID`    | 프롬프트 DB               |    ✅    |
| `SENDER_EMAIL`           | Gmail 발신 계정           |    ✅    |
| `SENDER_APP_PASSWORD`    | Gmail 앱 비밀번호         |    ✅    |
| `WEBHOOK_SECRET`         | 피드백 HMAC 시크릿        |    ✅    |
| `FEEDBACK_BASE_URL`      | 피드백 서버 URL           |    ✅    |
| `TELEGRAM_BOT_TOKEN`     | Telegram Bot              |   선택   |
| `ADMIN_TELEGRAM_CHAT_ID` | 관리자 알림               |   선택   |
| `NAVER_CLIENT_ID`        | 데이터랩 API              |   선택   |
| `NAVER_CLIENT_SECRET`    | 데이터랩 API              |   선택   |
| `REDDIT_ENABLED`         | Reddit 토글 (CI: `false`) |   선택   |

## Known Issues

1. **Reddit 403**: GitHub Actions IP가 차단됨 → `REDDIT_ENABLED=false`
2. **Gemini ClientError**: 네트워크 불안정 시 CB Open → 임계치 5회로 완화됨
3. **GitHub Actions에 REDDIT_ENABLED 미적용**: 워크플로우에 환경변수 추가 필요

## Session Startup Checklist

```bash
cat todo/todo.md                    # 진행 상태
ls -t logging/ | head -1 | xargs -I{} cat logging/{}  # 최근 로그
git status && git branch            # Git 상태
gh pr list                          # 열린 PR
python -m pytest tests/services/ tests/test_e2e_dryrun.py -q  # 테스트
ls errorCase/                       # 에러 기록
```

## Detailed Docs

| Document    | Path                       | Purpose                 |
| ----------- | -------------------------- | ----------------------- |
| 인수인계서  | `.local/HANDOVER.md`       | 전체 프로젝트 맥락/이력 |
| 실행 가이드 | `.local/CODEX_GUIDE.md`    | 템플릿/주의사항         |
| 의존성 맵   | `.local/DEPENDENCY_MAP.md` | 수정 영향도             |
| 요구사항    | `requirements/*.md`        | Phase 1~6               |
| Task 명세   | `task/*.md`                | 실행 계획               |
| Todo        | `todo/todo.md`             | 체크리스트 (최신)       |
| 환경변수    | `.env.template`            | 전체 키 + 발급 가이드   |
| 에러 기록   | `errorCase/`               | 프로덕션 에러 + 조치    |
