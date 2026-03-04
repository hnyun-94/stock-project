# 프로덕션 에러: Gemini API + Reddit 장애 (2026-03-04)

## 에러 상황

### 1. Reddit WSB API HTTP 403

- **발생 시각**: 2026-03-04 22:01:08
- **원인**: GitHub Actions IP가 Reddit 봇 탐지에 걸림
- **영향**: 커뮤니티 데이터 수집 실패 (파이프라인 계속 진행)

### 2. Gemini API ClientError → Circuit Breaker Open

- **발생 시각**: 2026-03-04 22:02:30 ~ 22:03:51
- **원인**: google-genai SDK 비동기 호출 네트워크 에러
- **영향**: 2회 연속 실패 → Circuit Breaker Open → 이후 모든 AI 호출 차단 (6건)
- **결과**: 리포트에 `⚠️ [Circuit Open]` 텍스트만 포함되어 발송

## 조치 방법 (PR #19)

### Circuit Breaker 완화

- `failure_threshold`: 2 → 5 (일시적 장애에 내성 확보)
- `recovery_timeout`: 120초 → 300초 (충분한 복구 대기)

### Gemini Retry 전략 개선

- `wait_exponential(multiplier=5, min=10, max=60)` → `(multiplier=3, min=5, max=30)`
- `stop_after_attempt(5)` → `3` (전체 대기 시간 단축: ~80초 → ~35초)
- 에러 발생 시 에러 클래스명과 메시지를 로그에 포함 (디버깅 용이)
- try/except로 TimeoutError와 일반 Exception 분리 처리

### Reddit 크롤러 개선

- `REDDIT_ENABLED` 환경변수 추가 (기본값: true)
- CI/CD에서 `REDDIT_ENABLED=false`로 비활성화 가능
- 403 에러를 ERROR → WARNING으로 레벨 조정
- User-Agent를 Reddit API 가이드라인 준수 형식으로 변경

## 재발 방지

- GitHub Actions workflow에 `REDDIT_ENABLED: false` 환경변수 추가 권장
- Circuit Breaker 설정은 운영 데이터 축적 후 추가 조정
