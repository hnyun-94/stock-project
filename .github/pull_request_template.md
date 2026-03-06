## Summary
- 기능 단위 설명:
- 범위 제외:

## Delivery Workflow Checklist
- [ ] 기능 단위로 분할 완료
- [ ] 품질 게이트 통과 (`uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q`)
- [ ] 커밋 크기 검증 통과 (`scripts/check_commit_size.sh --range origin/master..HEAD --max-lines 400`)
- [ ] 커밋 및 push 완료
- [ ] Multi-Role Review 작성
- [ ] Critical 이슈 0개 또는 동일 PR에서 수정 완료
- [ ] 머지 가능 상태 확인

## Commit Size Check
- 기준: commit 당 (추가+삭제) <= 400 lines
- 실행 결과:
  - `scripts/check_commit_size.sh --range origin/master..HEAD --max-lines 400`

## Quality Gate
- `uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q`
- 결과:

## Multi-Role Review

### PM
- Findings:
- Severity (`critical`/`major`/`minor`):
- Action:

### TPM
- Findings:
- Severity (`critical`/`major`/`minor`):
- Action:

### 기획자
- Findings:
- Severity (`critical`/`major`/`minor`):
- Action:

### 개발자
- Findings:
- Severity (`critical`/`major`/`minor`):
- Action:

### 신입개발자
- Findings:
- Severity (`critical`/`major`/`minor`):
- Action:

### 운영자
- Findings:
- Severity (`critical`/`major`/`minor`):
- Action:

## Merge Decision
- Critical issue exists?: Yes/No
- Merge now?: Yes/No
- Follow-up PR needed?: Yes/No
- Follow-up scope:
