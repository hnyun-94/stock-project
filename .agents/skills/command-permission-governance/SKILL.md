---
name: command-permission-governance
description: "Use when the user asks to reduce approval fatigue, classify command risk, or formalize safe vs high-risk command usage."
---

# Command Permission Governance Skill

이 스킬은 "승인 피로를 줄이되, 위험한 권한은 유지"해야 하는 작업에서 사용합니다.

## Usage Trigger

- "권한 정리"
- "승인 피로 줄이기"
- "어떤 명령은 자동으로, 어떤 명령은 꼭 리뷰"
- "명령어 위험도 분류"

## Workflow

1. 현재 권한 경계를 확인합니다.
   - `AGENTS.md`
   - `.codex/config.toml`
   - `.githooks/pre-push`
2. 반복 작업 시퀀스를 분해합니다.
   - 세션 시작
   - 품질 게이트
   - git 전달
   - 외부 시스템 변경
3. 명령을 3단계로 분류합니다.
   - Safe: read-only, 로컬 검증, workspace 내부 스크립트
   - Caution: dependency sync, 범위가 애매한 remote write
   - Delegated GitHub Collaboration: 일반적인 push/PR/CI 상태 확인
   - Always Review: `.env`, 외부 발송, 서버 listen, schema 변경, destructive command, 관리자급 GitHub 명령
4. 안전한 명령군은 wrapper script로 묶습니다.
   - `scripts/session_bootstrap.sh`
   - `scripts/run_quality_gate.sh`
5. 정책을 `AGENTS.md`, `scripts/README.md`, 필요 시 관련 skill에 반영합니다.

## Guardrails

- 일반 GitHub 협업 명령은 위임할 수 있습니다.
  - 예: `git push`, `gh pr create/view/checks/merge`, `gh run view/watch`
- 하지만 아래는 계속 재확인 대상으로 남깁니다.
  - `gh api`, `gh auth`, `gh secret`, `gh variable`
  - force push, remote branch 삭제, repo/admin setting 변경, release 삭제
  - `.env`, Notion schema, 실제 발송, Docker, destructive git
- `ask-for-approval = never` 같은 광범위 완화는 기본적으로 금지합니다.
- 승인 피로는 권한 축소가 아니라 "반복 안전 명령의 표준화"로 해결합니다.
