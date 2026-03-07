# Gemini Quota Delay-Aware Retry 개선 계획

작성일: 2026-03-08  
상태: 완료

---

## 1) 문제 정의

- 현재 Gemini 429 quota 오류는 `retryDelay`가 응답에 포함돼도 즉시 quota block으로 전환됩니다.
- 이 방식은 짧은 일시적 quota 구간에서도 바로 로컬 fallback으로 내려가 AI 품질을 회복할 기회를 놓칩니다.
- 반대로 긴 대기 시간을 무조건 기다리면 리포트 발송 시간이 과도하게 늘어나 사용자 경험과 운영 안정성을 해칩니다.

---

## 2) 역할별 검토

### PM

- 짧게 기다리면 AI 품질을 회복할 수 있는 상황에서는 기다리는 편이 사용자 가치가 높습니다.
- 다만 발송 지연이 1분을 넘기면 전체 리포트 경험을 해칠 수 있어 상한선이 필요합니다.

### TPM

- 기존 quota block/fallback 구조를 유지하면서 `safe_gemini_call` 내부에 지연 재시도 창만 추가하는 것이 가장 안전합니다.
- 전역 정책은 환경변수 기반 상수로 두고, 기본값은 `retryDelay + 3초 버퍼`, 총 대기 상한은 60초로 두는 것이 운영 제어에 유리합니다.

### 기획자

- 사용자는 AI가 되는 경우엔 더 좋은 리포트를 받고, 안 되면 오래 기다리지 않고 fallback을 받아야 합니다.
- “짧게 기다리고, 오래 걸리면 포기한다”는 규칙이 가장 이해하기 쉽습니다.

### 시니어 개발자

- retry는 quota 오류에만 선택적으로 적용해야 하며, 일반 오류나 모델 404 fallback 흐름을 섞지 않아야 합니다.
- 기존 tenacity 재시도와 충돌하지 않도록 quota는 내부적으로 한 번만 지연 재시도하고, 실패 시 Permanent 오류로 종료하는 구조가 적절합니다.

### 개발자

- `_generate_content_with_quota_retry()` 같은 국소 helper로 빼면 메인 흐름을 크게 흔들지 않고 primary/fallback model 호출에 공통 적용할 수 있습니다.
- 테스트는 `짧은 지연 성공`, `긴 지연 fallback`, `재시도 후 block` 3가지를 고정해야 합니다.

### 품질 담당자

- quota retry는 성공/실패 기준이 분명해야 합니다.
- `60초 이내 지연만 허용`, `초과 시 즉시 fallback`, `재시도 후 재실패 시 block`이 검증 가능한 규칙입니다.

### 신입개발자

- 재시도 정책은 `safe_gemini_call` 하나만 보면 이해 가능해야 합니다.
- helper 함수와 테스트 명이 정책을 그대로 설명하도록 만드는 것이 중요합니다.

### 운영자

- 6초, 10초처럼 짧은 retryDelay는 약간의 버퍼를 더해 기다리는 편이 운영 품질에 유리합니다.
- 1분을 넘는 대기는 스케줄러 지연과 중첩 런 리스크가 커지므로 즉시 fallback이 맞습니다.

### 주식 전문가

- 리포트 품질은 AI 요약이 살아 있을 때 더 높지만, 발송이 과도하게 늦어지는 것은 실시간 해석 가치와 충돌합니다.
- 따라서 짧은 복구 창만 허용하는 절충안이 적절합니다.

### UI/UX 전문가

- 메일/알림 리포트는 “조금 더 정확한 내용”보다 “적절한 시간 안에 도착하는 것”이 더 중요할 때가 많습니다.
- 1분 상한은 체감 지연을 관리하는 UX 기준으로 타당합니다.

### 퍼블리셔 전문가

- 발행 지연이 길어지면 같은 내용도 가치가 떨어집니다.
- 짧은 delay retry는 허용하되, 발행 SLA를 넘기지 않도록 cutoff가 필요합니다.

### 프롬프트 전문가

- quota retry는 프롬프트 변경 이슈가 아니라 호출 제어 이슈입니다.
- 프롬프트를 손대지 않고 transport 제어 계층에서 해결하는 편이 원인 분리가 명확합니다.

### 컨텍스트 엔지니어

- 이번 변경은 `ai_summarizer`와 테스트, 기준 문서만 건드리는 게 맞습니다.
- 운영 규칙은 코드와 문서에만 닫고 AGENTS/skill 변경까지 넓히지 않는 편이 컨텍스트 효율상 낫습니다.

---

## 3) 구현 판단

- 채택 1: Gemini 429 quota 응답의 `RetryInfo.retryDelay`를 읽고, 실제 대기는 `retryDelay + 3초` 버퍼로 계산
- 채택 2: `retryDelay + 3초 + 현재까지 경과 시간 <= 60초`일 때만 지연 재시도
- 채택 3: 재시도 후에도 quota면 기존 quota block/fallback 로직으로 전환
- 채택 4: 60초를 넘는 대기는 기다리지 않고 즉시 fallback
- 기각 1: 모든 quota 오류를 무조건 즉시 block
  - 이유: 짧은 일시적 quota 구간에서도 AI 품질 회복 기회를 버립니다.
- 기각 2: `retryDelay`가 얼마든 전부 기다리기
  - 이유: 발송 지연이 커져 사용자 경험과 운영 안정성이 악화됩니다.

---

## 4) 적용 범위

- `src/services/ai_summarizer.py`
  - delay-aware retry helper 추가
  - 60초 retry budget 적용
- `tests/services/test_ai_summarizer.py`
  - 짧은 delay 성공 / 긴 delay fallback / 후속 block 테스트 추가
- 기준 문서
  - `done/completed_work_report.md`
  - `task/next_steps_roadmap.md`
  - `todo/todo.md`

---

## 5) 완료 기준

- `retryDelay`가 짧을 때는 실제 대기 후 재시도 경로가 동작해야 합니다.
- `retryDelay`가 60초를 넘으면 기다리지 않고 fallback으로 전환해야 합니다.
- 동일 quota 재실패 후에는 follow-up call이 block 상태를 따라야 합니다.
- 전체 품질 게이트, PR, merge까지 완료해야 합니다.
