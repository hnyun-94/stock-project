"""
이 스크립트는 Notion API를 사용하여 지정된 Notion 데이터베이스의 스키마를 업데이트합니다.
주요 목적은 특정 Notion 데이터베이스에 새로운 속성(컬럼)을 추가하거나 기존 속성을 업데이트하는 것입니다.
구체적으로 '수신 채널'(다중 선택 유형)과 '텔레그램ID'(리치 텍스트 유형)라는 두 가지 속성을 데이터베이스에 추가합니다.
환경 변수(.env 파일)에서 Notion API 토큰과 대상 데이터베이스 ID를 로드하여 인증 및 API 요청에 사용합니다.
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('NOTION_TOKEN')
db_id = os.getenv('NOTION_DATABASE_ID')

properties_to_add = {
    "수신 채널": {
        "multi_select": {
            "options": [
                {
                    "name": "email",
                    "color": "blue"
                },
                {
                    "name": "telegram",
                    "color": "blue"
                }
            ]
        }
    },
    "텔레그램ID": {
        "rich_text": {}
    }
}

response = httpx.patch(
    f"https://api.notion.com/v1/databases/{db_id}",
    headers={
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    },
    json={
        "properties": properties_to_add
    }
)

if response.status_code == 200:
    print("✅ 성공적으로 컬럼 2개('수신 채널', '텔레그램ID')를 추가 및 업데이트했습니다!")
else:
    print(f"❌ 에러({response.status_code}): {response.text}")
