## 프로젝트 전반 리뷰 및 하드닝 계획서

작성일: 2026-03-07
대상 범위: 최적화, 보안, 품질, 기획, 테스트, 운영 안정성

### 1. 검토 라운드 요약

#### 라운드 1. 기준선 및 운영 경로 확인
- 근거: `master` clean, `136 passed`, 현재 계획 백로그 완료 상태 확인.
- 판단: 신규 기능 확장보다 운영 경로의 잔여 리스크를 줄이는 정리 작업이 우선입니다.

#### 라운드 2. 정적 스캔 및 품질 게이트 점검
- 근거:
  - `src/services/notifier/telegram.py`가 `requests.post(..., timeout=...)` 없이 동작.
  - `src/services/market_external_connectors.py`의 `SEC_USER_AGENT` 기본값이 `support@example.com`.
  - `uv run ruff check src tests` 결과 레거시 이슈가 1,100건 이상으로 전체 도입은 비현실적.
- 판단:
  - 전체 린트 게이트 즉시 도입은 기각합니다.
  - 대신 “변경된 Python 파일만” 기본 린트(F/I)를 강제하는 점진 도입이 타당합니다.

#### 라운드 3. 역할별 리뷰

### PM
- 문제:
  - 운영 알림 채널이 네트워크 hang 또는 과도한 메시지 길이로 실패할 수 있습니다.
  - SEC 커넥터가 실제 연락처가 아닌 예시 User-Agent로 호출될 수 있습니다.
- 판단:
  - 사용자가 받는 신뢰도와 운영 판단 품질에 직접 영향이 있으므로 즉시 수정합니다.

### TPM
- 문제:
  - 외부 의존성 호출 방어가 일부 모듈에서 일관되지 않습니다.
  - 전체 린트는 어려우나 변경 파일 최소 린트는 자동화 가능성이 높습니다.
- 판단:
  - timeout, chunking, placeholder 차단, changed-file lint를 이번 라운드 범위로 채택합니다.

### 기획자
- 문제:
  - 템플릿 환경변수에 실제 운영 시 그대로 쓰면 안 되는 예시값이 남아 있습니다.
- 판단:
  - `.env.template`, `README.md`에서 “필수 직접 입력” 성격을 명확히 드러내야 합니다.

### 개발자
- 문제:
  - 텔레그램 메시지 길이 제한 미고려.
  - HTTP 예외 처리가 상태 코드 중심으로만 되어 있어 요청 예외와 timeout 원인 분리가 약함.
- 판단:
  - `TelegramSender`에 timeout, chunking, raise-for-status 기반 실패 처리를 넣습니다.

### 신입개발자
- 문제:
  - 왜 SEC User-Agent가 필수인지 코드만 보고는 이해하기 어렵습니다.
  - 전체 Ruff 실패가 너무 커서 어디부터 정리해야 하는지 감이 없습니다.
- 판단:
  - 코드 주석/문서에 정책 이유를 남기고, changed-file lint 방식으로 진입 장벽을 낮춥니다.

### 운영자
- 문제:
  - 관리자 텔레그램 알림이 실패하면 장애를 제때 못 볼 수 있습니다.
  - 예시 User-Agent는 대외 호출 정책 위반 소지가 있습니다.
- 판단:
  - 운영 알림의 성공 가능성을 높이고, 정책 위반 가능성은 선제 차단합니다.

### 2. 이번 라운드 실행 항목

#### P0
- `TelegramSender`에 요청 timeout, 메시지 분할(chunking), 예외 로깅 강화 추가
- SEC 커넥터에서 placeholder/missing `SEC_USER_AGENT` 차단
- 관련 회귀 테스트 추가

#### P1
- changed-file 대상 Ruff(F/I) 검사 스크립트 추가
- `run_quality_gate.sh`, `pre-push`, PR workflow에 연결

#### P2
- `.env.template`, `README.md`, `scripts/README.md`, `AGENTS.md`에 새 규칙 반영

### 3. 기각한 대안
- 대안: 전체 `ruff check src tests`를 즉시 품질 게이트에 추가
- 기각 이유: 레거시 이슈 1,100건 이상으로 현재 생산성을 크게 훼손합니다.

- 대안: SEC User-Agent에 새 기본값을 유지
- 기각 이유: 예시 연락처 또는 가짜 연락처가 운영에 그대로 쓰일 가능성이 높습니다.

### 3-1. 커밋 예산
- Commit A: 운영 하드닝 + 회귀 테스트, 목표 360줄 이하
- Commit B: 품질 게이트/문서/계획 동기화, 목표 260줄 이하
- 판단 이유: 초기에는 한 커밋도 가능하다고 봤지만, 실제 diff 집계에서 400줄 근접 드리프트가 보여 runtime 변경과 process/doc 변경을 분리하는 편이 안전합니다.

### 4. 완료 기준
- 텔레그램 발송 경로가 timeout/길이 제한을 처리한다.
- SEC 커넥터가 placeholder User-Agent로 호출되지 않는다.
- 품질 게이트에 changed-file lint가 포함된다.
- 관련 단위 테스트와 문서가 함께 갱신된다.

### 근거 또는 이유
- `requests.post(..., timeout=...)` 누락은 운영 알림 경로에서 hang 리스크를 키웁니다.
- Telegram은 메시지 길이 제한이 있어 긴 알림을 그대로 보내면 실패 가능성이 있습니다.
- SEC는 식별 가능한 User-Agent 정책이 강해 placeholder 기본값 사용이 적절하지 않습니다.
- 전체 Ruff 도입은 현재 레거시 부채가 커서, 변경 파일에만 점진 도입하는 편이 비용 대비 효과가 높습니다.

### 종합 판단
- 이번 라운드는 제품 기능 확장보다 운영 방어와 품질 프로세스 강화가 우선입니다.
- 따라서 `TelegramSender` 하드닝, SEC placeholder 차단, changed-file lint, 회귀 테스트 보강을 묶어서 즉시 반영합니다.

### PR 리뷰 후 추가 논의
- 추가 발견:
  - GitHub Actions PR 게이트가 synthetic merge commit을 checkout 하면서 커밋 크기 정책을 합산 오판할 수 있었습니다.
- 근거:
  - PR #45의 첫 quality-gate 실패 로그에서 merge ref 단일 커밋 541줄로 계산됐지만, 실제 PR 브랜치 커밋은 293줄 + 248줄이었습니다.
- 후속 판단:
  - `pr_quality_gate.yml`은 실제 PR head SHA를 checkout 하도록 수정합니다.
