# 남은 계획 항목 일괄 완료 계획서

## 요청 배경

- 사용자는 "계획된 모든 개발사항을 진행"하라고 요청했다.
- 현재 `todo/todo.md` 기준 미완료 항목은 다음 4개다.
  - OpenDART 분류 지표를 사용자 리포트 해석 문구와 연결
  - FRED/SEC 지표를 시계열로 누적 저장하고 1D/7D 변화율 계산
  - 소스별 품질 점수 기반 리포트 신뢰도 배지 추가
  - 운영 대시보드 문서/점검표(Runbook) 표준화
- 추가로 P3 성격의 문서 동기화 검증을 CI에서 재현 가능하게 만드는 것이 남은 계획을 닫는 데 필요하다.

## 목표

- 외부 커넥터의 snapshot metric을 별도 시계열로 영속화한다.
- OpenDART/FRED/SEC 지표를 최근 1D/7D 변화율로 계산한다.
- 이 변화를 리포트의 `도메인 신호 해석` 섹션과 `신뢰도 배지`로 연결한다.
- 운영자가 바로 사용할 수 있는 Runbook 문서와 PR/CI 문서 동기화 검증을 추가한다.

## 역할별 검토

### PM

- 판단: 채택
- 근거: 남은 항목은 모두 "리포트를 얼마나 믿고 어떻게 운영할지"에 직접 연결된다. 사용자 가치와 운영 안정성이 한 번에 올라간다.

### TPM

- 판단: 채택
- 근거: `external_connector_runs`와 snapshot metric은 성격이 다르다. 시계열 지표용 저장 경로를 분리해야 이후 변화율과 신뢰도 계산이 일관된다.

### 기획자

- 판단: 채택
- 근거: 숫자 저장만 늘리면 다시 리포트가 난해해진다. `짧은 판단 + 근거 + 긍정/중립/부정 + 표` 구조로 연결해야 읽기성이 유지된다.

### 개발자

- 판단: 채택
- 근거: DB(metric points) -> builder(domain card/badge) -> formatter(render) -> workflow/doc sync 흐름으로 책임을 나누면 회귀 테스트도 명확하다.

### 신입개발자

- 판단: 채택
- 근거: 이번 작업은 테이블 1개, 카드 2개, 문서/CI 보강으로 분리할 수 있어 학습과 유지보수가 쉽다.

### 운영자

- 판단: 채택
- 근거: Runbook과 신뢰도 배지가 없으면 장애 감지 후에도 "이 리포트를 믿어도 되나?"를 다시 사람이 판단해야 한다.

## 검토 라운드

### 1차 검토

- 선택안 A: 남은 항목을 문서와 UI 수준으로만 마무리
- 선택안 B: metric 영속화 + 리포트 반영 + Runbook/CI까지 닫기
- 판단: B 채택
- 기각 이유:
  - A는 코드상 미완료 항목을 그대로 남겨 계획서만 정리하는 수준에 머문다.

### 2차 검토

- 검토 내용: 시계열 저장 방식
- 판단: `external_connector_runs`와 별도의 `connector_metric_points` 테이블을 추가
- 기각 이유:
  - 실행 이력과 snapshot metric을 같은 테이블에 섞으면 집계 의미가 달라져 1D/7D 변화율이 왜곡된다.

### 3차 검토

- 검토 내용: 문서 동기화 자동화 수준
- 판단:
  - Runbook 문서를 추가한다.
  - PR CI에서 `check_context_sync.sh`와 pytest를 실행한다.
  - `done/completed_work_report.md`를 최신 기준선으로 갱신한다.
- 기각 이유:
  - 로컬 훅만으로는 PR 단계에서 문서 불일치를 강제하기 어렵다.

## 구현 범위

1. DB / connector metric
- `connector_metric_points` 테이블 추가
- OpenDART/FRED/SEC snapshot metric 저장
- 1D/7D 변화율 계산 메서드 추가

2. 리포트 고도화
- OpenDART/FRED/SEC 해석 카드 추가
- 리포트 신뢰도 배지 추가
- badge/domain section formatter 반영

3. 운영 문서 / CI
- 운영 Runbook 문서 추가
- PR 품질 게이트 workflow 추가
- 완료 기준선 문서 갱신

## 커밋 예산

1. 계획서 + DB metric points + connector persistence + 테스트: 340 lines 이하
2. report_builder / formatter / 리포트 테스트: 360 lines 이하
3. workflow + runbook + 완료 문서/백로그 갱신: 220 lines 이하

## 완료 기준

- OpenDART/FRED/SEC metric이 DB에 누적되고 1D/7D 변화율이 계산된다.
- 리포트에 도메인 신호 해석 섹션과 신뢰도 배지가 추가된다.
- 운영 Runbook 문서가 저장소에 포함되고, PR CI에서 문서 동기화와 pytest가 검사된다.
- `todo/todo.md`의 남은 계획 항목이 모두 완료 상태가 된다.
- `uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q` 및 품질 게이트 통과

## 종합 판단

- 남아 있는 계획 항목은 서로 연결돼 있어 분리 구현보다 한 번에 닫는 편이 낫다.
- metric 영속화가 선행돼야 리포트 해석과 신뢰도 배지가 의미를 가진다.
- 따라서 이번 라운드에서 남은 계획 항목을 모두 구현하고, 문서/CI까지 닫는다.
