# 명령 권한 정책 검토 및 실행 계획서

작성일: 2026-03-07

## 요청 요약

- 현재 작업 시퀀스에 필요한 명령을 정리한다.
- 사용자 개인 보안, 치명적 시스템 권한 여부를 구분한다.
- 이후 작업에서 승인/리뷰 피로도를 줄일 수 있도록 권한 정책과 실행 방식을 정비한다.

## 역할별 검토

### PM 관점

- 목표는 "승인 제거"가 아니라 "반복 승인 판단 비용 감소"다.
- 사용자는 같은 안전한 명령 세트를 매번 다시 설명받고 싶어하지 않는다.
- 반대로 개인 정보, 발송, 외부 시스템 변경까지 자동 승인되면 신뢰를 잃는다.

### TPM 관점

- 이 저장소는 `.env`, Notion, Gemini, 이메일, GitHub write 권한을 함께 가진다.
- 따라서 `ask-for-approval = never` 또는 광범위한 full-auto 완화는 부적절하다.
- 이미 `.codex/config.toml`에서 `workspace-write + network=allow`가 적용되어 있으므로, 추가 완화 포인트는 "권한"보다 "명령 번들링"에 가깝다.

### 기획자 관점

- 세션 시작, 품질 게이트, 배포 직전 등 반복 구간은 한두 개의 표준 명령으로 묶여야 한다.
- 사용자는 어떤 명령이 안전하고 어떤 명령은 반드시 재확인해야 하는지 한 번에 이해할 수 있어야 한다.

### 개발자 관점

- 안전한 read-only/검증 명령은 wrapper script로 묶으면 된다.
- 외부 발송/서버 open/Notion 스키마 변경/파괴적 git는 wrapper를 만들더라도 승인 기준을 낮추면 안 된다.
- hook, skill, AGENTS 문서가 같은 명령 세트를 가리켜야 drift가 줄어든다.

### 신입개발자 관점

- `cat`, `git status`, `pytest`, `check_commit_size`를 매번 조합하기보다 `session_bootstrap.sh`, `run_quality_gate.sh` 같은 단일 진입점이 학습 부담을 줄인다.

### 운영자 관점

- `src.main` 실행은 실제 외부 API 호출과 발송 부작용이 있다.
- `feedback_server` 실행은 로컬/컨테이너에서 listen socket을 연다.
- `.env`, Notion schema, Docker, destructive git는 항상 명시적 재검토가 필요하다.

## 종합 판단

- 권한 자체를 넓히기보다 안전한 명령군을 표준 스크립트로 묶고, 위험도 매트릭스를 AGENTS와 skill로 승격하는 것이 타당하다.
- `.codex/config.toml`의 기본 정책은 유지한다.
  - 유지 이유: live secret + outbound side effect + remote write 권한이 공존
- 승인 피로 감소는 다음 3가지로 달성한다.
  1. 세션 시작용 명령 번들 추가
  2. 품질 게이트용 명령 번들 추가
  3. 권한 위험도 표를 AGENTS/skill에 반영

## 병렬 스트림

### Stream A: 정책/문서

- `AGENTS.md`에 명령 권한 매트릭스 추가
- `scripts/README.md`에 새 wrapper script 설명 추가
- 작업 로그 갱신

### Stream B: 실행 번들

- `scripts/session_bootstrap.sh` 추가
- `scripts/run_quality_gate.sh` 추가

### Stream C: 재사용 구조화

- `.agents/skills/codex-session-setup/SKILL.md` 업데이트
- `.agents/skills/e2e-test-suite/SKILL.md` 업데이트
- 명령 권한 전용 skill 추가

## 수용 기준

- 세션 시작과 품질 게이트를 각각 1개 명령으로 실행할 수 있다.
- AGENTS에 안전/주의/항상 리뷰 명령군이 구분되어 있다.
- `.codex/config.toml`은 보수적 승인 정책을 유지한다.
- 새 스크립트는 `sh -n`, 실제 실행 검증, 기존 테스트 게이트를 통과한다.
