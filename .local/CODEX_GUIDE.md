# Codex 실행 가이드

> OpenAI Codex Agent가 코드를 수정하거나 새 기능을 개발할 때 참조하는 환경/실행 가이드입니다.
> 반드시 프로젝트 루트의 `AGENTS.md`와 상세 시스템인 `HANDOVER.md`를 먼저 읽은 후 이 파일을 참조하세요.

---

## 🛠 Codex Agent Environment & Sandbox Setup

Codex는 강화된 샌드박스로 로컬 파일 변경과 네트워크 통신을 제한합니다. 이 프로젝트 원활한 실행을 위해 아래 설정을 확인/구성하십시오.

### 1. `config.toml` 프로젝트 지역 설정 허용

- 필요시 프로젝트 루트의 `.codex/config.toml` (또는 `~/.codex/config.toml`)에 대해 다음 권한을 에스컬레이션하세요:
  ```toml
  [sandbox]
  mode = "workspace-write"  # 작업 영역의 파일만 읽고 씀
  network = "allow"         # `aiohttp` 크롤링 및 Gemini API 연동을 허용하려면 필수
  ask-for-approval = "on-request" # 민감한 명령 외에는 --full-auto 모드로 빠르게 진행
  ```

### 2. Full-Auto Error Mode (터미널 Hang 주의)

- Codex가 `--full-auto`로 동작할 때 명령 실행 결과를 대기합니다.
- 상호작용이 필요한 명령어(예: `vi`, `npm install` 중단, Pager 등)는 백그라운드에서 Hang을 유발합니다. 따라서 다음과 같이 무인 모드로만 실행합니다.

---

## 💻 Quick Reference

### 실행

```bash
# 의존성 설치 (최초 1회, 인터랙티브 끄기)
uv sync --frozen

# 파이프라인 무인 실행
uv run python -m src.main
```

### 테스트 (Codex 권장 단위 검증)

```bash
# 외부 API 없이 순수 비즈니스 로직(Services) 및 드라이런 검증
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 크롤러 개발 후 외부 네트워크 정상 여부 확인 (aiohttp 라이브)
python -m pytest tests/ -v
```

### 문법/구문 빠른 검증

```bash
python -c "import ast; ast.parse(open('src/services/ai_summarizer.py').read()); print('OK')"
```

---

## 🤝 Project Codex Collaboration Rules

### 새 모듈 템플릿

```python
"""
모듈의 역할을 설명하는 한줄 docstring.

[Task x.x, REQ-xxx]
저장소/의존성: 어떤 DB나 API(Gemini, Notion 등)를 연동하는지 서술.
"""

from typing import List, Dict
import logging
from src.utils.logger import global_logger
from src.utils.database import get_db

# 기능 구현...
```

### 테스트 코드 템플릿 (Mock 필수)

```python
"""
비즈니스 로직에 대한 순수 단위 테스트.
"""

import unittest
from unittest.mock import MagicMock
import sys

# ⚠️ 반드시 대상 모듈 import 직전에 logger를 Mock 처리하여 로그 I/O 차단
sys.modules['src.utils.logger'] = MagicMock()

from src.services.new_service import TargetClass

class TestNewService(unittest.TestCase):
    def setUp(self):
        pass

    def test_success_case(self):
        result = TargetClass().do_something()
        self.assertTrue(result)
```

### 커스텀 스킬 (Agent Skills) 생성 템플릿

Codex의 역량 및 자동화를 확장하려면 `.agents/skills/<skill-name>/SKILL.md` 경로에 아래 형식으로 스킬을 정의하십시오.

```yaml
---
name: 스킬 이름 (소문자, 하이픈)
description: "스킬의 목적과 동작 방식 간략 요약"
---

# 스킬 제목

## Usage Trigger
이 스킬을 언제 실행해야 하는지 명시 (예: 배포 직전, 특정 에러 발생 시)

## Instructions
1. 실행할 구체적 동작
2. 사용할 커맨더
```

### 작업 완료 체크리스트 (Hooks 대체)

Codex는 `pre-commit` 등 고정된 Git Hook 대신 Automation 지침으로 다음을 수행해야 함:

1. 테스트 실행 100% PASS 확인
2. `DEPENDENCY_MAP.md` 갱신 (모듈 추가/삭제 시)
3. `todo/todo.md` 체크 갱신
4. `logging/YYYY-MM-DD.md` 파일에 요약본 기록
5. 터미널 Hang Process Clear (`pkill -f`)

### 커밋 및 PR 원칙

- **커밋**: Conventional 커밋. 예) `feat: add sentiment model [REQ-101]`
- **PR 생성**:
  ```bash
  echo "PR Description here" > .tmp/pr_body.md
  gh pr create --head <BRANCH> --base master --title "<TITLE>" --body-file .tmp/pr_body.md
  ```
  _(절대로 `gh pr create --body "..."` 사용 금지)_

---

## ⚠️ 취약점 알리미 (Danger Zones)

| 모듈 경로        | 위험성          | 파급 효과                                                                     |
| ---------------- | --------------- | ----------------------------------------------------------------------------- |
| `models.py`      | 🔴 **CRITICAL** | 전체 크롤러 및 DB 타입 에러 발생. 필드 추가/삭제 전 모든 모듈 검색 필수       |
| `database.py`    | 🔴 **CRITICAL** | WAL 모드 및 스키마 구조. 컬럼 변경 시 이전 데이터 마이그레이션 전략 필요      |
| `http_client.py` | 🟠 **HIGH**     | `aiohttp` 세션 풀 관리. 타임아웃/헤더 변경 시 Reddit 등 Strict 403 API에 타격 |
| `main.py`        | 🟠 **HIGH**     | `asyncio.gather` 병행 처리 및 파이프라인 단계 로직 깨짐 시퀀스                |

_(※ 위 파일을 수정해야 할 경우 가장 보수적인 테스트를 선행하십시오.)_
