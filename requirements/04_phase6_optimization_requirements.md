# Phase 6 성능 및 기능 최적화 요구사항 정의서

# 이 문서는 Phase 5까지 완료된 프로젝트의 전체 코드베이스를 정밀 분석하여

# 성능/기능/품질 관점에서 도출된 최적화 요구사항과 구체적 구현 방법을 정리합니다.

---

## 1. 배경 및 목적

Phase 5까지의 개발로 주식 리포트 자동화 시스템의 핵심 기능(크롤링, AI 요약, 개인화, 알림, 피드백, 백테스팅, Docker, 보안)은 모두 구현되었습니다.
그러나 **실제 운영 관점**에서 코드를 재점검한 결과, 다음 세 가지 축에서 개선이 필요합니다:

1. **성능(Performance)**: 불필요한 리소스 반복 생성, 순차 처리 병목, API 과다 호출
2. **기능(Feature)**: 데이터 품질 부족(뉴스 제목만 수집), 피드백 미활용, 정량적 검증 부재
3. **품질(Quality)**: 서비스 레이어 테스트 부재, 보안 버그, 과도한 타임아웃 설정

---

## 2. 성능 최적화 요구사항 (Performance)

### REQ-P01: aiohttp ClientSession 재사용 (커넥션 풀링)

- **현재 문제**:
  모든 크롤러 함수(`naver_news.py`, `daum_news.py`, `google_news.py`, `google_trends.py`, `community.py`, `market_index.py`, `naver_datalab.py`)가
  `async with aiohttp.ClientSession() as session:` 패턴으로 **매 호출마다 새 TCP 세션을 생성/해제**합니다.
  이로 인해 DNS 조회 → TCP 핸드셰이크 → TLS 협상이 매번 반복되며 크롤링 전체에 누적 오버헤드가 발생합니다.

- **요구사항**:
  글로벌 또는 모듈 단위 `ClientSession` 싱글톤을 도입하여 HTTP 커넥션 풀을 재사용해야 합니다.

- **구현 방법**:
  1. `src/crawlers/http_client.py` 신규 모듈을 생성합니다.
  2. 모듈 내에 `get_session()` / `close_session()` 비동기 함수를 구현합니다.
  3. `get_session()`은 싱글톤으로 동작하며, 세션이 없거나 닫혔을 때만 새로 생성합니다.
  4. 공통 `User-Agent` 헤더와 `ClientTimeout(total=15)` 을 기본값으로 설정합니다.
  5. 기존 7개 크롤러 파일에서 `aiohttp.ClientSession()` 생성 부분을 `get_session()` 호출로 교체합니다.
  6. `main.py`의 `run_pipeline()` 종료 시점(`finally` 블록)에서 `close_session()`을 호출합니다.

  ```python
  # src/crawlers/http_client.py
  import aiohttp

  _session: aiohttp.ClientSession | None = None

  async def get_session() -> aiohttp.ClientSession:
      global _session
      if _session is None or _session.closed:
          _session = aiohttp.ClientSession(
              timeout=aiohttp.ClientTimeout(total=15),
              headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
          )
      return _session

  async def close_session():
      global _session
      if _session and not _session.closed:
          await _session.close()
          _session = None
  ```

- **기대 효과**: 크롤링 전체 소요 시간 20~40% 단축
- **영향 범위**: 크롤러 7개 파일(`naver_news.py`, `daum_news.py`, `google_news.py`, `google_trends.py`, `community.py`, `market_index.py`, `naver_datalab.py`) + `main.py`

---

### REQ-P02: 사용자별 키워드 뉴스 크롤링 완전 병렬화

- **현재 문제**:
  `main.py:110~121`에서 각 사용자의 키워드를 **순차적 `for` 루프**로 처리합니다.
  키워드 A의 3개 소스(네이버/다음/구글) 크롤링이 완료되어야 키워드 B를 시작합니다.

- **요구사항**:
  모든 키워드의 크롤링 작업을 하나의 `asyncio.gather`로 묶어 완전 병렬화해야 합니다.

- **구현 방법**:
  1. 키워드별 for 루프 대신, 리스트 컴프리헨션으로 모든 키워드의 3소스 크롤링 코루틴을 생성합니다.
  2. 하나의 `asyncio.gather(*all_tasks, return_exceptions=True)`로 한 번에 실행합니다.
  3. 결과를 키워드별로 그룹핑하여 기존 로직과 동일하게 `kw_news_results`에 매핑합니다.

  ```python
  # 개선 후 (main.py 내부)
  all_kw_tasks = []
  for kw in keywords_to_search:
      all_kw_tasks.extend([
          search_news_by_keyword(kw, 3),
          search_daum_news_by_keyword(kw, 3),
          search_google_news_by_keyword(kw, 3),
      ])
  all_results = await asyncio.gather(*all_kw_tasks, return_exceptions=True)

  # 3개씩 그룹핑
  kw_news_results = []
  for i in range(0, len(all_results), 3):
      flat_news = []
      for res in all_results[i:i+3]:
          if isinstance(res, list):
              flat_news.extend(res)
      kw_news_results.append(flat_news[:7])
  ```

- **기대 효과**: 1사용자 2키워드 기준 약 50% 시간 단축
- **영향 범위**: `main.py`

---

### REQ-P03: Gemini 클라이언트 싱글톤 패턴 적용

- **현재 문제**:
  `ai_summarizer.py`의 `_get_client()` 함수가 호출될 때마다 새로운 `genai.Client` 객체를 생성합니다.
  또한 `generate_market_summary()`, `generate_theme_briefing()` 함수 내부에서도 불필요하게 `client = _get_client()`를 호출하고 있지만 실제로 사용하지 않습니다 (실제 API 호출은 `safe_gemini_call`에서 수행).

- **요구사항**:
  `genai.Client`를 모듈 레벨 싱글톤으로 관리하고, 사용하지 않는 `client = _get_client()` 호출을 제거해야 합니다.

- **구현 방법**:
  1. `_get_client()`를 싱글톤 패턴으로 변경합니다 (모듈 변수에 캐싱).
  2. `generate_market_summary()`, `generate_theme_briefing()` 내부의 불필요한 `client = _get_client()` 호출을 삭제합니다.

  ```python
  _client = None

  def _get_client():
      global _client
      if _client is None:
          api_key = os.getenv("GEMINI_API_KEY")
          if not api_key:
              raise ValueError("GEMINI_API_KEY 환경 변수가 설정되어 있지 않습니다.")
          _client = genai.Client(api_key=api_key)
      return _client
  ```

- **기대 효과**: 미세 성능 개선 + 메모리 최적화 + 데드 코드 제거
- **영향 범위**: `ai_summarizer.py`

---

### REQ-P04: BrowserPool 자원 해제 보장

- **현재 문제**:
  `main.py`에서 `BrowserPool.cleanup()`이 호출되지 않습니다.
  동적 크롤링(`dynamic_community.py`)을 사용하지 않더라도, 향후 사용 시 Chromium 프로세스가 좀비화될 위험이 있습니다.

- **요구사항**:
  파이프라인 종료 시 `BrowserPool.cleanup()`을 `finally` 블록에서 반드시 호출해야 합니다.

- **구현 방법**:
  `main.py`의 `run_pipeline()` 함수 내 `try-except` 블록을 `try-except-finally`로 변경하고,
  `finally`에서 `BrowserPool.cleanup()`과 `close_session()`을 호출합니다.

- **기대 효과**: 메모리 누수 방지, Docker 컨테이너 안정성 확보
- **영향 범위**: `main.py`

---

## 3. 기능 최적화 요구사항 (Feature)

### REQ-F01: 뉴스 본문 리드 문단 수집

- **현재 문제**:
  모든 크롤러가 뉴스 `title`만 수집합니다. AI가 제목만으로 시황을 분석하므로 깊이가 부족합니다.
  `NewsArticle` 모델에 `summary` 필드가 정의되어 있지만 활용되지 않습니다.

- **요구사항**:
  각 뉴스 링크에서 본문 첫 2~3문장(리드 문단)을 추출하여 `NewsArticle.summary` 필드에 저장하고,
  AI 프롬프트에 컨텍스트로 전달해야 합니다.

- **구현 방법**:
  1. `src/crawlers/article_parser.py` 신규 모듈을 생성합니다.
  2. `async def extract_lead_paragraph(url: str, max_sentences: int = 3) -> str` 함수를 구현합니다.
  3. 뉴스 크롤링 후 `asyncio.gather`로 각 기사의 리드 문단을 병렬 추출합니다.
  4. `ai_summarizer.py`의 프롬프트 구성 시 `summary` 필드도 포함합니다.

- **기대 효과**: AI 요약의 정확도/깊이 대폭 향상
- **영향 범위**: 신규 모듈 + 크롤러 3개 + `ai_summarizer.py`

---

### REQ-F02: 뉴스 중복 제거 (Deduplication)

- **현재 문제**:
  네이버/다음/구글 3개 소스에서 동일 기사가 중복 수집될 가능성이 높습니다.
  중복 기사가 AI에 전달되면 토큰이 낭비되고 요약 품질이 저하됩니다.

- **요구사항**:
  같은 키워드에 대해 3개 소스에서 수집한 뉴스를 병합할 때,
  제목 유사도가 85% 이상인 기사는 필터링해야 합니다.

- **구현 방법**:
  1. `src/utils/deduplicator.py` 신규 모듈을 생성합니다.
  2. `difflib.SequenceMatcher`를 사용한 빠른 문자열 유사도 비교 함수를 구현합니다.
  3. `main.py`에서 3소스 뉴스 병합 직후, 중복 제거 함수를 호출합니다.

  ```python
  from difflib import SequenceMatcher

  def deduplicate_news(articles: list[NewsArticle], threshold: float = 0.85) -> list[NewsArticle]:
      unique = []
      for article in articles:
          is_dup = any(
              SequenceMatcher(None, article.title, u.title).ratio() >= threshold
              for u in unique
          )
          if not is_dup:
              unique.append(article)
      return unique
  ```

- **기대 효과**: AI 컨텍스트 품질 향상, 토큰 절약 20~30%
- **영향 범위**: 신규 모듈 + `main.py`

---

### REQ-F03: 크롤링 결과 인메모리 캐싱

- **현재 문제**:
  사용자 A, B가 동일 키워드("반도체")를 관심사로 등록한 경우,
  같은 키워드에 대해 크롤링이 중복 실행됩니다.

- **요구사항**:
  TTL(Time-To-Live) 기반 인메모리 캐시를 도입하여,
  동일 키워드/시간대의 크롤링 결과를 재사용해야 합니다.

- **구현 방법**:
  1. `src/utils/cache.py` 신규 모듈을 생성합니다.
  2. TTL 기반 딕셔너리 캐시 클래스 `TTLCache`를 구현합니다.
  3. `main.py`에서 키워드 크롤링 전 캐시를 조회하고, 미스 시에만 크롤링을 수행합니다.

  ```python
  import time

  class TTLCache:
      def __init__(self, ttl_seconds: int = 1800):  # 기본 30분
          self._store = {}
          self._ttl = ttl_seconds

      def get(self, key: str):
          if key in self._store:
              value, timestamp = self._store[key]
              if time.time() - timestamp < self._ttl:
                  return value
              del self._store[key]
          return None

      def set(self, key: str, value):
          self._store[key] = (value, time.time())
  ```

- **기대 효과**: 외부 API 호출 50%+ 절감, 차단/Rate Limit 위험 감소
- **영향 범위**: 신규 모듈 + `main.py`

---

### REQ-F04: 감정 지표(Sentiment Score) 도입

- **현재 문제**:
  커뮤니티 데이터(종토방, 식갤, WSB)가 제목만 전달되어 정량적 분석이 불가합니다.

- **요구사항**:
  커뮤니티 게시글 제목에서 긍정/부정 감정을 0~100으로 수치화하여
  리포트에 "시장 심리 온도계" 섹션을 추가해야 합니다.

- **구현 방법**:
  1. Gemini API에 감정 분석 전용 프롬프트를 추가합니다.
  2. 커뮤니티 데이터 수집 후 일괄 감정 분석 수행 → 평균 점수 산출합니다.
  3. `report_formatter.py`에 온도계 시각화 섹션을 추가합니다.

- **기대 효과**: 투자자 입장에서 시장 온도를 직관적으로 파악 가능
- **영향 범위**: `ai_summarizer.py` + `report_formatter.py` + 프롬프트

---

### REQ-F05: 백테스팅 채점 정량화

- **현재 문제**:
  `backtesting_scorer.py`가 AI에게 "스스로 채점하라"는 방식이라
  객관적 검증이 없습니다.

- **요구사항**:
  과거 스냅샷의 예측 종목/방향과 실제 종가 데이터를 비교하는
  정량적 스코어링 로직을 구현해야 합니다.

- **구현 방법**:
  1. 네이버 금융에서 과거 종가 데이터를 비동기 크롤링하는 함수를 추가합니다.
  2. 스냅샷의 예측 방향(상승/하락)과 실제 결과를 비교하여 적중률을 계산합니다.
  3. 정량적 결과를 AI 분석과 함께 복합 리포트로 출력합니다.

- **기대 효과**: 객관적이고 신뢰할 수 있는 AI 성능 지표 확보
- **영향 범위**: `backtesting_scorer.py` + 신규 크롤링 함수

---

## 4. 품질 및 보안 요구사항 (Quality & Security)

### REQ-Q01: 피드백 링크 HMAC 서명 연동 (버그 수정)

- **현재 문제** (🚨 치명적 버그):
  `feedback_manager.py`의 `generate_feedback_link()` 함수가 HMAC 서명 없이 URL을 생성합니다.
  반면 `feedback_server.py`의 `submit_feedback()` 엔드포인트는 `verify_signature()`로 서명을 검증합니다.
  따라서 **현재 피드백 기능이 100% 실패하는 구조**입니다.

- **요구사항**:
  `generate_feedback_link()` 함수가 `WEBHOOK_SECRET` 기반 HMAC-SHA256 서명이 포함된 URL을 생성해야 합니다.

- **구현 방법**:

  ```python
  # feedback_manager.py 수정
  import hmac, hashlib, os

  def generate_feedback_link(user_name: str, score: int = 5) -> str:
      secret = os.getenv("WEBHOOK_SECRET", "default_secret_key")
      payload = f"{user_name}:{score}".encode('utf-8')
      signature = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
      base_url = os.getenv("FEEDBACK_BASE_URL", "https://your-domain.com")
      return f"{base_url}/api/feedback?user={user_name}&score={score}&signature={signature}"
  ```

- **기대 효과**: 피드백 루프의 실제 작동 보장
- **영향 범위**: `feedback_manager.py` + `main.py`(호출부)

---

### REQ-Q02: 과도한 타임아웃 설정 일괄 수정 (Notion API + Gemini API)

- **현재 문제**:
  1. `user_manager.py:37`, `prompt_manager.py:29` 에서 Notion API 호출 타임아웃이 **300초(5분)**로 설정. 실제 응답은 2~5초.
  2. `ai_summarizer.py:51`의 `safe_gemini_call()`에서 Gemini API 호출 타임아웃도 **300초(5분)**로 설정. 실제 Gemini 응답은 10~30초 이내.
  3. `queue_worker.py:44`의 이메일 발송 타임아웃도 **300초(5분)** 동일. 실제 SMTP 전송은 10초 이내.

- **요구사항**:
  각 외부 호출 특성에 맞게 합리적인 타임아웃으로 축소하여 빠른 실패(Fail-Fast)를 보장해야 합니다.

- **구현 방법**:
  | 대상 | 현재 | 변경 | 근거 |
  |------|:---:|:---:|------|
  | Notion API (`user_manager.py`, `prompt_manager.py`) | 300s | 30s | 실제 응답 2~5초 |
  | Gemini API (`ai_summarizer.py:safe_gemini_call`) | 300s | 90s | 긴 프롬프트 감안해도 90초면 충분 |
  | SMTP 발송 (`queue_worker.py`) | 300s | 60s | 네트워크 지연 감안 |

- **기대 효과**: 장애 상황에서 파이프라인이 5분간 블로킹되는 것 방지. 빠른 실패 후 재시도로 전체 안정성 향상.
- **영향 범위**: `user_manager.py`, `prompt_manager.py`, `ai_summarizer.py`, `queue_worker.py`

---

### REQ-Q03: 서비스 레이어 테스트 추가

- **현재 문제**:
  `tests/` 폴더에 크롤러 테스트만 존재합니다.
  `ai_summarizer`, `prompt_manager`, `backtesting_scorer`, `feedback_manager` 등
  핵심 서비스에 대한 테스트가 **전무**합니다.

- **요구사항**:
  Mock을 활용한 서비스 단위 테스트를 최소 4개 이상 추가해야 합니다.

- **구현 방법**:
  1. `tests/services/` 디렉토리를 생성합니다.
  2. `test_ai_summarizer.py`: Gemini API Mock + 프롬프트 생성 검증
  3. `test_prompt_manager.py`: 캐시 적재/조회 로직 검증
  4. `test_backtesting_scorer.py`: 스냅샷 로드 및 리포트 생성 검증
  5. `test_feedback_manager.py`: 피드백 기록, 링크 생성, 서명 검증 통합 테스트

- **기대 효과**: 리팩토링 시 회귀 버그 조기 발견
- **영향 범위**: `tests/` 디렉토리

---

### REQ-Q04: Docker Compose 환경 변수 일원화

- **현재 문제**:
  `docker-compose.yml`에 `WEBHOOK_SECRET`만 주입되고 있으며,
  `GEMINI_API_KEY`, `NOTION_TOKEN`, `NOTION_DATABASE_ID` 등 핵심 환경변수가 누락되어 있습니다.

- **요구사항**:
  `env_file` 지시어를 사용하여 `.env` 파일의 모든 환경변수를 컨테이너에 주입해야 합니다.

- **구현 방법**:

  ```yaml
  services:
    feedback-server:
      env_file:
        - .env
      # 기존 environment 블록의 개별 변수 제거
    crawler-pipeline:
      env_file:
        - .env
  ```

- **기대 효과**: Docker 환경에서 파이프라인 정상 작동 보장
- **영향 범위**: `docker-compose.yml`

---

### REQ-Q05: 민감 정보 기본값 보안 강화

- **현재 문제**:
  `feedback_server.py`에서 `WEBHOOK_SECRET`의 기본값이 `"default_secret_key"`로 설정되어 있습니다.
  실수로 환경변수 없이 배포하면 누구나 피드백을 조작할 수 있습니다.

- **요구사항**:
  기본값을 제거하고, 환경변수 미설정 시 서버 시작을 차단하는 가드 로직을 추가해야 합니다.

- **구현 방법**:

  ```python
  WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
  if not WEBHOOK_SECRET:
      raise RuntimeError("환경변수 WEBHOOK_SECRET이 설정되지 않았습니다. 보안을 위해 서버를 시작할 수 없습니다.")
  ```

- **기대 효과**: 프로덕션 환경에서의 보안 사고 예방
- **영향 범위**: `feedback_server.py`

---

### REQ-Q06: 루트 디렉토리 산재 파일 정리

- **현재 문제**:
  루트 디렉토리에 `test_async_gemini.py`, `test_db.py`, `test_notion.py`, `test_gemini.py`,
  `test_gemini2.py`, `add_columns.py`, `check_notion.py`, `update_notion_db.py`,
  `update_notion_schema.py`, `update_notion_user.py` 등 일회성 스크립트가 방치되어 있습니다.

- **요구사항**:
  이 파일들을 `scripts/` 디렉토리로 이동하거나, 불필요한 파일은 삭제하여 프로젝트 루트를 정리해야 합니다.

- **기대 효과**: 프로젝트 구조 가독성 향상, 신규 개발자 온보딩 효율 증대
- **영향 범위**: 루트 디렉토리

---

### REQ-P05: Gemini Batch 호출 도입 (멀티 테마 일괄 분석)

- **현재 문제**:
  사용자별로 테마 브리핑을 개별 `safe_gemini_call`로 호출합니다.
  `Semaphore(2)`로 인해 동시에 2건만 처리되어, 키워드 3개인 사용자는 최소 2라운드의 API 호출이 필요합니다.

- **요구사항**:
  여러 테마를 하나의 프롬프트로 통합하여 1회 API 호출로 처리해야 합니다.

- **구현 방법**:
  1. `ai_summarizer.py`에 `async def generate_multi_theme_briefing(themes: list[dict]) -> dict` 함수 추가
  2. 프롬프트에 "다음 N개 테마에 대해 각각 분석해줘"라는 지시를 추가하고, JSON 구조로 출력하도록 유도
  3. 반환된 결과를 테마별로 파싱하여 기존 `theme_briefings` 리스트에 매핑
  4. `main.py`에서 키워드별 개별 호출 대신 배치 호출로 교체

- **기대 효과**: API 호출 횟수 60% 절감, Rate Limit 위험 감소
- **영향 범위**: `ai_summarizer.py`, `main.py`

---

### REQ-P06: JSON 파일 → SQLite 마이그레이션

- **현재 문제**:
  `logging/ai_predictions.json`, `logging/user_feedback.json` 등이 파일 기반으로 관리됩니다.
  동시 쓰기 시 Race Condition 위험, 파일 크기 증가 시 전체 읽기/쓰기 성능 저하,
  특정 조건의 데이터 조회(예: "최근 7일 평균 별점")가 어렵습니다.

- **요구사항**:
  경량 SQLite DB로 마이그레이션하여 데이터 무결성과 쿼리 효율을 확보해야 합니다.

- **구현 방법**:
  1. `src/utils/database.py` 신규 모듈을 생성합니다.
  2. `predictions`, `feedback` 테이블 스키마를 정의합니다.
  3. `ai_tracker.py`와 `feedback_manager.py`의 JSON 읽기/쓰기를 SQLite 쿼리로 교체합니다.
  4. 기존 JSON 파일에서 기존 데이터를 마이그레이션하는 스크립트를 제공합니다.

- **기대 효과**: 데이터 무결성 확보, 피드백 분석/백테스팅 쿼리 효율 대폭 향상
- **영향 범위**: `ai_tracker.py`, `feedback_manager.py`, `backtesting_scorer.py`, 신규 `database.py`

---

### REQ-Q07: 동기 Notion 호출의 비동기 전환 (이벤트 루프 블로킹 방지)

- **현재 문제**:
  `main.py:58`의 `fetch_prompts_from_notion()`과 `main.py:78`의 `fetch_active_users()`가
  동기 함수(`httpx.get()` 사용)인데 async 파이프라인 내에서 `await` 없이 직접 호출됩니다.
  이로 인해 Notion API 호출 중 **이벤트 루프가 블로킹**되어 다른 비동기 작업이 정지됩니다.

- **요구사항**:
  두 함수를 비동기 실행으로 전환하여 이벤트 루프 블로킹을 제거해야 합니다.

- **구현 방법 (방법 A - 최소 변경)**:
  `main.py`에서 두 호출을 `asyncio.to_thread()`로 래핑합니다.

  ```python
  await asyncio.to_thread(fetch_prompts_from_notion)
  users = await asyncio.to_thread(fetch_active_users)
  ```

- **구현 방법 (방법 B - 완전 비동기 전환)**:
  `user_manager.py`와 `prompt_manager.py`의 `httpx.get()`을 `httpx.AsyncClient`로 교체하고,
  함수 자체를 `async def`로 변경합니다.

- **기대 효과**: 파이프라인 시작 단계에서의 이벤트 루프 블로킹 제거
- **영향 범위**: `main.py`, `user_manager.py`, `prompt_manager.py`

---

### REQ-F06: 별점 기반 자동 프롬프트 튜닝 루프

- **현재 문제**:
  `user_feedback.json`에 사용자 별점이 쌓이고 있으나, 피드백이 프롬프트 개선에 전혀 연동되지 않습니다.
  피드백 루프가 수집 단계에서 끊겨 있는 상태입니다.

- **요구사항**:
  최근 N일간 평균 별점이 일정 수준 이하일 경우, 프롬프트를 자동으로 조정하는 피드백 루프를 구축해야 합니다.

- **구현 방법**:
  1. `feedback_manager.py`에 `get_average_score(window_days=7)` 함수를 추가합니다.
  2. 파이프라인 시작 시 평균 별점을 체크합니다.
  3. 3.0 미만이면 `temperature`를 0.3으로 낮추거나, 프롬프트에 "더 실질적이고 구체적인 조언 위주로" 지시를 추가합니다.

- **기대 효과**: 진정한 AI 자율 개선 시스템의 초석
- **영향 범위**: `feedback_manager.py`, `ai_summarizer.py` 또는 `prompt_manager.py`

---

### REQ-F07: 프롬프트 버전 관리 및 A/B 테스트

- **현재 문제**:
  Notion 프롬프트 DB에 버전 추적이 없어, 어떤 프롬프트가 좋은 평가를 받았는지 알 수 없습니다.

- **요구사항**:
  프롬프트에 `Version`, `Variant` 필드를 추가하고, 피드백과 연결하여 어떤 버전이 높은 평점을 받는지 자동 추적해야 합니다.

- **구현 방법**:
  1. Notion 프롬프트 DB 스키마에 `Version`, `Variant` 필드를 추가합니다.
  2. `prompt_manager.py`에서 동일 Title의 프롬프트가 여러 Variant로 존재할 경우 랜덤 선택합니다.
  3. 선택된 Variant를 피드백과 연결하여 추적합니다.

- **기대 효과**: 데이터 기반 프롬프트 최적화
- **영향 범위**: Notion DB 스키마, `prompt_manager.py`

---

### REQ-Q08: E2E 파이프라인 드라이런 테스트

- **현재 문제**:
  전체 파이프라인을 관통하는 통합 테스트가 없어, 크롤러↔AI↔발송 간 연동 오류를 사전에 감지할 수 없습니다.

- **요구사항**:
  Mock 데이터 기반의 전체 파이프라인 드라이런(Dry-Run) 테스트를 구현해야 합니다.

- **구현 방법**:
  1. `tests/test_pipeline_e2e.py` 신규 파일을 생성합니다.
  2. 크롤러/AI/발송을 모두 Mock으로 대체합니다.
  3. `run_pipeline()` 전체 흐름이 정상 완료되는지 검증합니다.
  4. 사용자 0명 시 조기 종료, 특정 크롤러 실패 시 나머지 동작을 검증합니다.

- **기대 효과**: 배포 전 완전한 기능 검증 가능
- **영향 범위**: `tests/` 디렉토리

---

_작성일: 2026-03-02 | 기준: Phase 5 완료 후 전체 코드베이스 정밀 분석 결과_
_갱신일: 2026-03-02 | Gap Analysis 교차 검증 반영 (REQ-P05, REQ-P06, REQ-Q07 추가, REQ-P01/REQ-Q02 보정)_
_최종 검증: 2026-03-02 | 3문서 일관성 검증 (REQ-F06, REQ-F07, REQ-Q08 추가, 총 21개 REQ 완비)_
