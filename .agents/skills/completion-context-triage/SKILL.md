---
name: completion-context-triage
description: "Use when wrapping up work to decide whether to keep, compress, or drop context based on remaining queue and handoff value."
---

# Completion Context Triage Skill

이 스킬은 작업 종료 시 context를 무조건 유지하지 않고, 실제 후속 작업 가치가 있는 정보만 남기기 위한 기준입니다.

## Usage Trigger

- "마무리"
- "후속 작업 확인"
- "context 정리"
- "wrap up"
- 구현, 검증, PR/merge가 끝난 직후

## Workflow

1. 남아 있는 큐를 확인합니다.
   - 현재 사용자의 미해결 요청
   - 이번 변경과 직접 이어지는 `todo/`, `task/`, `done/` 후속 항목
   - 실패한 검증, 미해결 오류, dirty worktree, 미머지 PR
2. 아래 세 가지를 판단합니다.
   - context를 유지하는 것이 바로 다음 작업 품질에 유리한가
   - 필요한 정보가 이미 정제 문서에 남아 있는가
   - raw context를 계속 유지하면 노이즈나 overflow가 커지는가
3. 결과를 세 가지 중 하나로 결정합니다.
   - Keep: 즉시 이어질 후속 작업이 있고, 아직 문서화되지 않은 핵심 맥락이 남아 있을 때
   - Compress: 후속 작업은 있지만 raw 맥락 전체는 불필요할 때
   - Drop: 후속 작업이 없거나, 정제 문서만으로 충분할 때
4. `Compress` 또는 `Keep`일 때는 아래만 남깁니다.
   - 현재 상태
   - 핵심 변경 파일
   - 검증 결과
   - 잔여 리스크
   - 다음 액션
5. 긴 로그, 반복 설명, 이미 `task/`, `done/`, `README.md`, `AGENTS.md`에 남은 내용은 재보존하지 않습니다.

## Guardrails

- 이 스킬은 deterministic hook로 강제하지 않습니다.
- context 최적화에 실익이 없으면 적용하지 않습니다.
- raw 로그보다 정제 문서를 우선 기준선으로 삼습니다.
- 주식/뉴스 맥락은 최신성이 중요하므로, 오래된 상세 맥락을 기계적으로 유지하지 않습니다.
