# GitHub 명령 권한 위임 정책 계획서

## 요청 요약

- GitHub 관련 명령어 권한은 앞으로 위임된 상태로 다루고 싶다.
- 다만 사용자 보안과 프로젝트 안전성은 유지해야 한다.

## 역할별 검토

### PM

- 판단: 채택
- 근거: PR 생성, 확인, 머지, 원격 push는 반복 빈도가 높아 매번 승인 판단을 다시 하는 비용이 크다.

### TPM

- 판단: 부분 채택
- 근거: 일반 GitHub 협업 명령은 위임해도 되지만, `gh api`, secret, auth, force push, destructive remote 작업까지 넓히면 위험하다.

### 기획자

- 판단: 채택
- 근거: 사용자는 "어디까지는 맡겨도 되는지" 경계가 한눈에 보여야 한다. 위임 범위와 예외 범위를 명시해야 한다.

### 개발자

- 판단: 채택
- 근거: 실제 반복 흐름은 `git push`, `gh pr create/view/merge`, workflow 상태 확인 정도다. 이 범위는 정책으로 승격하는 편이 효율적이다.

### 신입개발자

- 판단: 채택
- 근거: GitHub 명령 전체를 묶어 막아두면 필요 이상으로 보수적이고, 반대로 전체를 풀어두면 위험하다. 협업 명령과 관리자 명령을 나누는 편이 이해하기 쉽다.

### 운영자

- 판단: 부분 채택
- 근거: 일반 PR 협업은 위임 가능하지만, 저장소 설정 변경, secret 조작, 강제 push, mass action은 여전히 명시적 재확인이 필요하다.

## 검토 라운드

### 1차 검토

- 선택안 A: GitHub 관련 명령 전부 위임
- 선택안 B: 일반 협업 명령만 위임, 관리자/파괴적 명령은 예외 유지
- 판단: B 채택
- 기각 이유:
  - A는 속도는 빠르지만 권한 오남용과 복구 비용이 커진다.

### 2차 검토

- 검토 내용: 실제 위임 범위
- 판단:
  - 위임: `git push`, `gh pr create/view/checks/merge`, `gh run view/watch`, `gh workflow view`
  - 예외 유지: `gh api`, `gh auth`, `gh secret`, `gh variable`, `gh release delete`, remote branch 강제 삭제, force push

### 3차 검토

- 검토 내용: 구현 방식
- 판단:
  - `AGENTS.md`의 Command Permission Policy를 갱신한다.
  - `command-permission-governance` skill을 갱신해 같은 기준을 재사용한다.
  - `.codex/config.toml`은 broad auto-approval로 바꾸지 않는다.
- 기각 이유:
  - config를 과도하게 완화하면 GitHub 외의 민감 권한까지 함께 느슨해질 수 있다.

## 종합 판단

- GitHub 관련 명령 전체를 일괄 위임하지는 않는다.
- 대신 표준 협업 명령은 상시 위임 범위로 승격한다.
- 파괴적, 관리자급, 범용 API 계열 GitHub 명령은 계속 재확인 대상으로 남긴다.
- 운영상 실제 자동 강제 검증은 기존의 `pre-push`와 품질 게이트를 유지한다.
