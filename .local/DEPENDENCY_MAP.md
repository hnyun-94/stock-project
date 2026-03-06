# 모듈 의존성 맵 (Module Dependency Map)

> 각 모듈의 import 관계와 역할을 시각화합니다.
> 코드 수정 시 영향 범위를 파악하는 데 사용합니다.

---

## 진입점

```
src/main.py
├── src/crawlers/*      (데이터 수집)
├── src/services/*      (비즈니스 로직)
├── src/utils/*         (유틸리티)
└── src/models.py       (DTO)
```

## 크롤러 계층

```
src/crawlers/
├── http_client.py      ← 모든 크롤러가 의존 (aiohttp 세션 풀)
├── browser_pool.py     ← dynamic_community.py만 의존 (Playwright)
├── market_index.py     ← http_client, models(MarketIndex)
├── naver_news.py       ← http_client, models(NewsArticle)
├── daum_news.py        ← http_client, models(NewsArticle)
├── google_news.py      ← http_client, models(NewsArticle), feedparser
├── community.py        ← http_client, models(CommunityPost)
├── google_trends.py    ← http_client, models(SearchTrend), pytrends
├── naver_datalab.py    ← http_client, models(SearchTrend)
├── article_parser.py   ← http_client, models(NewsArticle)
└── dynamic_community.py ← browser_pool, models(CommunityPost)
```

## 서비스 계층

```
src/services/
├── ai_summarizer.py    ← google-genai, circuit_breaker, prompt_manager, prompt_tuner
│                         tenacity(retry), models(*)
├── prompt_manager.py   ← httpx, Notion API
├── prompt_tuner.py     ← database
├── prompt_versioning.py ← database
├── user_manager.py     ← httpx, Notion API, models(User)
├── feedback_manager.py ← database, hmac
├── ai_tracker.py       ← database
├── backtesting_scorer.py ← database, ai_summarizer
└── notifier/
    ├── base.py         ← ABC
    ├── email.py        ← smtplib, base
    ├── telegram.py     ← httpx, base
    └── queue_worker.py ← threading, queue, base
```

## 유틸리티 계층

```
src/utils/
├── logger.py           ← 의존 없음 (다른 모든 모듈이 의존)
├── database.py         ← sqlite3, logger (싱글톤)
├── cache.py            ← logger
├── deduplicator.py     ← logger, models(NewsArticle)
├── sentiment.py        ← logger
├── circuit_breaker.py  ← logger
├── report_formatter.py ← markdown
└── auto_patcher.py     ← (실험적, 미사용)
```

## 수정 시 영향도 가이드

| 수정 대상            | 영향 범위                                    | 테스트                           |
| -------------------- | -------------------------------------------- | -------------------------------- |
| `models.py`          | **전체** — 모든 크롤러와 서비스가 의존       | 전체 테스트 실행                 |
| `http_client.py`     | 크롤러 전체                                  | 크롤러 테스트 (aiohttp 필요)     |
| `database.py`        | feedback, tracker, scorer, tuner, versioning | `test_database.py` + 관련 서비스 |
| `ai_summarizer.py`   | main.py (AI 호출)                            | `test_e2e_dryrun.py`             |
| `circuit_breaker.py` | ai_summarizer만 직접 의존                    | 수동 검증                        |
| `cache.py`           | main.py (캐시 로직)                          | `test_cache.py`                  |
| `deduplicator.py`    | main.py (중복 제거)                          | `test_deduplicator.py`           |
| `sentiment.py`       | main.py (감정 분석)                          | `test_sentiment.py`              |
| `main.py`            | 파이프라인 진입점                            | E2E 테스트 + 수동 검증           |
