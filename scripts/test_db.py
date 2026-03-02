"""
이 모듈은 Notion API와 연동하여 특정 Notion 데이터베이스의 구조를 조회하고,
그 안에 저장된 사용자 데이터를 읽어오는 예제 스크립트입니다.

환경 변수에서 Notion API 토큰과 데이터베이스 ID를 로드하고,
`notion_client` 라이브러리를 사용하여 Notion 클라이언트를 초기화합니다.
초기화된 클라이언트를 통해 데이터베이스의 속성(스키마)을 확인하고,
데이터베이스 내부에 존재하는 사용자("Active User") 데이터를 쿼리하여
각 사용자의 이름, 이메일, 관심 키워드 정보를 추출하고 콘솔에 출력합니다.

주요 기능:
- .env 파일에서 Notion API 키 및 데이터베이스 ID 로드.
- Notion 데이터베이스의 메타데이터(속성) 조회.
- Notion 데이터베이스 내의 페이지(데이터 로우) 쿼리.
- 쿼리된 페이지에서 특정 속성(이름, 이메일, 관심 키워드) 추출 및 출력.

오류 발생 시 Notion API 응답 에러 또는 기타 예외를 처리합니다.
"""
import os
import pprint
from dotenv import load_dotenv
from notion_client import Client, APIResponseError

load_dotenv()
token = os.getenv('NOTION_TOKEN')
db_id = os.getenv('NOTION_DATABASE_ID')

print(f"Token (앞 10자리): {token[:10]}... ({len(token)} chars)" if token else "Token: None")
print(f"DB ID: {db_id}")

if not token or not db_id:
    print("환경변수 누락됨")
    exit(1)

notion = Client(auth=token)

try:
    print("\n[1단계] Database 속성(스키마) 조회 시도 중...")
    res = notion.databases.retrieve(database_id=db_id)
    print("✅ 데이터베이스 접근 성공! 읽어온 컬럼들:")
    props = res.get('properties', {})
    for k, v in props.items():
        print(f"  - {k} ({v.get('type')})")
        
    print("\n[2단계] 내부에 데이터(Active User)가 있는지 조회 시도 중...")
    import httpx
    response = httpx.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28"
        },
        json={}
    )
    response.raise_for_status()
    query_res = response.json()
    results = query_res.get('results', [])
    print(f"총 {len(results)}명의 데이터 로우가 존재합니다.")
    
    for row in results:
        props = row.get("properties", {})
        
        name = "이름없음"
        if "이름" in props and props["이름"].get("title"):
             name = props["이름"]["title"][0]["text"]["content"]
             
        email = ""
        if "이메일" in props and props["이메일"].get("email"):
             email = props["이메일"]["email"]
             
        keywords = []
        if "관심 키워드" in props and props["관심 키워드"].get("rich_text"):
             text = props["관심 키워드"]["rich_text"][0]["text"]["content"]
             keywords = [k.strip() for k in text.split(",")]
             
        print(f"  > 사용자 발견: {name} (이메일: {email}, 키워드: {keywords})")
        
except APIResponseError as e:
    print(f"❌ Notion API 에러 발생:")
    print(f"  - 코드: {e.code}")
    print(f"  - 이유: {getattr(e, 'message', str(e))}")
except Exception as e:
    print(f"❌ 기타 에러 발생: {e}")
