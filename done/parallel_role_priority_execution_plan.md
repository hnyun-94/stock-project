# 역할분할 우선순위 검증 및 병렬 실행 계획서

작성일: 2026-03-07

---

## 1) 목적

- 요청사항을 역할별로 검증하고 우선순위를 높은 순으로 정렬합니다.
- 누락/성능 리스크를 먼저 제거한 뒤 기능 구현을 시작합니다.
- 작업은 기능 단위로 쪼개 Git/PR에서 독립적으로 관리합니다.
- 병렬 가능한 스트림을 분리해 동시 진행합니다.

---

## 2) 역할별 최신 상태 (동기화)

### PM 관점

- 상태:
  - 소스 정책 가드, 정량 스냅샷, 외부 커넥터(텔레메트리 포함)가 리포트 경로에 연결되어 사용자 가치가 전달되는 상태입니다.
- 잔여 과제:
  - 운영 지표(성공률/지연)의 사용자 노출 레벨 정의

### TPM 관점

- 상태:
  - 런타임 소스 거버넌스(strict 옵션), 커넥터 실패 격리, 커밋/PR 품질 게이트가 적용되었습니다.
- 잔여 과제:
  - 커넥터 실패율/지연 임계치 기반 자동 알림 정책 수립

### 기획자 관점

- 상태:
  - 정량 통계 스냅샷 + 외부 소스 텔레메트리 섹션이 리포트에 포함됩니다.
- 잔여 과제:
  - OpenDART 카테고리 지표(실적/자금조달/지분) 해석 문구 고도화

### 개발자 관점

- 상태:
  - 모듈 경계(`market_source_governance`, `market_signal_summary`, `market_external_connectors`)와 테스트 경계가 정립되었습니다.
- 잔여 과제:
  - 커넥터 지표의 시계열 집계 및 대시보드 연계 API 확장

### 신입개발자 관점

- 상태:
  - 기능 단위 PR 분할, 커밋 400줄 정책, 다중 역할 리뷰 템플릿이 정착되었습니다.
- 잔여 과제:
  - 문서-코드 자동 동기화 체크(정적 점검) 추가

### 운영자 관점

- 상태:
  - 외부 소스 실행 결과가 SQLite(`external_connector_runs`)에 저장되어 추적 가능합니다.
- 잔여 과제:
  - 일자별 성공률/지연 리포트 자동화 및 경보 채널 연동

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
- [x] PR-C 3차(커넥터 텔레메트리 DB 영속화 + 성공률 조회 API) 구현 및 검증 완료
