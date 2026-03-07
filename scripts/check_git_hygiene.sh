#!/bin/sh
# Git 추적 대상 위생 점검 스크립트.
# - 로컬 전용 산출물이 추적 중인지 확인합니다.
# - 절대 경로, 실제 이메일 같은 민감 패턴이 추적 파일에 없는지 검사합니다.

set -eu

FORBIDDEN_PATH_PATTERN='^(\.env$|\.env\..+|\.local/|logging/|error[Cc]ase/|data/|\.tmp/|.+\.db$|.+\.db-shm$|.+\.db-wal$|.+\.log$|.+/user_feedback\.json$|.+/ai_predictions\.json$)'
ABSOLUTE_PATH_PATTERN='(/Users/|/home/[^/]+/)'
EMAIL_PATTERN='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
ALLOWED_EMAIL_PATTERN='@(example\.com|domain\.com)\b'

tracked_files="$(git ls-files)"

if [ -z "$tracked_files" ]; then
  echo "[git-hygiene] 추적 파일이 없어 점검을 건너뜁니다."
  exit 0
fi

forbidden_paths="$(
  printf '%s\n' "$tracked_files" \
    | grep -E "$FORBIDDEN_PATH_PATTERN" \
    | grep -Ev '^\.env\.template$' \
    || true
)"
if [ -n "$forbidden_paths" ]; then
  echo "[git-hygiene] ERROR: 로컬 전용 또는 민감 산출물이 Git 추적 대상에 포함되어 있습니다." >&2
  printf '%s\n' "$forbidden_paths" >&2
  exit 1
fi

absolute_path_hits="$(git ls-files -z | xargs -0 rg -n "$ABSOLUTE_PATH_PATTERN" || true)"
if [ -n "$absolute_path_hits" ]; then
  echo "[git-hygiene] ERROR: 추적 파일에서 로컬 절대 경로가 발견되었습니다." >&2
  printf '%s\n' "$absolute_path_hits" >&2
  exit 1
fi

email_hits="$(
  git ls-files -z \
    | xargs -0 rg -n "$EMAIL_PATTERN" \
    | grep -Ev '^(\.env\.template|tests/)' \
    | grep -Ev "$ALLOWED_EMAIL_PATTERN" \
    || true
)"
if [ -n "$email_hits" ]; then
  echo "[git-hygiene] ERROR: 추적 파일에서 실제 이메일로 보이는 패턴이 발견되었습니다." >&2
  printf '%s\n' "$email_hits" >&2
  exit 1
fi

echo "[git-hygiene] 점검 완료"
