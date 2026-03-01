# 주식 리포트 자동화 프로젝트 - 향후 작업 계획 (TODO)

현재 코어 기능(뉴스/트렌드/지수 데이터 수집, AI 프롬프트 연동, Email 발송 시스템, Github Actions 자동 스케줄링)의 1차 MVP 뼈대가 모두 개발/연동 완료되었습니다.

앞으로 고도화하고 진행되어야 할 주요 작업들의 목록은 아래와 같습니다.

## 0. 클린 아키텍처 및 단위 테스트(TDD) 환경 구축

- [x] **0.1 프로젝트 폴더 소문자화 및 문서 최신화**
  - 기존 `Logging`, `errorCase`, `TODO` 등 대문자 포함 폴더를 `logging`, `errorcase`, `todo` 등 소문자로 일괄 변경하고 `main-guide.md` 등 규칙 문서를 업데이트.
- [x] **0.2 클린 코드 아키텍처 패턴 수립 (DTO & Abstract)**
  - Crawler 등 외부 의존성이 있는 모듈들의 반환값을 Dictionary 대신 DTO(`dataclasses` 또는 `pydantic`)로 통일하고 인터페이스 등을 분리 검토.
- [x] **0.3 핵심 모듈 단위 테스트(pytest) 작성**
  - 신규 기능 추가에 앞서, 기존 작성된 `src/crawlers` 및 `src/services` 내 핵심 함수들의 단위 테스트(`tests/`)를 작성하고 성공 여부 확인.

## 1. 알림 채널 확장

- [x] **1.1 카카오톡 알림톡/메시지 구현 방향 검토**
  - 현재 이메일 발송(`email_sender.py`)은 완성되었으나, 즉각적인 확인을 돕기 위해 카카오 비즈니스 알림톡(유료) 혹은 카카오톡 봇(무료/개인용 API) 연동 검토. (todo/03_notification_channel_review.md 참고 - 비용 및 사업자 한계로 Telegram 선도입 확정)
- [x] **1.2 텔레그램(Telegram) 봇 발송 채널 추가 검토**
  - 개발자가 가장 쉽게 적용하고 방(Channel) 단위로 구독자들에게 배포하기 좋은 시스템이므로 `telegram-bot` API 연동 모듈 개발 추가 건. (적용 완료됨)

## 2. 데이터 크롤링 및 수집 고도화

- [x] **2.1 네이버 증권 세부 지표 수집 추가**
  - 지수뿐 아니라 달러 환율/유가/금시세 등 거시 경제(Macro) 지표 추가 크롤링 구성 및 파이프라인 연동 완료.
- [x] **2.2 디시인사이드 외 추가 커뮤니티 파싱 검토**
  - 글로벌 주식 민심 및 밈(Meme) 트렌드 파악을 위해 `Reddit WallStreetBets(r/wallstreetbets)`의 Hot 타임라인 게시글 파싱 크롤러(`get_reddit_wallstreetbets`)를 추가하고 메인 병렬 파이프라인(`asyncio.gather`)에 연동 완료. (캡챠가 심한 블라인드, 펨코 대신 가장 우회 리스크가 적고 글로벌 시야 확보가 가능한 레딧 채택)
- [x] **2.3 데이터 수집 병렬 처리 안정화**
  - 기존 동기적(`requests`) 흐름을 `asyncio` 및 `aiohttp` 기반으로 비동기(Async) 병렬 처리 구조로 대폭 개선. (각종 크롤러 및 이메일 수신자 키워드 파싱 속도 O(N) 개선)

## 3. 사용자 구독/관심사 세분화 로직 강화

- [x] **3.1 Notion 필터링 심화 및 안정화**
  - `user_manager.py`의 `query` 과정에서 Notion Filter 이슈(버전/클래스 충돌)를 httpx로 걷어내고, 사용자가 세팅한 Custom Column(Multi-select, Select 등)을 안전하게 파싱하도록 보강 완료.
- [x] **3.2 테마 키워드 개수 및 속도 조절 이슈 대응 (Rate Limit 우회)**
  - Gemini API의 일일/분당 Rate Limit (429 RESOURCE_EXHAUSTED) 예외를 피하기 위해 `tenacity` 라이브러리를 활용한 `Exponential Backoff Wait(지수 백오프 대기)` 및 `asyncio.Semaphore` 기반 큐(Queue) 로직 도입을 완료했습니다.

## 4. 로깅 시스템 및 오류 모니터링 고도화

- [x] **4.1 Error Webhook 도입 (텔레그램)**
  - `src/utils/logger.py` 내에 에러 발생 시 관리자(`ADMIN_TELEGRAM_CHAT_ID`)로 즉각 알림을 발송하는 로직 신규 구축.
- [x] **4.2 Daily 로깅 자동화 및 예외 기록 보존 체계**
  - 파이썬 표준 `logging` 모듈 및 `TimedRotatingFileHandler`를 활용해 일일 로그를 `logging/app.log` 형태로 저장.
  - 치명적 에러 발생 시 상세 `Traceback` 내역을 `errorcase/YYYY-MM-DD_HHMMSS_error.md` 형식으로 자동 저장하여 영구 보존.
