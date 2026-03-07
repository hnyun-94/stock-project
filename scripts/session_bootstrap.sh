#!/bin/sh
# 안전한 세션 초기화 번들.
# - read-only 상태 점검을 한 번에 수행합니다.
# - 기본값은 기준선 테스트 포함이며, 빠른 확인만 필요하면 --no-tests를 사용합니다.

set -eu

RUN_TESTS="true"

usage() {
  cat <<'EOF'
Usage:
  scripts/session_bootstrap.sh [--no-tests]

Options:
  --no-tests   문서/상태 확인만 수행하고 기준선 테스트는 건너뜁니다.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-tests)
      RUN_TESTS="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[session-bootstrap] 알 수 없는 옵션: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

echo "[session-bootstrap] todo/todo.md"
cat todo/todo.md

LATEST_LOG="$(ls -t logging/ 2>/dev/null | head -1 || true)"
if [ -n "$LATEST_LOG" ]; then
  echo "[session-bootstrap] logging/$LATEST_LOG"
  cat "logging/$LATEST_LOG"
else
  echo "[session-bootstrap] logging 디렉토리에 로그가 없습니다."
fi

echo "[session-bootstrap] git status --short --branch"
git status --short --branch

echo "[session-bootstrap] current branch"
git branch --show-current

echo "[session-bootstrap] hooks path"
git config --get core.hooksPath || true

if [ -f .codex/config.toml ]; then
  echo "[session-bootstrap] .codex/config.toml"
  sed -n '1,120p' .codex/config.toml
fi

if [ "$RUN_TESTS" = "true" ]; then
  echo "[session-bootstrap] baseline tests"
  if command -v uv >/dev/null 2>&1; then
    UV_CACHE_DIR="${UV_CACHE_DIR:-.tmp/.uv-cache}" \
      uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
  else
    python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
  fi
fi

echo "[session-bootstrap] 완료"
