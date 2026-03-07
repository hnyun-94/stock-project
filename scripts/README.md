# 스크립트 디렉토리

이 폴더에는 메인 파이프라인 외에 Codex/개발자가 반복적으로 사용하는 보조 스크립트가 모여 있습니다.

## 반복 작업 번들

| 파일명                    | 용도 |
| ------------------------- | ---- |
| `session_bootstrap.sh`    | 세션 시작 시 문서/형상/훅/기준선 테스트를 한 번에 점검 |
| `run_quality_gate.sh`     | py_compile + 커밋 크기 + 문맥 동기화 + 표준 pytest 게이트 실행 |
| `check_git_hygiene.sh`    | 금지 경로, 절대 경로, 실제 이메일 노출 여부를 검사 |
| `check_commit_size.sh`    | 커밋당 변경량(추가+삭제) 400줄 제한 검증 |
| `check_context_sync.sh`   | 코드/문서 동기화 및 런타임 smoke check |
| `check_review_policy.sh`  | 역할별 리뷰, 근거, 판단이 task/done 문서에 남았는지 검사 |
| `check_runtime_state.py`  | SQLite 런타임 상태 점검 |

## 파일 목록

| 파일명                    | 용도                          |
| ------------------------- | ----------------------------- |
| `add_columns.py`          | Notion DB 컬럼 추가           |
| `check_notion.py`         | Notion 연결 상태 확인         |
| `test_async_gemini.py`    | Gemini 비동기 호출 테스트     |
| `test_db.py`              | DB 연결 테스트                |
| `test_gemini.py`          | Gemini API 기본 테스트        |
| `test_gemini2.py`         | Gemini API 추가 테스트        |
| `test_notion.py`          | Notion API 테스트             |
| `update_notion_db.py`     | Notion DB 업데이트            |
| `update_notion_schema.py` | Notion DB 스키마 변경         |
| `update_notion_user.py`   | Notion 사용자 데이터 업데이트 |
| `provision_prompt_db.py`  | 프롬프트 DB 스키마/데이터 동기화 |

## 권한 정책 요약

- `session_bootstrap.sh`, `run_quality_gate.sh`는 기본적으로 안전한 로컬 검증 명령만 실행합니다.
- `check_git_hygiene.sh`는 Git에 올라가면 안 되는 로컬 산출물과 민감 패턴을 검사합니다.
- `check_review_policy.sh`는 구현성 변경이 근거 없는 즉흥 작업으로 끝나지 않았는지 검사합니다.
- `.env`, 외부 발송, 서버 listen, Notion 스키마 변경, destructive command는 이 번들에 포함하지 않습니다.
- 상세 기준은 `AGENTS.md`의 `Command Permission Policy` 섹션을 따릅니다.
