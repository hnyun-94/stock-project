# 역할분할 우선순위 검증 및 병렬 실행 계획서

작성일: 2026-03-07

---

## 1) 목적

- 요청사항을 역할별로 검증하고 우선순위를 높은 순으로 정렬합니다.
- 누락/성능 리스크를 먼저 제거한 뒤 기능 구현을 시작합니다.
- 작업은 기능 단위로 쪼개 Git/PR에서 독립적으로 관리합니다.
- 병렬 가능한 스트림을 분리해 동시 진행합니다.

---

## 2) 역할별 검증 결과

### PM 관점

- Findings:
  - 신규로 만든 정책/통계 모듈이 메인 파이프라인에 연결되지 않아 사용자 가치가 아직 0입니다.
- Severity:
  - `major`
- Action:
  - 런타임 거버넌스 체크와 통계 섹션 생성을 우선 연결합니다.

### TPM 관점

- Findings:
  - 무료 한도/약관 위반 방지 로직이 실행 시점에 강제되지 않습니다.
  - 실행 주기 대비 호출 버짓이 자동 점검되지 않습니다.
- Severity:
  - `critical`
- Action:
  - 파이프라인 시작 시 소스 정책/호출량 점검을 수행하고 strict 모드를 제공합니다.

### 기획자 관점

- Findings:
  - "정량 통계 스냅샷"이 설계되어 있으나 리포트에 아직 노출되지 않습니다.
- Severity:
  - `major`
- Action:
  - 리포트 본문에 통계 섹션을 삽입하고 사용자 해석 문구를 보강합니다.

### 개발자 관점

- Findings:
  - 기능 경계가 명확하나 통합 지점(main.py)이 없어 테스트 효용이 제한됩니다.
- Severity:
  - `major`
- Action:
  - 기능단위 통합 순서: `governance` → `summary integration` → `connector`.

### 신입개발자 관점

- Findings:
  - 어떤 기능이 어떤 PR로 나가는지 기준이 필요합니다.
- Severity:
  - `minor`
- Action:
  - 기능단위 PR 분할 표준과 커밋 크기 기준(<=400 lines)을 작업계획에 고정합니다.

### 운영자 관점

- Findings:
  - 정책 위반 소스(예: 비상업 제한 소스) 오사용을 런타임에서 탐지하지 못합니다.
- Severity:
  - `critical`
- Action:
  - 정책 위반/한도 초과를 로그 경고 또는 strict 차단으로 처리합니다.

---

## 3) 우선순위 (High -> Low)

1. **P0 - 런타임 소스 거버넌스 체크 통합** (`critical`)
2. **P1 - 리포트 정량 통계 섹션 통합** (`major`)
3. **P2 - 실제 소스 커넥터 확장(data.go/OpenDART/SEC/FRED)** (`major`)
4. **P3 - 운영 대시보드/모니터링 고도화** (`minor`)

---

## 4) 병렬 작업 스트림

- **Stream A (TPM/운영, P0)**: 소스 정책/무료한도 런타임 검증, strict 모드, 로그 표준화
- **Stream B (기획/개발, P1)**: 통계 스냅샷 리포트 통합, 사용자 가독성 개선
- **Stream C (PM/신입, P2 준비)**: 커넥터 우선순위 백로그 + API 키/약관 체크리스트

병렬 규칙:
- A/B/C는 서로 다른 파일 경계를 유지합니다.
- 공통 파일(`src/main.py`) 충돌을 피하기 위해 병합 순서는 `A -> B -> C`로 둡니다.

---

## 5) 기능단위 Git 관리 원칙

- 커밋은 기능 1개만 포함합니다.
- 커밋당 변경량(추가+삭제)은 400 lines 이하를 유지합니다.
- PR은 하나의 결과물만 포함합니다.
  - 예: `feat: add runtime source policy guard`
  - 예: `feat: add market snapshot section to report`

---

## 6) 기능단위 PR 분할(실행 계획)

### PR-A (P0, Stream A)

- Scope:
  - `src/services/market_source_governance.py` 런타임 평가 헬퍼 추가
  - `src/main.py` 시작 단계에 거버넌스 체크 연결
  - `tests/services/test_market_source_governance.py` 테스트 확장
- Merge 조건:
  - quality gate 통과
  - 다중 관점 리뷰에서 `critical` 없음

### PR-B (P1, Stream B)

- Scope:
  - `src/services/market_signal_summary.py` + `src/main.py` + `src/utils/report_formatter.py` 통계 섹션 통합
  - 통계 노출 테스트 추가
- Merge 조건:
  - quality gate 통과
  - 사용자 리포트 렌더링 회귀 없음

### PR-C (P2, Stream C)

- Scope:
  - data.go/OpenDART/SEC/FRED 커넥터를 단계적으로 연결
  - 호출 버짓/캐시 정책 실적 로그 추가
- Merge 조건:
  - 각 소스별 단위 테스트/모의 테스트 통과
  - 약관/한도 체크리스트 완료
 - 진행 메모:
   - 1차 구현으로 `market_external_connectors.py`에서 4개 소스 최소 지표(count) 수집 경로를 통합함.

---

## 7) 착수 상태

- [x] 역할분할 검증 완료
- [x] 우선순위 정렬 완료
- [x] 병렬 스트림/기능단위 분할 완료
- [x] PR-A 구현 및 검증 완료
- [x] PR-B 구현 및 검증 완료
- [x] PR-C 1차(커넥터 레이어 + main 연동) 구현 및 검증 완료
- [x] PR-C 2차(커넥터 텔레메트리 + OpenDART 세부 카테고리) 구현 및 검증 완료
