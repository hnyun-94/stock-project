---
name: runtime-architecture-review
description: "Use when work touches GitHub Actions, SQLite, caches, env-driven state, workflow persistence, or runtime recovery. Verify the architecture fits CI runners and add health checks."
---

# Runtime Architecture Review Skill

이 스킬은 런타임 상태 저장/복구가 얽힌 작업을 위한 표준 점검 절차입니다.
특히 GitHub Actions, SQLite, cache, workflow, env 기반 경로가 바뀌는 경우 사용합니다.

## Usage Trigger

다음 상황에서 사용합니다.

- GitHub Actions / workflow 변경
- SQLite / DB path / cache / artifact / state persistence 변경
- "CI에서도 의도대로 동작하는지 확인"
- "runtime architecture", "운영 상태", "복구", "health-check" 요청

## Workflow

1. 상태 저장 주체를 식별합니다.
   - SQLite
   - cache/artifact
   - env path
   - in-memory cache / process-local state
2. "설정이 코드에 실제 연결되는지"를 먼저 확인합니다.
   - 예: `STOCK_DB_PATH`가 실제 DB 초기화에 반영되는지
3. 복구/안전 경로를 확인합니다.
   - 손상 파일 처리
   - missing cache fallback
   - clean shutdown / checkpoint
4. workflow에 health-check를 추가합니다.
   - pre-run / post-run 점검
   - 런타임 상태를 stdout/log로 남김
5. 테스트를 보강합니다.
   - env path
   - pagination / recovery / fallback
   - security regressions if exposed surface changed
6. 작업 로그와 계획 문서를 갱신합니다.

## Preferred Commands

```bash
uv run python scripts/check_runtime_state.py --db-path .tmp/runtime/stock_project.db --label local-check
scripts/check_context_sync.sh --range origin/master..HEAD
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
```

## Guardrails

- "Actions에서 env를 넣었으니 된다"라고 가정하지 않습니다. 코드 연결 여부를 확인해야 합니다.
- 상태 저장 아키텍처를 바꿀 때는 workflow, code, test를 함께 수정합니다.
- 복구 불가능한 손상/불일치가 감지되면 조용히 무시하지 말고 로그와 계획 문서에 남깁니다.
