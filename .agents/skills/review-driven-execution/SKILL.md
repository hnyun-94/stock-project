---
name: review-driven-execution
description: "Use when the user asks for PM/TPM/기획자/개발자/신입개발자/운영자 multi-role review, a written plan, parallel work streams, interim logging, and implementation after review."
---

# Review-Driven Execution Skill

이 스킬은 사용자가 반복적으로 요구한 협업 방식 자체를 표준화합니다.
대상은 "리뷰 -> 계획서 -> 병렬 실행 -> 중간 로그 -> 구현" 흐름이 필요한 작업입니다.

## Usage Trigger

다음 표현이 보이면 사용합니다.

- "PM, TPM, 기획자, 개발자, 신입개발자, 운영자 관점으로 검토"
- "계획서 작성 후 개발"
- "병렬로 진행"
- "중간 결과를 남기고 이어서 가능하게"
- "여러 번 리뷰 후 구현"

## Workflow

1. 관련 문서를 읽습니다.
   - `AGENTS.md`
   - `todo/todo.md`
   - 최신 로컬 `logging/YYYY-MM-DD.md`
   - 작업과 직접 연관된 `task/*.md`, `done/*.md`
2. 요구사항을 역할별로 검토합니다.
   - PM: 사용자 가치, 범위, 우선순위
   - TPM: 런타임/의존성/배포 리스크
   - 기획자: 정보 구조, UX, 수용 기준
   - 개발자: 모듈 경계, 테스트 가능성, 변경 범위
   - 신입개발자: 이해 가능성, 온보딩 난도
   - 운영자: 관측성, 장애 복구, 안전성
3. 결과를 `task/<주제>_plan.md`에 구조화합니다.
   - 요청 요약
   - 역할별 검토
   - 종합 판단
   - 병렬 스트림
   - 구현 범위 / 후속 범위
   - 수용 기준
4. 구현 전 병렬 스트림을 확정합니다.
   - 공통 파일 충돌이 큰 스트림은 마지막에 합칩니다.
   - 테스트/문서/운영 경로는 가능한 한 먼저 마련합니다.
5. 중간 결과를 남깁니다.
   - 구현이 시작되면 로컬 `logging/YYYY-MM-DD.md`에 작업 내용/검증 결과를 기록합니다.
   - Git에 남겨야 할 내용은 `task/` 또는 `done/` 문서에 정제해서 남깁니다.
6. 구현 후 품질 게이트와 Git 전달 절차를 완료합니다.

## Default Outputs

- 계획서: `task/*.md`
- 작업 로그: 로컬 `logging/YYYY-MM-DD.md`
- 필요 시 후속 백로그: 관련 `task/*.md`

## Guardrails

- 역할 리뷰 없이 바로 큰 기능 구현으로 들어가지 않습니다.
- 계획서가 없는 상태에서 공통 파일(`src/main.py`, workflow, DB 계층)을 크게 수정하지 않습니다.
- 반복 요구를 발견하면 임시 대응으로 끝내지 말고 `AGENTS.md`, `skills`, `hooks`, `scripts`로 승격합니다.
