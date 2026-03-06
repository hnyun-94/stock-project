#!/bin/sh
# 커밋 크기 검증 스크립트.
# - 기본 정책: 커밋 1개당 (추가 + 삭제) <= 400 lines
# - pre-push 훅 또는 수동 검증에서 공통 사용

set -eu

MAX_LINES=400
RANGE=""

print_usage() {
  cat <<'EOF'
Usage:
  scripts/check_commit_size.sh [--range <git-range>] [--max-lines <N>]

Examples:
  scripts/check_commit_size.sh --range origin/master..HEAD --max-lines 400
  scripts/check_commit_size.sh --max-lines 300
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --range)
      RANGE="${2:-}"
      shift 2
      ;;
    --max-lines)
      MAX_LINES="${2:-}"
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "[check-commit-size] 알 수 없는 옵션: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

if ! echo "$MAX_LINES" | grep -Eq '^[0-9]+$'; then
  echo "[check-commit-size] --max-lines는 숫자여야 합니다: $MAX_LINES" >&2
  exit 2
fi

if [ -n "$RANGE" ]; then
  COMMITS=$(git rev-list "$RANGE")
else
  COMMITS=$(git rev-list -n 1 HEAD)
fi

if [ -z "$COMMITS" ]; then
  echo "[check-commit-size] 검사 대상 커밋이 없습니다."
  exit 0
fi

VIOLATION=0

for COMMIT in $COMMITS; do
  CHANGED_LINES=$(
    git show --numstat --format= "$COMMIT" \
    | awk '
      BEGIN { sum = 0 }
      {
        if ($1 ~ /^[0-9]+$/) sum += $1
        if ($2 ~ /^[0-9]+$/) sum += $2
      }
      END { print sum + 0 }
    '
  )

  if [ "$CHANGED_LINES" -gt "$MAX_LINES" ]; then
    echo "[check-commit-size] FAIL: $COMMIT -> ${CHANGED_LINES} lines (limit: $MAX_LINES)"
    VIOLATION=1
  else
    echo "[check-commit-size] PASS: $COMMIT -> ${CHANGED_LINES} lines"
  fi
done

if [ "$VIOLATION" -ne 0 ]; then
  echo "[check-commit-size] 커밋 크기 정책 위반이 있어 중단합니다." >&2
  exit 1
fi

echo "[check-commit-size] 모든 커밋이 ${MAX_LINES} lines 제한을 만족합니다."
