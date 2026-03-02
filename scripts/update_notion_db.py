import os
import requests

def get_env():
    env = {}
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env[k] = v.strip("\"'\n")
    return env

env = get_env()
token = env.get("NOTION_TOKEN")
db_id = env.get("NOTION_PROMPT_DB_ID")
headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

print("DB ID:", db_id)

try:
    res = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=headers, timeout=10)
    data = res.json()
    props = data.get("properties", {})
    title_prop_name = [name for name, prop in props.items() if prop["type"] == "title"][0]
    
    print("Title prop name is", title_prop_name)
    
    # 이메일 등 불필요한 속성 제거
    patch_data = {
        "properties": {
            title_prop_name: {"name": "Title", "title": {}},
            "Content": {"name": "Content", "rich_text": {}},
            "IsActive": {"name": "IsActive", "checkbox": {}},
            "Model": {"name": "Model", "select": {"options": [{"name": "gemini-1.5-flash", "color": "blue"}, {"name": "gemini-2.0-flash", "color": "green"}]}},
            "Temperature": {"name": "Temperature", "number": {"format": "number"}}
        }
    }
    
    # 기존에 있었던 컬럼들 (에러가 나지 않도록) 제거 (None 선언)
    for prop_name in ["이메일", "관심키워드", "수신여부", "이름"]:
        if prop_name in props and prop_name != title_prop_name:
            patch_data["properties"][prop_name] = None
            
    res2 = requests.patch(f"https://api.notion.com/v1/databases/{db_id}", headers=headers, json=patch_data, timeout=10)
    print("Schema Update Status:", res2.status_code)
    
except Exception as e:
    print("Error:", e)
