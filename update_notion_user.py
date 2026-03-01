"""
이 모듈은 Notion API를 사용하여 특정 Notion 페이지의 속성을 업데이트하는 스크립트입니다.

**역할 (Role):**
환경 변수로부터 Notion API 토큰을 로드하고, 지정된 Notion 페이지 ID에 대해 특정 속성(예: '보유종목', '긴급알림 임계치')을 PATCH 요청을 통해 업데이트합니다.
이는 Notion 데이터베이스의 페이지 내용을 자동으로 관리하고 갱신하는 데 사용될 수 있습니다.

**사용 방법 (Usage):**
1. `.env` 파일에 `NOTION_TOKEN` 환경 변수를 설정합니다.
2. `PAGE_ID` 변수에 업데이트하고자 하는 Notion 페이지의 ID를 입력합니다.
3. `data` 변수에 업데이트할 속성 정보와 값을 JSON 형식으로 정의합니다.
4. 스크립트를 실행하여 Notion 페이지를 업데이트합니다.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = "3133efeb-d7d9-8010-8562-d94dddfde20f" # 윤현노 페이지 ID

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

data = {
    "properties": {
        "보유종목": {
            "rich_text": [
                {
                    "text": {
                        "content": "삼성전자, SK하이닉스, 엔비디아"
                    }
                }
            ]
        },
        "긴급알림 임계치": {
            "number": 0.05
        }
    }
}

response = requests.patch(
    f"https://api.notion.com/v1/pages/{PAGE_ID}",
    headers=headers,
    json=data
)

if response.status_code == 200:
    print("성공적으로 '윤현노' 사용자 데이터를 업데이트했습니다.")
else:
    print(f"업데이트 실패: {response.status_code}")
    print(response.json())
