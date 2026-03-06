---
name: pr-creator
description: "Create and merge PRs safely with gh CLI using --body-file, after passing the project quality gate tests."
---

# PR Creator Skill

이 스킬은 `gh` CLI 사용 시 터미널 hang을 피하면서 안전하게 PR을 생성/머지합니다.
또한 `pr-governance` 정책(커밋 400줄 제한, 다중 관점 리뷰)을 PR 본문에 반영합니다.
또한 코드 변경 작업의 기본 완료 조건을 `commit -> push -> PR -> review -> merge`로 강제합니다.

## Usage Trigger

기능/버그 수정을 마치고 PR 생성 또는 머지가 필요할 때 사용합니다.

## Instructions

1. feature 브랜치(`feat/*`, `fix/*`, `refactor/*`, `test/*`)인지 확인합니다.
2. 커밋당 변경량이 400줄 이하인지 검증합니다.
3. 품질 게이트 테스트를 통과시킵니다.
4. 커밋을 생성하고 원격 브랜치로 push합니다.
5. PR 본문을 `.tmp/pr_body.md`로 작성합니다.
   - PM/TPM/기획자/개발자/신입개발자/운영자 리뷰 섹션 필수
   - `critical`/`major`/`minor` 심각도와 조치 내용 포함
6. `gh pr create --body-file`로 PR을 생성합니다.
7. 머지 전 의사결정:
   - `critical` 발견 시: 같은 PR에서 수정 후 재검증
   - `major/minor`만 존재 시: 후속 PR 범위를 본문에 명시
8. 사용자가 머지 보류를 명시하지 않았다면 `gh pr merge --squash --delete-branch`를 실행합니다.
9. `.tmp/pr_body.md`를 삭제합니다.

## Example Execution Script (Internal Use)

```bash
# 1) Quality gate
scripts/check_commit_size.sh --range origin/master..HEAD --max-lines 400
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q

# 2) Commit + push
git add <FILES>
git commit -m "feat: added X"
git push -u origin "$(git branch --show-current)"

# 3) PR body file
cat > .tmp/pr_body.md <<'EOF'
## Summary
Implemented feature X.

## Multi-Role Review
### PM
- Findings:
- Severity:
- Action:

### TPM
- Findings:
- Severity:
- Action:

### 기획자
- Findings:
- Severity:
- Action:

### 개발자
- Findings:
- Severity:
- Action:

### 신입개발자
- Findings:
- Severity:
- Action:

### 운영자
- Findings:
- Severity:
- Action:

## Merge Decision
- Critical issue exists?: No
- Merge now?: Yes
- Follow-up PR needed?: No
EOF
gh pr create --head "$(git branch --show-current)" --base master --title "feat: added X" --body-file .tmp/pr_body.md

# 4) Merge (default when user did not request hold)
gh pr merge <PR_NUMBER> --squash --delete-branch

rm -f .tmp/pr_body.md
```
