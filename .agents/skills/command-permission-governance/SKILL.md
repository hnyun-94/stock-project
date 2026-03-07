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
   - Caution: 범위가 애매한 remote write, uv 외 일반 외부 시스템 변경
   - Delegated uv Commands: 사용자가 prefix 자체를 위임한 `uv sync`, `uv run ...`, `uv tool ...`
   - Delegated gh Commands: 현재 repo 범위의 일반적인 협업/조회 명령
   - Always Review: `.env`, non-uv 서버/컨테이너 실행, schema 변경, destructive command, 관리자급 GitHub 명령
4. 안전한 명령군은 wrapper script로 묶습니다.
   - `scripts/session_bootstrap.sh`
   - `scripts/run_quality_gate.sh`
5. 정책을 `AGENTS.md`, `scripts/README.md`, 필요 시 관련 skill에 반영합니다.

## Repo Defaults

- Delegated uv Commands
  - `uv sync`
  - `uv lock`, `uv export`
  - `uv run ...`
  - `uv tool ...`
- Delegated gh Commands
  - `gh pr ...`
  - `gh run ...`
  - `gh workflow ...`
  - `gh repo view`
  - `gh issue ...`
  - `gh label list`, `gh search prs`, `gh search issues`
- Safe wrappers
  - `scripts/session_bootstrap.sh`
  - `scripts/run_quality_gate.sh`
- Always Review examples
  - `gh api`, `gh auth`, `gh secret`, `gh variable`
  - `gh repo edit`, `gh ruleset`, `gh release delete`
  - `.env`, Notion schema/data mutation, Docker, destructive git

## Guardrails

- 현재 repo 범위의 `gh` 협업/조회 명령은 위임할 수 있습니다.
  - 예: `git push`, `gh pr ...`, `gh run ...`, `gh workflow ...`, `gh issue ...`
- 사용자가 `uv` 전체를 위임한 경우 `uv` prefix는 별도 재확인 없이 사용합니다.
  - 예: `uv sync`, `uv run python -m pytest ...`, `uv run python -m src.main`
- 하지만 아래는 계속 재확인 대상으로 남깁니다.
  - `gh api`, `gh auth`, `gh secret`, `gh variable`
  - `gh repo edit`, `gh ruleset`, `gh release delete`
  - force push, remote branch 삭제, repo/admin setting 변경, 조직/계정 범위 대량 작업
  - `.env`, Notion schema, Docker, destructive git
- `ask-for-approval = never` 같은 광범위 완화는 기본적으로 금지합니다.
- 승인 피로는 권한 축소가 아니라 "반복 안전 명령의 표준화"로 해결합니다.
