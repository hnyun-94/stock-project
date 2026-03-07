#!/bin/sh
# 문맥 동기화 및 런타임 smoke check 스크립트.
# - 코드/워크플로우/스킬 변경 시 logging/task/todo 동기화 여부를 경고합니다.
# - runtime-sensitive 변경 시 SQLite 상태 점검 스크립트를 실행합니다.

set -eu

RANGE=""
STRICT_DOC_SYNC="${STRICT_DOC_SYNC:-false}"

print_usage() {
  cat <<'EOF'
Usage:
  scripts/check_context_sync.sh --range <git-range>

Examples:
  scripts/check_context_sync.sh --range origin/master..HEAD
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --range)
      RANGE="${2:-}"
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "[context-sync] 알 수 없는 옵션: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$RANGE" ]; then
  echo "[context-sync] --range 옵션이 필요합니다." >&2
  exit 2
fi

CHANGED_FILES="$(git diff --name-only "$RANGE" || true)"

if [ -z "$CHANGED_FILES" ]; then
  echo "[context-sync] 변경 파일이 없어 점검을 건너뜁니다."
  exit 0
fi

has_changes_matching() {
  pattern="$1"
  printf '%s\n' "$CHANGED_FILES" | grep -Eq "$pattern"
}

CODE_LIKE_PATTERN='^(src/|tests/|\.github/workflows/|scripts/|AGENTS\.md|\.agents/skills/)'
DOC_LIKE_PATTERN='^(logging/|task/|todo/)'
RUNTIME_PATTERN='^(src/utils/database\.py|src/main\.py|src/services/user_manager\.py|src/services/market_external_connectors\.py|\.github/workflows/report_scheduler\.yml|scripts/check_runtime_state\.py)'

if has_changes_matching "$RUNTIME_PATTERN"; then
  echo "[context-sync] 런타임 상태 smoke check 실행"
  mkdir -p .tmp/prepush
  if command -v uv >/dev/null 2>&1; then
    UV_CACHE_DIR=.tmp/.uv-cache uv run python scripts/check_runtime_state.py --db-path .tmp/prepush/runtime.db --label pre-push
  else
    python scripts/check_runtime_state.py --db-path .tmp/prepush/runtime.db --label pre-push
  fi
fi

if has_changes_matching "$CODE_LIKE_PATTERN" && ! has_changes_matching "$DOC_LIKE_PATTERN"; then
  echo "[context-sync] WARNING: 코드/워크플로우/스킬 변경이 있으나 logging/, task/, todo/ 갱신이 감지되지 않았습니다." >&2
  echo "[context-sync] WARNING: 반복 요구는 문서/로그로 승격해 다음 세션에서 재사용 가능하게 유지하세요." >&2
  if [ "$STRICT_DOC_SYNC" = "true" ]; then
    echo "[context-sync] STRICT_DOC_SYNC=true 이므로 push를 중단합니다." >&2
    exit 1
  fi
fi

echo "[context-sync] 문맥 동기화 점검 완료"
