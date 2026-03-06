# Codex 실행 가이드

> Codex가 코드를 수정하거나 새 기능을 개발할 때 참조하는 실행 가이드입니다.
> 반드시 HANDOVER.md를 먼저 읽은 후 이 파일을 참조하세요.

---

## Quick Reference

### 테스트 실행

```bash
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v
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
# PR body를 .tmp/pr_body.md에 저장
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

상세 설명과 사용법을 기술합니다.

[Task x.x, REQ-xxx]
"""

from src.utils.logger import global_logger

# 구현...
```

### 새 테스트 작성 템플릿

```python
"""
모듈명 단위 테스트 모듈.

[Task x.x, REQ-xxx]
"""

import unittest
from unittest.mock import MagicMock
import sys

sys.modules['src.utils.logger'] = MagicMock()

from src.모듈 import 클래스_또는_함수


class TestModuleName(unittest.TestCase):
    """테스트 클래스."""

    def test_기능(self):
        """테스트 설명."""
        pass


if __name__ == "__main__":
    unittest.main()
```

### PR Body 템플릿

```markdown
## PR 요약

한줄 요약

### 3관점 리뷰

- 개발자: 기술적 평가
- 검토자: 코드 품질 평가
- 운영자: 운영 영향 평가

머지 승인
```

---

## 주의사항

### 절대 하지 말 것

1. `gh pr create`에서 `--body` 인라인 사용 (→ hang)
2. 대화형 명령어 실행 (`vi`, `nano`, `less`)
3. `/tmp/`에 임시파일 생성 (→ `.tmp/` 사용)
4. 테스트 없이 PR 생성
5. `todo/todo.md` 갱신 없이 세션 종료
6. 커밋 메시지를 한줄로만 작성

### 반드시 할 것

1. 작업 완료 시 `logging/YYYY-MM-DD.md` 기록
2. 에러 발생 시 `errorCase/` 기록
3. 테스트 ALL PASS 확인 후 커밋
4. PR merge 후 `todo/todo.md` 갱신
5. 세션 종료 시 hang 프로세스 정리
6. 파일 상단에 모듈 설명 docstring 작성
