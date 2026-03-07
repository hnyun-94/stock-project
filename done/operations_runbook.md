# Operations Runbook

## 목적

- 외부 커넥터, 리포트 신뢰도, 발송 파이프라인 이상 징후를 운영자가 빠르게 판단하고 대응하기 위한 표준 절차입니다.
- 저장소 안에서 바로 재현 가능한 점검 명령과 우선순위를 제공합니다.

## 주요 운영 신호

### 1. 리포트 신뢰도 배지

- `높음`: 최근 7일 평균 성공률과 최신성이 안정적입니다.
- `보통`: 일부 source 경고가 있거나 최신성/성공률이 중간 수준입니다.
- `주의`: source 품질 저하, 최신성 저하, 누적 메트릭 부족이 겹친 상태입니다.

### 2. 데이터 신뢰도 섹션

- 최근 7일 source별 성공률, 평균 지연, 최근 오류 사유를 보여줍니다.
- `주의` 판정 source가 반복되면 리포트 해석을 보수적으로 봐야 합니다.

### 3. 외부 지표 해석 섹션

- `OpenDART 공시 흐름`
  - 실적/영업 증가: 실적 시즌 기대 강화
  - 자금조달 증가: 희석/자금 압박 우려 점검
  - 지분 변화 증가: 지배구조/수급 변수 점검
- `FRED·SEC 시계열`
  - FRED 금리 상승: 성장주 밸류에이션 부담 확대 가능
  - FRED 금리 하락: 성장주 부담 완화 가능
  - SEC 샘플 이상치: 커버리지/데이터 이상 여부 확인

## 일상 점검 루틴

1. 최신 리포트의 `리포트 신뢰도 배지`와 `데이터 신뢰도` 섹션을 먼저 확인합니다.
2. 텔레그램 운영 알림이 온 경우 source, 1H/24H 실패율, 최근 상세를 확인합니다.
3. 아래 명령으로 로컬 상태를 재현합니다.

```bash
scripts/session_bootstrap.sh --no-tests
uv run python scripts/check_runtime_state.py --db-path data/stock_project.db --label manual-check
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
```

## 장애 대응 체크리스트

### A. 커넥터 실패율/지연 경보

1. `src/services/connector_alerts.py` 경고 메시지에서 source와 trigger reason을 확인합니다.
2. `data/stock_project.db`의 `external_connector_runs`, `connector_metric_points` 누적 여부를 점검합니다.
3. source별 최근 오류 사유를 확인합니다.
4. 일시 장애면 다음 배치 1회 더 관찰하고, 반복이면 source 설정/API 키/요청 정책을 점검합니다.

### B. 리포트 신뢰도 배지 하락

1. 최근 7일 데이터 신뢰도 표에서 `주의` source가 몇 개인지 확인합니다.
2. `connector_metric_points` 최신 날짜가 늦지 않았는지 확인합니다.
3. OpenDART/FRED/SEC 중 어느 지표가 비어 있는지 확인합니다.

### C. 메인 파이프라인 실패

1. GitHub Actions `report_scheduler.yml` 로그를 확인합니다.
2. `scripts/check_runtime_state.py` 결과에서 DB row count와 손상 여부를 확인합니다.
3. Gemini quota 오류면 fallback 경로와 quota block 상태를 점검합니다.

## 우선 점검 명령

```bash
uv run python scripts/check_runtime_state.py --db-path data/stock_project.db --label incident
sh scripts/run_quality_gate.sh --range origin/master..HEAD
uv run python -m src.main
```

## 운영 판단 기준

- `높음` 배지 + 커넥터 경보 없음:
  - 정상 운영
- `보통` 배지 + 특정 source 주의:
  - 리포트는 발송하되 해석을 보수적으로 본다
- `주의` 배지 또는 반복 경보:
  - source 장애/누락 여부를 먼저 해소하고 리포트 해석 신뢰도를 낮게 본다

## 관련 파일

- `src/services/connector_alerts.py`
- `src/services/market_external_connectors.py`
- `src/services/report_builder.py`
- `src/utils/database.py`
- `.github/workflows/report_scheduler.yml`
