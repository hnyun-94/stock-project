# 일회성/유틸리티 스크립트 디렉토리

이 폴더에는 **메인 파이프라인에 포함되지 않는** 일회성 스크립트들이 모여 있습니다.
Notion DB 스키마 변경, API 연결 테스트 등 개발/운영 시 한 번만 실행하는 용도입니다.

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
