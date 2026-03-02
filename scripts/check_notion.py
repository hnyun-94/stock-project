"""
이 스크립트는 notion-client 라이브러리를 사용하여 Notion API와의 기본적인 상호작용을 테스트하고 시연합니다.
환경 변수(.env 파일)에서 Notion API 인증 토큰과 대상 데이터베이스 또는 페이지의 ID를 로드하여 사용합니다.
주어진 ID가 Notion 데이터베이스인지 또는 페이지인지 확인하기 위해 두 가지 유형의 검색을 시도하고,
성공 시 해당 객체의 관련 정보를 표준 출력(console)에 출력합니다.
또한, `notion.databases` 객체에서 사용 가능한 메서드들을 탐색하여 보여줍니다.
이는 Notion API 연동 초기 단계에서 Notion 객체의 유효성 검사 및 사용 가능한 기능 탐색에 유용합니다.

역할:
    - 환경 변수에서 Notion API 토큰 및 데이터베이스/페이지 ID 로드.
    - Notion 클라이언트 객체 초기화.
    - 주어진 ID를 Notion 데이터베이스로 조회 시도 및 성공 시 출력.
    - 주어진 ID를 Notion 페이지로 조회 시도 및 성공 시 출력.
    - `notion.databases` 객체의 사용 가능한 메서드 목록 출력.

입력:
    - 환경 변수:
        - `NOTION_TOKEN` (문자열): Notion API 인증을 위한 시크릿 토큰.
                                 예: 'secret_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        - `NOTION_DATABASE_ID` (문자열): 테스트할 Notion 데이터베이스 또는 페이지의 고유 ID.
                                        예: 'a1b2c3d4-e5f6-7890-1234-567890abcdef'

반환값:
    - 없음 (스크립트 실행 결과 및 오류 메시지를 표준 출력(console)에 직접 출력합니다).
"""
import os
import pprint
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()
notion = Client(auth=os.getenv('NOTION_TOKEN'))
db_id = os.getenv('NOTION_DATABASE_ID')

print(f"Checking ID: {db_id}")

try:
    res = notion.databases.retrieve(database_id=db_id)
    print("This is a DATABASE!")
    # In notion-client 3.0.0, querying a database is: notion.databases.query(database_id=db_id)
    # Wait, earlier dir(notion.databases) showed `query` does NOT exist.
    # Actually, in notion_client 3.0.0, `query` IS inside `notion.databases`. Let's print dir!
    print("Database columns:")
    pprint.pprint(list(res.get('properties', {}).keys()))
except Exception as e:
    print(f"Error retrieving as database: {e}")

try:
    res = notion.pages.retrieve(page_id=db_id)
    print("This is a PAGE!")
    print("URL:", res.get('url'))
except Exception as e:
    print(f"Error retrieving as page: {e}")

try:
    print("Dir of notion.databases:")
    print(dir(notion.databases))
except Exception as e:
    print(f"Error: {e}")
