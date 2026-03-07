# GitHub Actions 런타임 상태/전사 리뷰 및 실행 계획서

작성일: 2026-03-07

---

## 1. 리뷰 목적

- GitHub Actions 환경에서 SQLite 기반 상태 저장이 의도대로 유지되는지 검토합니다.
- 전 프로젝트를 성능, 보안, 요구사항 누락, 운영 안정성 관점에서 재검토합니다.
- 즉시 개발할 P0/P1 항목과 후속 백로그를 분리하여 병렬 실행 계획을 수립합니다.

---

## 2. 핵심 결론

### 결론 A. GitHub Actions의 SQLite 상태 유지 구조는 "부분적으로만" 맞습니다.

현재 워크플로우는 `actions/cache`로 `data/stock_project.db`를 복구/저장하려고 시도하므로, **기본 의도(실행 간 상태 유지)** 자체는 존재합니다.

하지만 다음 이유로 완전하지 않습니다.

1. 코드가 `STOCK_DB_PATH` 환경변수를 실제로 사용하지 않습니다.
2. 캐시에서 복구한 DB가 손상되었을 때 자동 복구 경로가 없습니다.
3. 종료 시 WAL checkpoint 보장이 없어 Actions 캐시 저장 직전 상태가 불안정할 수 있습니다.
4. Actions에서 복구된 DB 상태를 검증하는 health-check 단계가 없습니다.

따라서 현재 구조는 "운 좋으면 유지" 수준이며, **운영 가능한 런타임 상태 계층으로 보기는 어렵습니다.**

### 결론 B. 즉시 수정해야 할 보안/요구사항 누락이 존재합니다.

1. `feedback_server.py`는 사용자 입력 `user`를 HTML에 그대로 렌더링하여 XSS 가능성이 있습니다.
2. `user_manager.py`는 Notion DB 첫 페이지(`results`)만 읽기 때문에 사용자 수가 100명을 넘으면 일부 구독자가 누락됩니다.

---

## 3. 멀티롤 리뷰

### PM 관점

- 현상:
  - 최근 추가한 리포트 이력/변화점 기능은 상태 저장이 유지되어야 제품 가치가 나옵니다.
  - 사용자 페이지네이션 부재는 일부 고객이 리포트를 못 받는 문제로 직결됩니다.
- 판단:
  - 이번 사이클의 최우선은 "상태 유지 신뢰성"과 "전체 사용자 전달 보장"입니다.

### TPM 관점

- 현상:
  - Actions 캐시는 존재하지만 복구/무결성 검증/경로 일관성이 빠져 있습니다.
  - DB가 깨졌을 때 파이프라인이 즉시 실패할 가능성이 있습니다.
- 판단:
  - DB path abstraction + integrity recovery + workflow health-check가 P0입니다.

### 기획자 관점

- 현상:
  - "이전 2개 리포트와 현재 비교" 요구는 히스토리 지속성이 전제입니다.
  - 사용자 100명 이상일 때 일부 누락되는 구조는 제품 요구사항 위반입니다.
- 판단:
  - 리포트 상태 유지와 사용자 전체 조회는 기능 요구사항의 기반입니다.

### 개발자 관점

- 현상:
  - `DB_PATH`가 import 시점 상수로 고정되어 런타임 환경과 분리되어 있습니다.
  - SQLite는 WAL/복구/경로 스위칭을 유틸리티로 캡슐화해야 테스트 가능성이 높아집니다.
- 판단:
  - DB 초기화 책임을 정리하고 workflow와 테스트를 같이 보강해야 합니다.

### 신입개발자 관점

- 현상:
  - 현재는 "왜 workflow에 `STOCK_DB_PATH`를 넣었는데 코드가 안 쓰는지"를 처음 보면 이해하기 어렵습니다.
  - 페이지네이션 누락은 리뷰 없이는 놓치기 쉽습니다.
- 판단:
  - 설정-코드 연결을 명시적 helper로 바꾸고 예제 테스트를 추가해야 합니다.

### 운영자 관점

- 현상:
  - 캐시된 DB가 깨지면 운영 장애가 나도 원인 추적이 어렵습니다.
  - feedback 서버 XSS는 운영 리스크이자 외부 노출 문제입니다.
- 판단:
  - DB 상태 점검 로그와 손상 복구, HTML escape는 즉시 반영해야 합니다.

---

## 4. 발견 이슈 분류

### P0 - 이번 사이클 즉시 개발

1. **Actions/SQLite 런타임 상태 계층 정비**
   - env 기반 DB 경로 사용
   - 손상 DB 복구
   - WAL checkpoint/close 강화
   - workflow health-check 및 경로 일관성

2. **Feedback XSS 차단**
   - 사용자 이름 HTML escape
   - 관련 회귀 테스트 추가

### P1 - 이번 사이클 함께 개발

3. **Notion 사용자 페이지네이션**
   - `fetch_active_users()` 반복 조회
   - 100건 초과 사용자 누락 방지
   - 관련 단위 테스트 추가

### P2 - 계획서에 남길 후속 과제

4. **Workflow timeout 재평가**
   - 외부 API 지연 시 `timeout-minutes: 5`가 촉박할 수 있음
5. **DB 연산 직렬화/락 정책 검토**
   - 향후 worker/서버 동시 접근 확장 대비
6. **운영 오류 알림 표준화**
   - DB 복구/손상/restore miss 로그를 운영 텔레메트리로 승격
7. **민감 에러 메시지 최소화**
   - 외부 오류 원문을 그대로 텔레그램으로 보내는 정책 재검토

---

## 5. 실행 계획

### Stream A - 런타임 상태/Actions

- `src/utils/database.py`
  - env 경로 해석 helper 추가
  - DB open/recovery/checkpoint 경로 추가
  - singleton path switching 보강
- `scripts/check_runtime_state.py`
  - SQLite integrity + 주요 테이블 count 출력
- `.github/workflows/report_scheduler.yml`
  - health-check step 추가
  - DB path env를 단계 간 일관되게 사용

### Stream B - 보안

- `src/apps/feedback_server.py`
  - HTML escape helper 추가
  - 렌더링 안전화
- 테스트 추가

### Stream C - 요구사항 누락

- `src/services/user_manager.py`
  - Notion pagination 구현
- 테스트 추가

병합 순서:
- A와 B를 먼저 구현합니다.
- C는 API fetch 로직이 독립적이므로 병렬 구현 후 테스트에서 합칩니다.

---

## 6. 리뷰 라운드 결론

### 라운드 1: 구조 타당성 리뷰

- 상태 저장을 GitHub Actions cache와 SQLite로 유지하는 방향 자체는 유지합니다.
- 이유:
  - 현재 아키텍처와 가장 잘 맞고 변경 범위 대비 효과가 큽니다.

### 라운드 2: 운영 안정성 리뷰

- DB 손상 시 복구 후 재생성하는 self-healing 경로가 필요합니다.
- workflow에서 복구된 DB의 integrity를 노출해야 운영자가 원인을 파악할 수 있습니다.

### 라운드 3: 제품/보안 리뷰

- XSS 차단과 사용자 페이지네이션은 "있으면 좋은 것"이 아니라 기능/보안의 기본선입니다.

최종 결론:
- 이번 구현은 P0/P1 범위를 모두 개발합니다.
- P2는 후속 계획 항목으로 문서화만 하고 이번 PR에서는 제외합니다.

---

## 7. 실행 결과

### 이번 사이클 반영 완료

- `src/utils/database.py`
  - `STOCK_DB_PATH` 런타임 경로 해석 반영
  - 손상 DB 백업 후 재생성(self-healing) 추가
  - 종료 시 `wal_checkpoint(TRUNCATE)` 수행
  - 런타임 상태 count 조회 API 추가
- `scripts/check_runtime_state.py`
  - 로컬/GitHub Actions용 DB 상태 점검 스크립트 추가
- `.github/workflows/report_scheduler.yml`
  - job-level `STOCK_DB_PATH` 통일
  - pre-run / post-run SQLite 상태 점검 단계 추가
  - 캐시 경로를 env 기준으로 일원화
- `src/apps/feedback_server.py`
  - 피드백 완료 페이지 HTML escape 적용
- `src/services/user_manager.py`
  - Notion DB pagination 반영
- 테스트 보강
  - DB env path / 손상 복구
  - feedback HTML escape
  - Notion pagination

### 이번 사이클 미포함 (후속 백로그 유지)

- Workflow `timeout-minutes` 재평가
- DB 접근 직렬화/락 정책 강화
- 운영 알림 텔레메트리 고도화
- 에러 알림 메시지 민감정보 최소화
