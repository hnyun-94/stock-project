# Codex 실행 가이드

> Codex가 코드를 수정하거나 새 기능을 개발할 때 참조하는 실행 가이드입니다.
> 반드시 `AGENTS.md` (프로젝트 루트)와 `HANDOVER.md`를 먼저 읽은 후 이 파일을 참조하세요.

---

## Quick Reference

### 실행

```bash
# 의존성 설치 (최초 1회)
uv sync --frozen

# 파이프라인 실행
uv run python -m src.main

# 피드백 서버 실행
uv run python -m src.apps.feedback_server

# Docker
docker-compose up --build
```

### 테스트

```bash
# 표준 테스트 (권장 — 외부 API 불필요)
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v

# 전체 테스트 (aiohttp/playwright 라이브 필요)
python -m pytest tests/ -v

# 특정 파일
python -m pytest tests/services/test_cache.py -v
```

### 문법 검증

```bash
python -c "import ast; ast.parse(open('파일경로').read()); print('OK')"
```

### Git 워크플로우

```bash
git checkout -b feat/기능명
# 코드 작성...
git add 파일들
git commit -m "feat: 설명 [Task x.x, REQ-xxx]"
git push -u origin feat/기능명

# ⚠️ PR body는 반드시 파일로 (hang 방지)
echo "PR 내용" > .tmp/pr_body.md
gh pr create --base master --head feat/기능명 --title "..." --body-file .tmp/pr_body.md

gh pr merge N --squash --subject "..." --delete-branch
rm -f .tmp/pr_body.md
```

---

## 코드 작성 규칙

### 새 모듈 작성 템플릿

```python
"""
모듈 한줄 설명.

상세 설명: 이 모듈의 역할, 다른 모듈과의 관계를 기술합니다.
저장소/의존성: 어떤 외부 서비스나 DB에 의존하는지 명시합니다.

[Task x.x, REQ-xxx]
"""

import os
from src.utils.logger import global_logger
from src.utils.database import get_db  # DB 필요 시

# 구현...
```

### 새 테스트 작성 템플릿

```python
"""
모듈명 단위 테스트 모듈.

이 테스트는 외부 API 호출 없이 순수 로직만 검증합니다.

[Task x.x, REQ-xxx]
"""

import unittest
from unittest.mock import MagicMock
import sys

# ⚠️ 반드시 import 전에 로거 Mock 처리
sys.modules['src.utils.logger'] = MagicMock()

from src.모듈 import 클래스_또는_함수


class TestModuleName(unittest.TestCase):
    """테스트 클래스."""

    def setUp(self):
        """각 테스트 전 초기화."""
        pass

    def test_기본_동작(self):
        """정상 케이스 테스트."""
        result = 함수()
        self.assertEqual(result, expected)

    def test_엣지_케이스(self):
        """에러/경계값 테스트."""
        pass


if __name__ == "__main__":
    unittest.main()
```

### 커밋 메시지 템플릿

```
feat: 한줄 기능 설명 [Task x.x, REQ-xxx]

## 변경 내용

### 신규: src/모듈/파일명.py
- 기능 A 추가: 상세 설명
- 기능 B 추가: 상세 설명

### 수정: src/기존/파일명.py
- 기존 동작 X를 Y로 변경한 이유 설명
- 새 의존성 import 추가

### 테스트: tests/services/test_파일명.py
- N개 단위 테스트 추가
- 커버리지: 주요 함수 전체
```

### PR Body 템플릿

```markdown
## PR 요약

한줄 요약

### 3관점 리뷰

- **개발자**: 기술적 변경사항과 성능/안정성 영향
- **검토자**: 코드 품질, 테스트 커버리지, 코딩 컨벤션 준수
- **운영자**: 운영 환경에 미치는 영향, 필요한 설정 변경

### 테스트 결과

- `python -m pytest tests/services/ tests/test_e2e_dryrun.py -v`
- XX passed in X.Xs

머지 승인
```

---

## 주의사항

### ❌ 절대 하지 말 것

1. `gh pr create`에서 `--body` 인라인 사용 → **터미널 hang**
2. 대화형 명령어 실행 (`vi`, `nano`, `less`, `more`, `python` REPL)
3. `/tmp/`에 임시파일 생성 → `.tmp/` 사용
4. 테스트 없이 PR 생성
5. `todo/todo.md` 갱신 없이 세션 종료
6. 커밋 메시지를 한줄로만 작성 (body 필수)
7. `src/utils/logger.py`를 직접 import하는 테스트 코드 (Mock 필수)
8. `models.py` 수정 시 영향도 미검증

### ✅ 반드시 할 것

1. 작업 완료 시 `logging/YYYY-MM-DD.md` 기록
2. 에러 발생 시 `errorCase/YYYY-MM-DD_에러명.md` 기록
3. 테스트 ALL PASS 확인 후 커밋
4. PR merge 후 `todo/todo.md` 갱신
5. 세션 종료 시 hang 프로세스 정리 (`pkill -f "gh pr"`)
6. 파일 상단에 모듈 설명 docstring 작성
7. 새 모듈 추가 시 `DEPENDENCY_MAP.md` 업데이트
8. 코드 변경 시 `AGENTS.md`의 관련 섹션도 동기화 검토

### ⚠️ 수정 시 주의가 필요한 파일

| 파일                 | 위험도 | 이유                             |
| -------------------- | :----: | -------------------------------- |
| `models.py`          |   🔴   | 모든 크롤러+서비스가 의존        |
| `database.py`        |   🔴   | 스키마 변경 시 마이그레이션 필요 |
| `http_client.py`     |   🟠   | 모든 크롤러가 의존               |
| `circuit_breaker.py` |   🟠   | 설정 변경이 AI 전체에 영향       |
| `main.py`            |   🟠   | 파이프라인 흐름 변경             |
| `ai_summarizer.py`   |   🟡   | CB+Retry+Semaphore 3중 보호      |
