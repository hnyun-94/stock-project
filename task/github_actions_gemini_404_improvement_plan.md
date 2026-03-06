# GitHub Actions Gemini 404 개선 작업계획서

작성일: 2026-03-07  
대상 장애: `models/gemini-1.5-flash is not found (404 NOT_FOUND)`

---

## 1) 개선 목표

- 모델 종료/변경에도 파이프라인이 중단되지 않도록 복원력 확보
- 영구 오류를 빠르게 판별해 불필요한 재시도·CB 소모 제거
- CI 잡음을 줄여 실제 장애 신호를 선명하게 유지

## 2) 다각도 개선 포인트

### A. 백엔드 안정성 관점

- 고정 모델 의존 제거 (`gemini-1.5-flash` 하드코딩 제거)
- 가용 모델 자동 선택 (`ListModels` + 후보군)
- 404 즉시 대체 모델 전환

### B. 장애내성/운영 관점

- 영구 설정 오류는 재시도 제외
- Circuit Breaker는 실제 서비스 장애만 반영되도록 오탐 감소
- CI에서 Reddit 비활성화로 403 경고 제거

### C. 구성관리 관점

- `.env.template`에 모델 관련 env 명세 추가
- 워크플로우 env 명시 (`GEMINI_MODEL`, `GEMINI_MODEL_CANDIDATES`, `REDDIT_ENABLED`)

### D. QA 관점

- 모델 선택/404 판별 helper 단위 테스트 추가
- 품질 게이트(`tests/services + e2e_dryrun`) 통과 확인

## 3) 실행 항목

1. `src/services/ai_summarizer.py`
   - 모델 후보/선택/가용성 조회 helper 추가
   - 404 모델 오류 시 fallback 모델 자동 전환
   - 재시도 정책 개선(영구 오류 제외)
2. `src/services/prompt_manager.py`
   - Notion 프롬프트 기본 모델 갱신
3. `.github/workflows/report_scheduler.yml`
   - CI env 개선 (`REDDIT_ENABLED=false` 포함)
4. `.env.template`
   - 신규 env 문서화
5. `tests/services/test_ai_summarizer.py`
   - helper 테스트 보강

## 4) 검증 계획

- 로컬: `python -m pytest tests/services/ tests/test_e2e_dryrun.py -q`
- 훅: `.githooks/pre-push`
- 장애 회귀:
  - 모델 404 시 대체 모델 전환 로그 확인
  - 대체 모델 부재 시 명확한 설정 오류 메시지 확인

## 5) 완료 기준

- 품질 게이트 100% 통과
- 기존 404 연쇄 재시도 패턴이 개선되어 동일 장애 재발 가능성 감소
- 운영 문서/환경 변수 설명이 코드와 일치
