# 모듈 의존성 맵 (Module Dependency Map)

> 각 모듈의 import 관계와 역할을 시각화합니다.
> 코드 수정 시 영향 범위를 파악하는 데 사용합니다.
> 새 모듈 추가 시 이 문서도 함께 업데이트 필수.

---

## 진입점

```
src/main.py  (asyncio.run → main_with_timeout → run_pipeline)
├── src/crawlers/*      (데이터 수집, 11개 모듈)
├── src/services/*      (비즈니스 로직, 9개 + notifier 4개)
├── src/utils/*         (유틸리티, 8개 모듈)
└── src/models.py       (DTO, 5개 dataclass)

src/apps/feedback_server.py  (별도 진입점, FastAPI)
├── src/services/feedback_manager.py
└── src/utils/logger.py
```

## 크롤러 계층

```
src/crawlers/
├── http_client.py      ← 모든 크롤러가 의존 (aiohttp 싱글톤 세션)
│                         exports: get_session(), close_session()
├── browser_pool.py     ← dynamic_community.py만 의존 (Playwright)
│                         exports: BrowserPool.get_page(), .cleanup()
│
├── market_index.py     ← http_client, BeautifulSoup, models(MarketIndex)
├── naver_news.py       ← http_client, BeautifulSoup, models(NewsArticle)
├── daum_news.py        ← http_client, BeautifulSoup, models(NewsArticle)
├── google_news.py      ← http_client, feedparser, models(NewsArticle)
├── community.py        ← http_client, os, BeautifulSoup, models(CommunityPost)
│                         env: REDDIT_ENABLED
├── google_trends.py    ← http_client, pytrends, models(SearchTrend)
├── naver_datalab.py    ← http_client, models(SearchTrend)
│                         env: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
├── article_parser.py   ← http_client, BeautifulSoup, models(NewsArticle)
└── dynamic_community.py ← browser_pool, models(CommunityPost)
```

## 서비스 계층

```
src/services/
├── ai_summarizer.py    ← google-genai, circuit_breaker, prompt_manager,
│                         prompt_tuner, tenacity(retry), asyncio,
│                         models(*), logger
│                         env: GEMINI_API_KEY
│                         exports: safe_gemini_call(), generate_market_summary(),
│                                  generate_theme_briefing(),
│                                  generate_personalized_portfolio_analysis()
│
├── prompt_manager.py   ← httpx, os, logger
│                         env: NOTION_TOKEN, NOTION_PROMPT_DB_ID
│                         exports: fetch_prompts_from_notion(), get_prompt()
│
├── prompt_tuner.py     ← database, logger
│                         exports: get_tuned_prompt_params()
│
├── prompt_versioning.py ← database, hashlib, logger
│                         exports: PromptVersionManager
│
├── user_manager.py     ← httpx, os, models(User), logger
│                         env: NOTION_TOKEN, NOTION_DATABASE_ID
│                         exports: fetch_active_users()
│
├── feedback_manager.py ← database, hmac, hashlib, os, logger
│                         env: WEBHOOK_SECRET, FEEDBACK_BASE_URL
│                         exports: record_feedback(), generate_feedback_link(),
│                                  generate_feedback_links_html()
│
├── ai_tracker.py       ← database, logger
│                         exports: record_prediction_snapshot()
│
├── backtesting_scorer.py ← database, ai_summarizer, logger
│                         exports: generate_backtesting_report()
│
└── notifier/
    ├── base.py         ← ABC (추상 클래스)
    │                     exports: SenderBase
    ├── email.py        ← smtplib, base, logger
    │                     env: SENDER_EMAIL, SENDER_APP_PASSWORD
    ├── telegram.py     ← httpx, base, logger
    │                     env: TELEGRAM_BOT_TOKEN
    └── queue_worker.py ← threading, queue, base, logger
                          exports: global_message_queue, NotificationAction
```

## 유틸리티 계층

```
src/utils/
├── logger.py           ← 의존 없음 (다른 모든 모듈이 의존)
│                         exports: global_logger, log_critical_error()
│
├── database.py         ← sqlite3, threading, os, logger
│                         exports: Database, get_db()
│                         DB 경로: data/stock_project.db
│
├── cache.py            ← threading, time, logger
│                         exports: TTLCache, crawl_cache (싱글톤 인스턴스)
│
├── deduplicator.py     ← re, difflib, models(NewsArticle), logger
│                         exports: deduplicate_news()
│
├── sentiment.py        ← logger
│                         exports: analyze_sentiment(), format_sentiment_section()
│
├── circuit_breaker.py  ← asyncio, time, functools, logger
│                         exports: async_circuit_breaker (데코레이터)
│
├── report_formatter.py ← markdown
│                         exports: build_markdown_report()
│
└── auto_patcher.py     ← (실험적, 프로덕션 미사용)
```

## 수정 시 영향도 가이드

| 수정 대상              | 영향 범위                                    | 위험도 | 테스트 방법                             |
| ---------------------- | -------------------------------------------- | :----: | --------------------------------------- |
| `models.py`            | **전체** — 모든 크롤러와 서비스              |   🔴   | 전체 테스트 실행                        |
| `http_client.py`       | 크롤러 11개                                  |   🔴   | 크롤러 테스트 (aiohttp 필요)            |
| `database.py`          | feedback, tracker, scorer, tuner, versioning |   🔴   | `test_database.py` + 관련 서비스 테스트 |
| `ai_summarizer.py`     | main.py (AI 호출 전체)                       |   🟠   | `test_e2e_dryrun.py`                    |
| `circuit_breaker.py`   | ai_summarizer 직접 의존                      |   🟠   | 수동 검증 (단위 테스트 없음)            |
| `main.py`              | 파이프라인 진입점                            |   🟠   | E2E + 수동 실행                         |
| `cache.py`             | main.py (캐시 로직)                          |   🟡   | `test_cache.py`                         |
| `deduplicator.py`      | main.py (중복 제거)                          |   🟡   | `test_deduplicator.py`                  |
| `sentiment.py`         | main.py (감정 분석)                          |   🟡   | `test_sentiment.py`                     |
| `prompt_manager.py`    | ai_summarizer                                |   🟡   | 수동 검증 (Notion 의존)                 |
| `prompt_tuner.py`      | ai_summarizer                                |   🟢   | `test_prompt_tuner.py`                  |
| `prompt_versioning.py` | 독립 모듈                                    |   🟢   | `test_prompt_versioning.py`             |
| `feedback_manager.py`  | feedback_server                              |   🟢   | `test_feedback_manager.py`              |
| `notifier/*`           | main.py (발송)                               |   🟢   | `test_notifier.py`                      |

## 신규 모듈 추가 시 체크리스트

1. [ ] `src/` 하위 적절한 위치에 모듈 생성 (상단 docstring 필수)
2. [ ] `tests/services/test_모듈명.py` 단위 테스트 작성
3. [ ] 이 파일 (`DEPENDENCY_MAP.md`)에 의존성 추가
4. [ ] `AGENTS.md`의 Project Structure에 파일 추가
5. [ ] `main.py` 또는 호출 모듈에 import 추가
6. [ ] 테스트 실행: `python -m pytest tests/services/ tests/test_e2e_dryrun.py -v`
