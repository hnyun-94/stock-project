# GitHub 명령 권한 위임 정책 계획서

## 요청 요약

- GitHub 관련 명령어(`gh`) 권한은 앞으로 위임된 상태로 다루고 싶다.
- 다만 사용자 보안과 프로젝트 안전성은 유지해야 한다.

## 역할별 검토

### PM

- 판단: 확대 채택
- 근거: PR 생성, 확인, 머지, run 조회뿐 아니라 이슈/워크플로우/저장소 조회도 반복 빈도가 높아 매번 승인 판단을 다시 하는 비용이 크다.

### TPM

- 판단: 조건부 확대 채택
- 근거: `gh`를 broadly 위임할 수는 있지만, `gh api`, `gh auth`, secret/variable, repo setting, destructive release 작업까지 열면 위험 경계가 사라진다.

### 기획자

- 판단: 채택
- 근거: 사용자는 `gh` 전반을 맡기고 싶어 하지만, 실제 문서는 "대부분 허용 + 민감 작업 예외"가 한눈에 보이도록 정리돼야 한다.

### 개발자

- 판단: 확대 채택
- 근거: 실제 반복 흐름은 `gh pr`, `gh run`, `gh workflow`, `gh repo`, `gh issue` 조회/협업까지 넓다. repo 운영 범위의 `gh`는 상시 위임해도 효율적이다.

### 신입개발자

- 판단: 채택
- 근거: `gh` 전체를 막아두면 필요 이상으로 불편하고, 전부 열어두면 왜 위험한지 감이 안 잡힌다. repo 협업용과 관리자용을 나누는 편이 이해하기 쉽다.

### 운영자

- 판단: 조건부 확대 채택
- 근거: 일반 repo 협업/조회는 위임 가능하지만, 저장소 설정 변경, secret 조작, 강제 push, mass action, 조직 범위 작업은 여전히 명시적 재확인이 필요하다.

## 검토 라운드

### 1차 검토

- 선택안 A: `gh` 관련 명령 전부 위임
- 선택안 B: repo 협업/조회 명령 대부분 위임, 관리자/파괴적 명령은 예외 유지
- 판단: B 채택
- 기각 이유:
  - A는 속도는 빠르지만 권한 오남용과 복구 비용이 커진다.

### 2차 검토

- 검토 내용: 실제 위임 범위
- 판단:
  - 위임:
    - 현재 repo 범위의 `gh pr ...`
    - 현재 repo 범위의 `gh run ...`
    - 현재 repo 범위의 `gh workflow ...`
    - 현재 repo 범위의 `gh repo view`
    - 현재 repo 범위의 `gh issue ...`
    - 현재 repo 범위의 `gh label list`, `gh search prs`, `gh search issues`
  - 예외 유지:
    - `gh api`, `gh auth`
    - `gh secret`, `gh variable`
    - `gh repo edit`, `gh ruleset`, `gh release delete`
    - 조직/계정 범위 대량 작업, destructive remote 작업, force push

### 3차 검토

- 검토 내용: 구현 방식
- 판단:
  - `AGENTS.md`의 Command Permission Policy를 갱신한다.
  - `command-permission-governance` skill을 갱신해 같은 기준을 재사용한다.
  - `scripts/README.md`, `.codex/config.toml` 설명도 최신화한다.
- `.codex/config.toml`은 broad auto-approval로 바꾸지 않는다.
- 기각 이유:
  - config를 과도하게 완화하면 GitHub 외의 민감 권한까지 함께 느슨해질 수 있다.

## 종합 판단

- `gh` 명령은 앞으로 **현재 repo의 협업/조회성 명령 대부분을 상시 위임 범위**로 취급한다.
- 파괴적, 관리자급, 계정/secret/API 계열 GitHub 명령은 계속 재확인 대상으로 남긴다.
- 운영상 실제 자동 강제 검증은 기존의 `pre-push`와 품질 게이트를 유지한다.
