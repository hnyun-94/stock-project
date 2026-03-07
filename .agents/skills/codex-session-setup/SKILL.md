---
name: codex-session-setup
description: "Initialize a Codex session by loading project-management docs, checking repo/hook status, and running baseline tests."
---

# Codex Session Setup Skill

이 스킬은 새 Codex 세션에서 프로젝트 상태를 빠르게 복원하고 작업 가능 상태를 보장합니다.

## Usage Trigger

다음 요청일 때 사용합니다.

- "세팅해줘", "온보딩", "프로젝트 현황 읽고 시작"
- 프로젝트 관리 문서 로딩 + 상태 점검 + 기본 검증이 동시에 필요한 작업

## Instructions

1. 핵심 문서 로딩:
   `AGENTS.md`, `todo/todo.md`, `done/phase6_task.md`, `task/task.md`
2. E2E 운영 기준 문서 로딩(필요 시):
   `done/e2e_incident_response_plan.md`, `done/e2e_incident_execution_report.md`
3. 진행 상태 확인:
   `cat todo/todo.md`, 최신 `logging/YYYY-MM-DD.md`
4. 형상 관리 상태 확인:
   `git status`, `git branch`
5. Codex 설정/훅 점검:
   `.codex/config.toml` 존재 여부, `git config --get core.hooksPath`, `.githooks/pre-push` 실행 가능 여부
6. 기준선 테스트 실행:
   `uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q`
7. `AGENTS.md`의 Mandatory Delivery Workflow 섹션 존재 및 최신성 확인
8. 결과를 요약하고, 필요한 문서/설정 동기화를 반영합니다.

## Essential Commands

```bash
cat todo/todo.md
ls -t logging/ | head -1 | xargs -I{} cat logging/{}
git status && git branch
git config --get core.hooksPath
uv run python -m pytest tests/services/ tests/test_e2e_dryrun.py -q
```
