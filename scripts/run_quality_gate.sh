#!/bin/sh
# 로컬 품질 게이트 번들.
# - py_compile, commit size, context sync, 표준 pytest 게이트를 한 번에 실행합니다.

set -eu

RANGE=""
MAX_COMMIT_LINES="${MAX_COMMIT_LINES:-400}"
RUN_PY_COMPILE="true"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_quality_gate.sh [--range <git-range>] [--skip-py-compile]

Options:
  --range <git-range>    예: origin/master..HEAD
  --skip-py-compile      변경된 Python 파일 문법 검사를 건너뜁니다.
EOF
}

infer_default_range() {
  if git rev-parse --verify origin/master >/dev/null 2>&1; then
    echo "origin/master..HEAD"
    return
  fi
  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    echo "origin/main..HEAD"
    return
  fi
  echo "HEAD"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --range)
      RANGE="${2:-}"
      shift 2
      ;;
    --skip-py-compile)
      RUN_PY_COMPILE="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[quality-gate] 알 수 없는 옵션: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$RANGE" ]; then
  RANGE="$(infer_default_range)"
fi

echo "[quality-gate] range=$RANGE"

if [ "$RUN_PY_COMPILE" = "true" ]; then
  CHANGED_PY_FILES="$(git diff --name-only "$RANGE" -- '*.py' || true)"
  if [ -n "$CHANGED_PY_FILES" ]; then
    echo "[quality-gate] py_compile"
    # shellcheck disable=SC2086
    python -m py_compile $CHANGED_PY_FILES
  else
    echo "[quality-gate] py_compile 대상 변경 Python 파일이 없습니다."
  fi
fi

echo "[quality-gate] commit size"
scripts/check_commit_size.sh --range "$RANGE" --max-lines "$MAX_COMMIT_LINES"

echo "[quality-gate] git hygiene"
sh scripts/check_git_hygiene.sh

echo "[quality-gate] changed python lint"
sh scripts/check_changed_python_lint.sh --range "$RANGE"

echo "[quality-gate] context sync"
sh scripts/check_context_sync.sh --range "$RANGE"

echo "[quality-gate] review policy"
sh scripts/check_review_policy.sh --range "$RANGE"

echo "[quality-gate] pytest"
if command -v uv >/dev/null 2>&1; then
  UV_CACHE_DIR="${UV_CACHE_DIR:-.tmp/.uv-cache}" \
    uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
else
  python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
fi

echo "[quality-gate] 완료"
