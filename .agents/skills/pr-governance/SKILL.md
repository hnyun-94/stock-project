---
name: pr-governance
description: "Enforce feature-sliced PR workflow: commit size <=400 lines, multi-role PR review (PM/TPM/기획/개발/신입/운영), critical-issue handling, and merge/follow-up decision."
---

# PR Governance Skill

이 스킬은 PR 단위를 작게 유지하고, 다중 관점 리뷰를 표준화하여 안전하게 머지하기 위한 운영 절차입니다.
코드 변경 작업의 기본 완료 조건은 `commit -> push -> PR -> review -> merge` 전체 단계 완료입니다.

## Usage Trigger

다음 상황에서 반드시 사용합니다.

- 기능 구현을 시작할 때(작업 쪼개기 계획 수립)
- 커밋/PR 생성 직전
- PR 리뷰 및 머지 의사결정 시점

## Rules

1. 기능 단위로 PR을 분리합니다.
2. 각 커밋의 변경량(추가+삭제)은 최대 400줄을 넘기지 않습니다.
   - 이 한도는 계획서 단계에서 미리 커밋 예산으로 쪼갭니다.
   - 실제 목표치는 `300~350줄 내외`로 잡아 여유를 둡니다.
   - 수동 `check_commit_size` 실행은 기본 필수가 아니며, 예산 초과가 의심될 때만 사용합니다.
3. PR 본문에는 아래 6개 관점 리뷰를 모두 포함합니다.
   - PM
   - TPM
   - 기획자
   - 개발자
   - 신입개발자
   - 운영자
4. 리뷰 이슈는 심각도(`critical`, `major`, `minor`)를 명시합니다.
5. 치명적(`critical`) 이슈는 같은 PR에서 즉시 수정 후 재리뷰합니다.
6. 비치명적 개선사항은 머지 후 후속 PR로 분리 가능합니다.
7. 사용자가 머지 보류를 명시하지 않는 한, 코드 작업은 머지까지 수행합니다.

## Mandatory Sequence

1. 구현 전 계획서에 커밋 예산을 적습니다.
2. 구현 완료
3. 품질 게이트 실행
4. 기능 단위 커밋
   - 계획서의 커밋 예산 기준으로 나눕니다.
   - 범위 drift가 크면 수동 커밋 크기 검증을 추가합니다.
5. 원격 push
   - `pre-push`가 커밋 크기 정책을 자동 검증합니다.
6. PR 생성
7. 다중 관점 리뷰 및 이슈 처리
8. 머지 + 브랜치 정리

위 순서를 따르지 않으면 작업 완료로 간주하지 않습니다.

## Required PR Review Template

아래 형식을 PR 본문에 포함합니다.

```md
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
- Critical issue exists?: Yes/No
- Merge now?: Yes/No
- Follow-up PR needed?: Yes/No
- Follow-up scope (if needed):
```

## Decision Policy

- `critical` 발견:
  - PR 내 즉시 수정
  - 동일 PR에서 테스트 재실행 후 리뷰 갱신
  - 그 후 머지
- `major/minor`만 존재:
  - 현재 PR 머지 가능
  - 후속 PR 목록을 명시하고 생성
- 이슈 없음:
  - 바로 머지

## Commands

수동 커밋 크기 검증이 필요할 때만:

```bash
scripts/check_commit_size.sh --range origin/master..HEAD --max-lines 400
```

품질 게이트:

```bash
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
```
