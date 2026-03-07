#!/bin/sh
# 변경된 Python 파일에 한해 기본 Ruff 린트(F/I)를 실행합니다.
# - 레거시 전체 도입 대신, 새 변경분부터 import hygiene와 기본 정적 오류를 누적 방지합니다.

set -eu

RANGE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/check_changed_python_lint.sh [--range <git-range>]

Options:
  --range <git-range>    예: origin/master..HEAD
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[changed-python-lint] 알 수 없는 옵션: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$RANGE" ]; then
  RANGE="$(infer_default_range)"
fi

CHANGED_PY_FILES="$(
  {
    git diff --name-only --diff-filter=ACMR "$RANGE" -- '*.py' || true
    git diff --cached --name-only --diff-filter=ACMR -- '*.py' || true
    git diff --name-only --diff-filter=ACMR -- '*.py' || true
  } | sed '/^$/d' | sort -u
)"
if [ -z "$CHANGED_PY_FILES" ]; then
  echo "[changed-python-lint] 대상 변경 Python 파일이 없습니다."
  exit 0
fi

echo "[changed-python-lint] range=$RANGE"
echo "[changed-python-lint] files:"
printf '%s\n' "$CHANGED_PY_FILES"

if command -v uv >/dev/null 2>&1; then
  # shellcheck disable=SC2086
  UV_CACHE_DIR="${UV_CACHE_DIR:-.tmp/.uv-cache}" \
    uv run ruff check --select F,I $CHANGED_PY_FILES
  exit 0
fi

if command -v ruff >/dev/null 2>&1; then
  # shellcheck disable=SC2086
  ruff check --select F,I $CHANGED_PY_FILES
  exit 0
fi

echo "[changed-python-lint] ruff 실행 환경이 없습니다." >&2
exit 1
