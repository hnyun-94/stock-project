---
name: e2e-test-suite
description: "Run the project quality gate tests (services + e2e dryrun) before commit/push to prevent regressions."
---

# E2E Test Suite Skill

이 스킬은 커밋/푸시 전 표준 품질 게이트를 강제해 회귀를 방지합니다.
또한 완료 단계(`commit -> push -> PR -> review -> merge`)에서 테스트 누락을 방지하는 게이트 역할을 합니다.

## Usage Trigger

다음 상황에서 반드시 사용합니다.

- 커밋 직전
- push 직전
- `models.py`, `main.py`, `ai_summarizer.py`, `database.py` 변경 직후

## Instructions

1. 표준 품질 게이트를 한 번에 실행합니다.
2. 실패 시 커밋/푸시를 중단하고 문제를 수정합니다.
3. 장애 원인/해결 절차는 `done/e2e_incident_response_plan.md`를 기준으로 따릅니다.
4. 실행 결과와 누락점은 `done/e2e_incident_execution_report.md`에 반영합니다.
5. 필요 시 `errorCase/`, `todo/todo.md`, `logging/YYYY-MM-DD.md`를 업데이트합니다.
6. PR 전에는 `scripts/check_commit_size.sh --range origin/master..HEAD --max-lines 400`도 함께 실행합니다.
7. 테스트 실패 상태에서는 커밋/푸시/PR/머지를 진행하지 않습니다.

## Essential Command

```bash
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
```

## Hook Alignment

- `.githooks/pre-push`에서도 동일 명령을 실행합니다.
- 로컬에서 빠르게 확인한 뒤 push하여 중복 실패를 줄입니다.
