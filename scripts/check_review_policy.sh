#!/bin/sh
# 다중 관점 리뷰 및 근거 문서화 정책 점검 스크립트.
# - 구현성 변경이 있으면 task/ 또는 done/ 문서에 역할 리뷰와 판단 근거가 함께 기록됐는지 확인합니다.

set -eu

RANGE=""

print_usage() {
  cat <<'EOF'
Usage:
  scripts/check_review_policy.sh --range <git-range>

Examples:
  scripts/check_review_policy.sh --range origin/master..HEAD
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
      echo "[review-policy] 알 수 없는 옵션: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$RANGE" ]; then
  echo "[review-policy] --range 옵션이 필요합니다." >&2
  exit 2
fi

CHANGED_FILES="$(git diff --name-only "$RANGE" || true)"

if [ -z "$CHANGED_FILES" ]; then
  CHANGED_FILES="$(
    {
      git diff --name-only || true
      git diff --cached --name-only || true
      git ls-files --others --exclude-standard || true
    } | awk 'NF {print}' | sort -u
  )"
fi

if [ -z "$CHANGED_FILES" ]; then
  echo "[review-policy] 변경 파일이 없어 점검을 건너뜁니다."
  exit 0
fi

has_changes_matching() {
  pattern="$1"
  printf '%s\n' "$CHANGED_FILES" | grep -Eq "$pattern"
}

has_heading() {
  file="$1"
  heading="$2"
  grep -Eq "^###[[:space:]]+$heading([[:space:]]|$)" "$file"
}

doc_satisfies_policy() {
  file="$1"
  [ -f "$file" ] || return 1

  has_heading "$file" 'PM' &&
    has_heading "$file" 'TPM' &&
    has_heading "$file" '기획자' &&
    has_heading "$file" '시니어 개발자' &&
    has_heading "$file" '개발자' &&
    has_heading "$file" '품질 담당자' &&
  has_heading "$file" '신입개발자' &&
  has_heading "$file" '운영자' &&
  has_heading "$file" '주식 전문가' &&
  has_heading "$file" 'UI/UX 전문가' &&
  has_heading "$file" '퍼블리셔 전문가' &&
  grep -Eq '근거|이유' "$file" &&
  grep -Eq '종합 판단|최종 판단|판단' "$file"
}

IMPLEMENTATION_PATTERN='^(src/|tests/|\.github/workflows/|scripts/|\.agents/skills/)'
REVIEW_DOC_PATTERN='^(task/|done/)'

if ! has_changes_matching "$IMPLEMENTATION_PATTERN"; then
  echo "[review-policy] 구현성 변경이 없어 점검을 건너뜁니다."
  exit 0
fi

REVIEW_DOCS="$(printf '%s\n' "$CHANGED_FILES" | grep -E "$REVIEW_DOC_PATTERN" || true)"

if [ -z "$REVIEW_DOCS" ]; then
  echo "[review-policy] ERROR: 구현성 변경이 있으나 task/ 또는 done/ 문서 갱신이 없습니다." >&2
  echo "[review-policy] ERROR: 역할별 검토와 근거, 판단을 담은 계획서/실행 문서를 추가하세요." >&2
  exit 1
fi

for file in $REVIEW_DOCS; do
  if doc_satisfies_policy "$file"; then
    echo "[review-policy] 점검 완료"
    exit 0
  fi
done

echo "[review-policy] ERROR: 변경된 task/ 또는 done/ 문서에서 역할 리뷰/근거/판단 구조를 찾지 못했습니다." >&2
echo "[review-policy] ERROR: 'PM, TPM, 기획자, 시니어 개발자, 개발자, 품질 담당자, 신입개발자, 운영자, 주식 전문가, UI/UX 전문가, 퍼블리셔 전문가'와 '근거 또는 이유', '종합 판단'을 포함하세요." >&2
exit 1
