"""
이 모듈은 Notion 데이터베이스의 스키마를 업데이트하는 역할을 합니다.

역할:
환경 변수에 설정된 Notion API 토큰과 데이터베이스 ID를 사용하여 Notion 데이터베이스의 속성(프로퍼티) 스키마를 수정합니다.
주요 업데이트 내용은 '보유종목' 속성을 rich_text 타입으로, '긴급알림 임계치' 속성을 percent 형식의 number 타입으로 설정하는 것입니다.

이 파일의 목적은 특정 데이터베이스가 주식 보유 종목 정보와 긴급 알림 임계치 값을 저장하고 관리할 수 있도록
필요한 스키마를 자동으로 구성하거나 업데이트하는 것입니다.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOTION_TOKEN")
DB_ID = os.getenv("NOTION_DATABASE_ID")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

data = {
    "properties": {
        "보유종목": {
            "rich_text": {}
        },
        "긴급알림 임계치": {
            "number": {
                "format": "percent"
            }
        }
    }
}

response = requests.patch(
    f"https://api.notion.com/v1/databases/{DB_ID}",
    headers=headers,
    json=data
)

if response.status_code == 200:
    print("성공적으로 Notion Database 스키마를 업데이트했습니다.")
else:
    print(f"업데이트 실패: {response.status_code}")
    print(response.json())
