---
description: 터미널 Hang 방지를 위한 안전한 작업 가이드
---

# 터미널 Hang 방지 워크플로우

## 원칙

Agent가 `run_command` 도구로 터미널 명령을 실행할 때 "Running" 상태로 무한 대기하는
알려진 이슈가 있습니다. 이를 방지하기 위해 다음 원칙을 따릅니다.

## 작업 순서

### 1. 코드 작성

- `write_to_file`, `replace_file_content`, `multi_replace_file_content` 도구만 사용
- 절대 터미널에서 Python을 실행하여 코드를 검증하지 않음

### 2. 코드 검증

- `view_file`로 파일을 읽어 코드 리뷰로 검증
- `python -c`, `python -m py_compile` 등 Python 실행 명령 사용 금지
- 특히 `global_logger` 등 사이드이펙트가 있는 모듈의 import 테스트 절대 금지

### 3. git 작업 (커밋/PR)

- Agent가 직접 `run_command`로 git 명령을 실행하지 않음
- 대신, 사용자에게 실행할 명령어를 **텍스트로 안내**
- 사용자가 자신의 터미널에서 직접 실행

### 4. 결과 확인

- 사용자가 git 명령 실행 결과를 Agent에게 전달
- Agent는 결과를 확인하고 다음 작업 진행

## 예외 상황

- 터미널이 정상 작동하는 것이 확인된 경우에만 Agent가 직접 실행 고려
- 이 경우에도 `SafeToAutoRun: true`, `WaitMsBeforeAsync: 10000`으로 설정
- hang 발생 시 즉시 이 워크플로우로 전환
