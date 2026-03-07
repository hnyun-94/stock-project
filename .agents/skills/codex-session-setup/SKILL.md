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
3. 기본 점검은 `scripts/session_bootstrap.sh`로 실행합니다.
4. 빠른 문맥만 필요하면 `scripts/session_bootstrap.sh --no-tests`를 사용합니다.
5. Codex 설정/훅 점검:
   `.codex/config.toml` 존재 여부, `git config --get core.hooksPath`, `.githooks/pre-push` 실행 가능 여부
7. `AGENTS.md`의 Mandatory Delivery Workflow 섹션 존재 및 최신성 확인
8. 이전 세션이 남긴 정제 문서(`task/`, `done/`, `README.md`, `AGENTS.md`)를 우선 기준선으로 삼고, raw 문맥 재사용은 필요한 경우에만 제한적으로 수행합니다.
9. 결과를 요약하고, 필요한 문서/설정 동기화를 반영합니다.

## Essential Commands

```bash
scripts/session_bootstrap.sh
scripts/session_bootstrap.sh --no-tests
```
