# 향후 고도화 및 요구사항 (Todo - Phase 6: 성능 및 기능 최적화)

# 이 문서는 Phase 5까지 완료된 프로젝트를 4가지 역할(기획자, 백엔드, AI/데이터, QA)

# 관점에서 분석하여 도출한 최적화 과제 체크리스트입니다.

# 상세 구현 방법은 requirements/04_phase6_optimization_requirements.md를 참조합니다.

# 실제 진행 Task 명세는 task/phase6_task.md를 참조합니다.

---

## 🔧 백엔드/인프라 엔지니어 관점

### Sprint 1 - Quick Wins (즉시 적용)

- [x] **REQ-P01: aiohttp ClientSession 재사용** ← 🥇 최우선 ✅ PR #2
  - `src/crawlers/http_client.py` 신규 생성, 크롤러 **7개** 파일 세션 교체 (google_trends.py 포함)
  - 기대 효과: 크롤링 전체 시간 20~40% 단축

- [x] **REQ-P03: Gemini 클라이언트 싱글톤 패턴 적용** ✅ PR #3
  - `ai_summarizer.py` 내 `_get_client()` 싱글톤 전환 + 데드 코드 제거

- [x] **REQ-P04: BrowserPool 자원 해제 보장** ✅ PR #6
  - `main.py`의 `finally` 블록에서 `BrowserPool.cleanup()` 호출

- [x] **REQ-Q04: Docker Compose 환경 변수 일원화** ✅ PR #4
  - `docker-compose.yml`에 `env_file: .env` 추가

### Sprint 2 - Performance (성능 개선)

- [x] **REQ-P02: 키워드 뉴스 크롤링 완전 병렬화** ✅ PR #5
  - `main.py`의 순차 for 루프 → `asyncio.gather` 완전 병렬화
  - 기대 효과: 사용자당 50% 시간 단축

- [x] **REQ-F03: 크롤링 결과 인메모리 캐싱** ✅ PR #8
  - `src/utils/cache.py` TTLCache 클래스 구현, 동일 키워드 크롤링 결과 재사용

- [ ] **REQ-P05: Gemini Batch 호출 도입 (멀티 테마 일괄 분석)** ← 🆕
  - 여러 테마를 하나의 프롬프트로 통합 → API 호출 60% 절감

---

## 🎯 기획자 (Product Manager) 관점

### Sprint 3 - Feature (기능 고도화)

- [x] **REQ-F01: 뉴스 본문 리드 문단 수집** ✅ PR #11
  - `src/crawlers/article_parser.py` 신규 생성, 뉴스 본문 첫 2~3문장 추출
  - `NewsArticle.summary` 필드 활용, AI 프롬프트 컨텍스트 품질 향상

- [ ] **REQ-F04: 감정 지표(Sentiment Score) 도입**
  - 커뮤니티 데이터 감정 분석 → "시장 심리 온도계" 리포트 섹션 추가

- [ ] **REQ-F06: 별점 데이터 기반 자동 프롬프트 튜닝**
  - 피드백 평균 별점이 3.0 이하 시 프롬프트 자동 조정 루프 구축

---

## 🤖 AI/데이터 엔지니어 관점

### Sprint 2 - Data Quality

- [x] **REQ-F02: 뉴스 중복 제거 (Deduplication)** ✅ PR #9
  - `src/utils/deduplicator.py` 신규 생성, 제목 유사도 85% 이상 필터링

### Sprint 3 - AI Enhancement

- [ ] **REQ-F05: 백테스팅 채점 정량화**
  - 과거 스냅샷 예측 vs 실제 종가 비교 정량적 스코어링 구현

- [ ] **REQ-F07: 프롬프트 버전 관리 및 A/B 테스트**
  - Notion 프롬프트 DB에 `version` 필드 추가, 피드백과 연결 추적

- [ ] **Structured Output (JSON Mode) 도입**
  - Gemini `response_mime_type: "application/json"` 활용, 리포트 포맷 일관성 확보
  - → REQ-P05(Gemini Batch 호출)에서 함께 처리 가능

---

## ✅ QA / 코드 리뷰어 관점

### Sprint 1 - Critical Bugfix (즉시 수정)

- [x] **REQ-Q01: 피드백 링크 HMAC 서명 연동** ← 🚨 치명적 버그 ✅ PR #1
  - `generate_feedback_link()`에 HMAC 서명 포함 → 현재 100% 실패 상태 해결

- [x] **REQ-Q02: 과도한 타임아웃 일괄 축소** ← 범위 확대 ✅ PR #1
  - `user_manager.py`, `prompt_manager.py`: `timeout=300.0` → `timeout=30.0`
  - `ai_summarizer.py:safe_gemini_call`: `timeout=300.0` → `timeout=90.0` ← 🆕
  - `queue_worker.py` SMTP 발송: `timeout=300.0` → `timeout=60.0` ← 🆕

- [x] **REQ-Q05: 민감 정보 기본값 보안 강화** ✅ PR #1
  - `feedback_server.py`의 `WEBHOOK_SECRET` 기본값 제거, 미설정 시 서버 차단

- [x] **REQ-Q06: 루트 디렉토리 산재 파일 정리** ✅ PR #7
  - 일회성 스크립트 `scripts/` 이동 또는 삭제

### Sprint 4 - Quality (품질 확보)

- [x] **REQ-Q03: 서비스 레이어 테스트 추가** ✅ PR #12
  - `tests/services/` 생성, 캐시/중복제거/피드백 단위 테스트 28개

- [x] **REQ-Q08: E2E 파이프라인 드라이런 테스트** ✅ PR #13
  - 데이터 흐름 통합 테스트 7개 (모델 → 중복제거 → 캐시 → AI 포맷)

### Sprint 4 확장 (Gap Analysis 보완)

- [x] **REQ-Q07: 동기 Notion 호출 비동기 전환** ← 🆕 ✅ PR #10
  - `main.py`의 `fetch_prompts_from_notion()`, `fetch_active_users()`를 `asyncio.to_thread()`로 래핑

- [ ] **REQ-P06: JSON → SQLite 마이그레이션** ← 🆕
  - `src/utils/database.py` 신규 생성, `ai_tracker.py`/`feedback_manager.py` 교체

---

_작성일: 2026-03-02 | 상세 요구사항: `requirements/04_phase6_optimization_requirements.md` 참조_
_진행 Task 명세: `task/phase6_task.md` 참조_
_갱신일: 2026-03-04 19:39 | Sprint 3~4 개발 완료 (15 Task, 13 PR) - 체크리스트 갱신_
