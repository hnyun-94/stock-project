# Phase 6 최적화 프로젝트 - Task 명세서

# 이 문서는 Phase 5까지 완료된 주식 리포트 자동화 시스템의 전체 코드베이스를 분석하여

# 도출한 성능/기능/품질 최적화 과제를 역할별로 구체적 Task 단위로 정리한 것입니다.

# 각 Task의 상세 요구사항과 코드 예시는 requirements/04_phase6_optimization_requirements.md를 참조합니다.

---

## ✅ 동기화 상태 (2026-03-07)

- 본 문서의 Task 6.1~6.21은 코드베이스 기준 모두 완료되었습니다.
- 실제 구현 이력은 `todo/todo.md`, `logging/2026-03-07.md`, PR #20~#25를 기준으로 추적합니다.
- 완료 작업 기준선 요약은 `task/completed_work_report.md`를 사용합니다.

## 1. 백엔드/인프라 엔지니어 (Backend / Infrastructure Engineer)

> **목표:** "불필요한 리소스 반복 생성과 순차 처리 병목을 제거하고, Docker 환경에서도 안정적으로 동작하는 인프라를 구축한다."

### 📝 구체화 내용

- **커넥션 풀링 부재**: 현재 7개 크롤러에서 매번 새 HTTP 세션을 생성하고 파괴하는 구조. DNS 조회→TCP 핸드셰이크→TLS 협상이 크롤러 함수 호출마다 반복되어 전체 파이프라인의 20~40%가 커넥션 오버헤드로 소비됨.
- **순차 처리 병목**: 사용자별로 2개 키워드의 3소스 뉴스 크롤링이 키워드 A → 키워드 B 순서로 순차 실행됨. 비동기 환경임에도 병렬화되지 않아 사용자당 처리 시간이 2배로 늘어남.
- **Gemini 클라이언트 반복 생성**: API 호출 시마다 새 Client 객체가 인스턴스화되며, 일부 함수에서는 생성만 하고 사용하지 않는 데드 코드가 존재함.
- **Docker 환경 불완전**: docker-compose.yml에 `WEBHOOK_SECRET`만 주입되고 나머지 핵심 환경변수(`GEMINI_API_KEY`, `NOTION_TOKEN` 등)가 누락되어 컨테이너 실행 시 즉시 실패함.
- **BrowserPool 자원 누수**: Playwright 브라우저 인스턴스가 파이프라인 종료 후에도 해제되지 않아 좀비 프로세스 발생 가능성 있음.

### ✅ 진행되어야 할 Task 목록

- [x] **Task 6.1: aiohttp ClientSession 싱글톤 도입** ✅ 완료 `[REQ-P01]`
  - **신규 파일**: `src/crawlers/http_client.py` 생성
    - `get_session()`: 글로벌 싱글톤 ClientSession 반환 (닫혔으면 자동 재생성)
    - `close_session()`: 파이프라인 종료 시 세션 해제
    - 공통 `User-Agent` 헤더 + `ClientTimeout(total=15)` 기본 설정
  - **수정 파일** (7개): `naver_news.py`, `daum_news.py`, `google_news.py`, `google_trends.py`, `community.py`, `market_index.py`, `naver_datalab.py`
    - `async with aiohttp.ClientSession() as session:` → `session = await get_session()` 으로 교체
    - `async with session.get(...)` 패턴은 그대로 유지 (Response는 컨텍스트 매니저 사용)
  - **수정 파일**: `main.py`
    - `run_pipeline()` 의 `finally` 블록에서 `await close_session()` 호출
  - **브랜치명**: `feature/http-session-pooling`
  - **예상 작업량**: 약 1시간

- [x] **Task 6.2: 키워드 뉴스 크롤링 완전 병렬화** ✅ 완료 `[REQ-P02]`
  - **수정 파일**: `main.py` (110~121번 라인 영역)
  - **수정 내용**:
    - 기존 `for kw in keywords_to_search:` 순차 루프를 제거
    - 모든 키워드의 3소스(네이버/다음/구글) 크롤링 코루틴을 리스트로 모아 `asyncio.gather(*all_tasks)` 1회 호출
    - 결과를 3개씩 그룹핑하여 `kw_news_results` 리스트에 매핑
  - **주의사항**: `return_exceptions=True`를 유지하여 일부 소스 실패 시에도 나머지 결과 활용
  - **브랜치명**: `perf/parallel-keyword-crawling`
  - **예상 작업량**: 약 30분

- [x] **Task 6.3: Gemini 클라이언트 싱글톤 + 데드 코드 제거** ✅ 완료 `[REQ-P03]`
  - **수정 파일**: `src/services/ai_summarizer.py`
  - **수정 내용**:
    - `_get_client()` 함수를 모듈 레벨 변수 `_client`를 활용한 싱글톤 패턴으로 변경
    - `generate_market_summary()` (74번 라인), `generate_theme_briefing()` (128번 라인) 내부의 불필요한 `client = _get_client()` 호출 2건 삭제
  - **브랜치명**: `refactor/gemini-client-singleton`
  - **예상 작업량**: 약 15분

- [x] **Task 6.4: BrowserPool 자원 해제 + 세션 정리 보장** ✅ 완료 `[REQ-P04]`
  - **수정 파일**: `main.py`
  - **수정 내용**:
    - `run_pipeline()` 함수의 `except` 블록 뒤에 `finally` 블록 추가
    - `finally` 블록에서 `await BrowserPool.cleanup()` 및 `await close_session()` 호출
  - **브랜치명**: `fix/resource-cleanup`
  - **예상 작업량**: 약 15분

- [x] **Task 6.5: Docker Compose 환경 변수 일원화** ✅ 완료 `[REQ-Q04]`
  - **수정 파일**: `docker-compose.yml`
  - **수정 내용**:
    - 두 서비스 모두에 `env_file: - .env` 추가
    - 기존 `environment` 블록의 개별 `WEBHOOK_SECRET` 변수 제거
  - **브랜치명**: `fix/docker-env-file`
  - **예상 작업량**: 약 10분

---

## 2. 기획자 (Product Manager / Data Strategist)

> **목표:** "리포트의 정보 깊이를 끌어올리고, 사용자가 체감할 수 있는 새로운 가치 지표를 추가한다."

### 📝 구체화 내용

- **데이터 깊이 부족**: 현재 크롤러가 뉴스 제목(title)만 수집하고 있어, AI가 헤드라인만으로 시황을 분석함. `NewsArticle` 모델의 `summary` 필드가 정의되어 있으나 미활용 상태.
- **정량적 시장 심리 지표 부재**: 커뮤니티 데이터가 제목만 전달되어 "분위기가 좋다/나쁘다" 수준의 정성적 분석만 가능. 투자자가 즉각 판단할 정량적 지표(0~100점)가 없음.
- **피드백 미활용**: `user_feedback.json`에 별점이 쌓이고 있으나 프롬프트 개선에 전혀 연동되지 않음. 피드백 루프가 끊겨 있는 상태.

### ✅ 진행되어야 할 Task 목록

- [x] **Task 6.6: 뉴스 본문 리드 문단 수집** ✅ 완료 `[REQ-F01]`
  - **신규 파일**: `src/crawlers/article_parser.py`
    - `async def extract_lead_paragraph(url: str, max_sentences: int = 3) -> str` 구현
    - 기사 URL에 접속하여 `<article>` 또는 `<div class="article_body">` 등에서 첫 2~3문장 추출
    - 타임아웃 5초, 실패 시 빈 문자열 반환 (Graceful Degradation)
  - **수정 파일**: 뉴스 크롤러 3개 (`naver_news.py`, `daum_news.py`, `google_news.py`)
    - 크롤링 후 `asyncio.gather`로 각 기사의 리드 문단 병렬 추출 → `summary` 필드 채우기
  - **수정 파일**: `ai_summarizer.py`
    - 프롬프트 구성 시 `news.summary`가 있을 경우 `{i}. {news.title} - {news.summary}` 형태로 전달
  - **브랜치명**: `feature/news-body-summary`
  - **예상 작업량**: 약 3시간

- [x] **Task 6.7: 감정 지표(Sentiment Score) 도입** ✅ 완료 `[REQ-F04]`
  - **수정 파일**: `ai_summarizer.py`
    - `async def analyze_community_sentiment(posts: list) -> dict` 함수 추가
    - Gemini에 커뮤니티 제목 목록을 전달하여 0~100 감정 점수 + 한줄 해석을 JSON으로 반환받음
  - **수정 파일**: `report_formatter.py`
    - `build_markdown_report()`에 "📊 시장 심리 온도계" 섹션 추가
    - 감정 점수를 기반으로 이모지 게이지 (🟢 낙관 / 🟡 중립 / 🔴 비관) 시각화
  - **수정 파일**: `main.py`
    - 커뮤니티 데이터 수집 직후 감정 분석 호출 → 결과를 리포트에 포함
  - **브랜치명**: `feature/sentiment-score`
  - **예상 작업량**: 약 2시간

- [x] **Task 6.8: 별점 기반 자동 프롬프트 튜닝 루프** ✅ 완료 `[REQ-F06]`
  - **수정 파일**: `feedback_manager.py`
    - `def get_average_score(window_days: int = 7) -> float` 함수 추가
    - 최근 N일간 평균 별점 계산
  - **수정 파일**: `ai_summarizer.py` 또는 `prompt_manager.py`
    - 파이프라인 시작 시 평균 별점 체크 → 3.0 미만이면 temperature를 0.3으로 낮추거나 프롬프트에 "더 실질적이고 구체적인 조언 위주로" 지시 추가
  - **브랜치명**: `feature/auto-prompt-tuning`
  - **예상 작업량**: 약 2시간

---

## 3. AI/데이터 엔지니어 (AI / Data Engineer)

> **목표:** "AI에 전달되는 데이터 품질을 높이고, AI의 성과를 객관적으로 검증할 수 있는 체계를 만든다."

### 📝 구체화 내용

- **데이터 중복**: 네이버/다음/구글 3개 소스에서 동일 기사가 중복 수집됨. 중복 기사가 AI 프롬프트에 전달되면 토큰이 낭비되고 "같은 말 반복"식 요약이 생성될 위험이 있음.
- **불필요한 외부 호출**: 여러 사용자가 동일 키워드를 관심사로 등록한 경우, 같은 키워드에 대한 크롤링이 사용자 수만큼 반복됨.
- **백테스팅 객관성 부재**: 현재 `backtesting_scorer.py`가 AI에게 "네가 한 예측을 네가 채점해라"라고 요청하는 구조. 자기 참조적 평가 → 객관성 제로.

### ✅ 진행되어야 할 Task 목록

- [x] **Task 6.9: 뉴스 중복 제거 (Deduplication)** ✅ 완료 `[REQ-F02]`
  - **신규 파일**: `src/utils/deduplicator.py`
    - `def deduplicate_news(articles: list, threshold: float = 0.85) -> list` 구현
    - `difflib.SequenceMatcher`를 사용한 제목 유사도 비교
    - 유사도 threshold 이상인 기사를 필터링 (먼저 추가된 기사를 유지)
  - **수정 파일**: `main.py`
    - 3소스 뉴스 병합 직후 `deduplicate_news()` 호출
  - **테스트**: `tests/test_deduplicator.py` 작성 (유사한 제목 2건 → 1건으로 필터 검증)
  - **브랜치명**: `feature/news-deduplication`
  - **예상 작업량**: 약 1시간

- [x] **Task 6.10: 크롤링 결과 인메모리 캐싱** ✅ 완료 `[REQ-F03]`
  - **신규 파일**: `src/utils/cache.py`
    - `class TTLCache` 구현 (기본 TTL 30분)
    - `get(key)` / `set(key, value)` 메서드
    - TTL 초과 시 자동 만료
  - **수정 파일**: `main.py`
    - 키워드 크롤링 전 캐시 조회 → 히트 시 크롤링 스킵
    - 크롤링 결과를 캐시에 저장
  - **테스트**: `tests/test_cache.py` 작성 (TTL 만료 검증)
  - **브랜치명**: `feature/crawling-cache`
  - **예상 작업량**: 약 1시간

- [x] **Task 6.11: 백테스팅 채점 정량화** ✅ 완료 `[REQ-F05]`
  - **수정 파일**: `src/services/backtesting_scorer.py`
    - `async def fetch_closing_price(stock_name: str) -> float` 추가 (네이버 금융 종가 크롤링)
    - `def calculate_accuracy_score(snapshots: list, actual_prices: dict) -> dict` 추가
    - 예측 방향(상승/하락) vs 실제 결과 비교 → 백분율 적중률 산출
    - AI 분석 결과와 정량적 결과를 합쳐 복합 리포트 생성
  - **브랜치명**: `feature/quantitative-backtesting`
  - **예상 작업량**: 약 3시간

- [x] **Task 6.12: 프롬프트 A/B 테스트 시스템** ✅ 완료 `[REQ-F07]`
  - **수정 파일**: Notion 프롬프트 DB 스키마에 `Version`, `Variant` 필드 추가
  - **수정 파일**: `prompt_manager.py`
    - 동일 Title의 프롬프트가 여러 Variant로 존재할 경우 랜덤 선택
    - 선택된 Variant를 피드백과 연결하여 추적
  - **브랜치명**: `feature/prompt-ab-testing`
  - **예상 작업량**: 약 2시간

---

## 4. QA / 코드 리뷰어 (Quality Assurance / Reviewer)

> **목표:** "치명적 버그를 수정하고, 테스트 커버리지를 확장하며, 보안 취약점을 제거한다."

### 📝 구체화 내용

- **치명적 버그**: `generate_feedback_link()` 함수가 HMAC 서명 없이 URL을 생성하여 `feedback_server.py`의 서명 검증을 통과할 수 없음. 즉, **피드백 기능이 100% 작동하지 않는 상태**.
- **과도한 타임아웃**: Notion API 호출에 300초(5분) 타임아웃이 설정되어 있어, 장애 시 전체 파이프라인이 5분간 정지됨. 실제 Notion 응답은 2~5초.
- **테스트 사각지대**: 크롤러 테스트만 존재. 핵심 서비스(AI 요약, 프롬프트 관리, 백테스팅, 피드백)에 대한 테스트가 전무.
- **보안 취약점**: `WEBHOOK_SECRET` 기본값이 하드코딩되어 있어 환경변수 없이 배포 시 보안 구멍 발생.
- **프로젝트 위생**: 루트에 10개 이상의 일회성 스크립트가 방치되어 프로젝트 구조 가독성 저하.

### ✅ 진행되어야 할 Task 목록

- [x] **Task 6.13: 피드백 링크 HMAC 서명 연동 (치명적 버그 수정)** ✅ 완료 `[REQ-Q01]` ← 🚨 최우선
  - **수정 파일**: `src/services/feedback_manager.py`
    - `generate_feedback_link()` 함수에 `hmac`, `hashlib` 임포트 추가
    - `WEBHOOK_SECRET` 기반 HMAC-SHA256 서명 생성
    - URL에 `signature` 쿼리 파라미터 자동 포함
    - 별점 1~5점에 대해 각각 개별 URL 생성 (이메일에 별점 링크 5개 제공)
  - **수정 파일**: `main.py` (152~153번 라인)
    - `generate_feedback_link(name)` 호출부를 수정하여 별점별 링크 생성
  - **테스트**: `tests/services/test_feedback_manager.py` 작성
    - 생성된 URL의 서명이 서버의 `verify_signature()`를 통과하는지 검증
  - **브랜치명**: `fix/feedback-signature-bug`
  - **예상 작업량**: 약 1시간

- [x] **Task 6.14: 과도한 타임아웃 일괄 축소** ✅ 완료 `[REQ-Q02]` ← 범위 확대
  - **수정 파일**: `src/services/user_manager.py` (37번 라인)
    - `timeout=300.0` → `timeout=30.0`
  - **수정 파일**: `src/services/prompt_manager.py` (29번 라인)
    - `timeout=300.0` → `timeout=30.0`
  - **수정 파일**: `src/services/ai_summarizer.py` (51번 라인) ← 🆕
    - `safe_gemini_call()` 내부 `timeout=300.0` → `timeout=90.0`
  - **수정 파일**: `src/services/notifier/queue_worker.py` (44번 라인) ← 🆕
    - 이메일 발송 `timeout=300.0` → `timeout=60.0`
  - **브랜치명**: `fix/excessive-timeouts`
  - **예상 작업량**: 약 15분

- [x] **Task 6.15: WEBHOOK_SECRET 기본값 보안 강화** ✅ 완료 `[REQ-Q05]`
  - **수정 파일**: `src/apps/feedback_server.py` (25번 라인)
    - `WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "default_secret_key")` →
      `WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")` + 미설정 시 `RuntimeError` 발생
  - **브랜치명**: `fix/webhook-secret-guard`
  - **예상 작업량**: 약 10분

- [x] **Task 6.16: 루트 디렉토리 산재 파일 정리** ✅ 완료 `[REQ-Q06]`
  - **이동 대상 파일**: `test_async_gemini.py`, `test_db.py`, `test_notion.py`, `test_gemini.py`, `test_gemini2.py`, `add_columns.py`, `check_notion.py`, `update_notion_db.py`, `update_notion_schema.py`, `update_notion_user.py`
  - **수행 내용**:
    - `scripts/` 디렉토리 생성
    - 위 파일들을 `scripts/`로 이동
    - `.gitignore` 또는 README에 `scripts/` 설명 추가
  - **브랜치명**: `chore/cleanup-root-scripts`
  - **예상 작업량**: 약 20분

- [x] **Task 6.17: 서비스 레이어 단위 테스트 추가** ✅ 완료 `[REQ-Q03]`
  - **신규 디렉토리**: `tests/services/`
  - **신규 파일**:
    - `tests/services/test_ai_summarizer.py`: Gemini API Mock + 프롬프트 생성 검증
    - `tests/services/test_prompt_manager.py`: 캐시 적재/조회/포매팅 실패 시 None 반환 검증
    - `tests/services/test_backtesting_scorer.py`: 더미 스냅샷 생성 + 리포트 생성 검증
    - `tests/services/test_feedback_manager.py`: 별점 기록 + 범위 필터(1~5) 검증
  - **브랜치명**: `test/service-layer-tests`
  - **예상 작업량**: 약 3시간

- [x] **Task 6.18: E2E 파이프라인 드라이런 테스트** ✅ 완료 `[REQ-Q08]`
  - **신규 파일**: `tests/test_pipeline_e2e.py`
    - 크롤러/AI/발송을 모두 Mock으로 대체
    - `run_pipeline()` 전체 흐름이 정상 완료되는지 검증
    - 사용자 0명 시 조기 종료 검증
    - 특정 크롤러 실패 시에도 나머지가 동작하는지 검증
  - **브랜치명**: `test/e2e-pipeline-test`
  - **예상 작업량**: 약 2시간

---

## 📊 Task 진행 우선순위 요약

| 순위 | Task ID | 과제                       | 역할      | 예상 시간 |
| :--: | :-----: | -------------------------- | --------- | :-------: |
| 🥇 1 |  6.13   | 피드백 링크 서명 버그 수정 | QA        |    1h     |
| 🥇 1 |   6.1   | aiohttp Session 싱글톤     | 백엔드    |    1h     |
| 🥇 1 |  6.14   | 과도한 타임아웃 일괄 축소  | QA        |    15m    |
| 🥇 1 |  6.15   | WEBHOOK_SECRET 보안        | QA        |    10m    |
| 🥈 2 |   6.2   | 키워드 크롤링 병렬화       | 백엔드    |    30m    |
| 🥈 2 |   6.3   | Gemini Client 싱글톤       | 백엔드    |    15m    |
| 🥈 2 |   6.4   | BrowserPool 자원 해제      | 백엔드    |    15m    |
| 🥈 2 |   6.5   | Docker 환경변수 일원화     | 백엔드    |    10m    |
| 🥈 2 |   6.9   | 뉴스 중복 제거             | AI/데이터 |    1h     |
| 🥈 2 |  6.16   | 루트 파일 정리             | QA        |    20m    |
| 🥉 3 |  6.10   | 크롤링 캐싱                | AI/데이터 |    1h     |
| 🥉 3 |   6.6   | 뉴스 본문 수집             | 기획자    |    3h     |
| 🥉 3 |  6.17   | 서비스 테스트 추가         | QA        |    3h     |
|  4   |   6.7   | 감정 지표 도입             | 기획자    |    2h     |
|  4   |  6.11   | 백테스팅 정량화            | AI/데이터 |    3h     |
|  5   |   6.8   | 자동 프롬프트 튜닝         | 기획자    |    2h     |
|  5   |  6.12   | 프롬프트 A/B 테스트        | AI/데이터 |    2h     |
|  5   |  6.18   | E2E 파이프라인 테스트      | QA        |    2h     |
|  5   |  6.19   | Gemini Batch 호출 도입     | 백엔드    |    2h     |
|  5   |  6.20   | JSON→SQLite 마이그레이션   | 백엔드    |    3h     |
|  5   |  6.21   | 동기→비동기 Notion 전환    | 백엔드    |    30m    |

> **총 예상 작업량: 약 30시간 (Sprint 1~4에 걸쳐 점진적 진행)**

---

## 📋 Gap Analysis 보완 Task (교차 검증에서 추가 발견)

- [x] **Task 6.19: Gemini Batch 호출 도입** ✅ 완료 `[REQ-P05]`
  - **수정 파일**: `src/services/ai_summarizer.py`
    - `async def generate_multi_theme_briefing(themes: list[dict]) -> dict` 함수 추가
    - 여러 테마를 하나의 프롬프트로 통합하여 1회 API 호출로 처리
    - 결과를 JSON으로 파싱하여 테마별 분리
  - **수정 파일**: `main.py`
    - 키워드별 개별 `generate_theme_briefing()` 호출 → `generate_multi_theme_briefing()` 배치 호출로 교체
  - **브랜치명**: `perf/gemini-batch-call`
  - **예상 작업량**: 약 2시간

- [x] **Task 6.20: JSON → SQLite 마이그레이션** ✅ 완료 `[REQ-P06]`
  - **신규 파일**: `src/utils/database.py`
    - `init_db()`: `predictions`, `feedback` 테이블 생성
    - `insert_prediction()`, `insert_feedback()`, `get_recent_feedbacks()` 등 CRUD 함수
  - **수정 파일**: `src/services/ai_tracker.py`
    - JSON 파일 쓰기 → SQLite INSERT로 교체
  - **수정 파일**: `src/services/feedback_manager.py`
    - JSON 파일 읽기/쓰기 → SQLite 쿼리로 교체
  - **신규 파일**: `scripts/migrate_json_to_sqlite.py`
    - 기존 JSON 데이터를 SQLite로 이관하는 마이그레이션 스크립트
  - **브랜치명**: `refactor/json-to-sqlite`
  - **예상 작업량**: 약 3시간

- [x] **Task 6.21: 동기 Notion 호출 비동기 전환** ✅ 완료 `[REQ-Q07]`
  - **수정 파일**: `main.py`
    - `fetch_prompts_from_notion()` → `await asyncio.to_thread(fetch_prompts_from_notion)`
    - `users = fetch_active_users()` → `users = await asyncio.to_thread(fetch_active_users)`
  - **브랜치명**: `fix/async-notion-calls`
  - **예상 작업량**: 약 30분

---

_작성일: 2026-03-02_
_요구사항 상세: `requirements/04_phase6_optimization_requirements.md`_  
_체크리스트: `todo/todo.md`_
_갱신일: 2026-03-07 | Task 6.1~6.21 완료 상태 동기화 (PR #20~#25 포함)_
