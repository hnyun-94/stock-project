import os
from typing import Dict, Any, Optional
from src.utils.logger import global_logger
import re

# 메모리 캐시 딕셔너리
_PROMPT_CACHE: Dict[str, Dict[str, Any]] = {}

def fetch_prompts_from_notion() -> None:
    """
    Notion API를 호출하여 활성화(IsActive)된 프롬프트 목록을 한 번에 메모리에 캐싱합니다.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_PROMPT_DB_ID")
    
    if not notion_token or not db_id:
        global_logger.warning("NOTION_PROMPT_DB_ID 또는 TOKEN이 설정되지 않았습니다. 기본 로컬 프롬프트를 사용합니다.")
        return

    try:
        import httpx
        response = httpx.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28"
            },
            json={},
            timeout=30.0  # Notion API 타임아웃 30초 [REQ-Q02]
        )
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            global_logger.warning("Notion 프롬프트 DB가 비어있습니다. 로컬 폴백을 사용합니다.")
            return
            
        loaded_count = 0
        for row in results:
            props = row.get("properties", {})
            
            # 1. 활성화 상태 체크 (IsActive 체크박스) -> 컬럼이 아예 없으면 일단 패스
            is_active_prop = props.get("IsActive", {})
            if is_active_prop.get("type") == "checkbox" and not is_active_prop.get("checkbox"):
                continue  # 체크되지 않은 프롬프트는 스킵
                
            # 2. Title 추출
            title_prop = props.get("Title", {})
            if title_prop.get("type") == "title" and title_prop.get("title"):
                title = title_prop["title"][0]["text"]["content"]
            else:
                continue
                
            # 3. Content 추출
            content_prop = props.get("Content", {})
            if content_prop.get("type") == "rich_text" and content_prop.get("rich_text"):
                content = "".join([t["text"]["content"] for t in content_prop["rich_text"]])
            else:
                continue
                
            # 4. 부가적인 메타 옵션들
            model = "gemini-1.5-flash"  # 기본값
            model_prop = props.get("Model", {})
            if model_prop.get("type") == "select" and model_prop.get("select"):
                model = model_prop["select"]["name"]
                
            temperature = 0.5  # 기본값
            temp_prop = props.get("Temperature", {})
            if temp_prop.get("type") == "number" and temp_prop.get("number") is not None:
                temperature = float(temp_prop["number"])
                
            # 5. 메모리에 적재
            _PROMPT_CACHE[title] = {
                "content": content,
                "model": model,
                "temperature": temperature
            }
            loaded_count += 1
            
        global_logger.info(f"✨ Notion에서 {loaded_count}개의 동적 프롬프트를 성공적으로 로드했습니다.")
        
    except Exception as e:
        global_logger.error(f"Notion 프롬프트 DB 연동 실패 (로컬 Fallback을 사용합니다): {e}")

def get_cached_prompt(title: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    메모리 캐시에서 프롬프트 데이터(텍스트, 모델 등)를 꺼내서 가공 반환합니다.
    없으면 None을 리턴하여 로컬 마크다운 fallback을 타게 합니다.
    """
    if title not in _PROMPT_CACHE:
        return None
        
    prompt_data = _PROMPT_CACHE[title].copy()
    template_str = prompt_data["content"]
    
    # 전달받은 kwargs(예: keyword, context_news 등)를 본문에 치환 (에러 방어 포함)
    try:
        formatted_content = template_str.format(**kwargs)
        prompt_data["content"] = formatted_content
        return prompt_data
    except Exception as e:
        global_logger.warning(f"프롬프트 '{title}' 변수 포매팅 실패. (주입된 데이터와 {{}}개수가 안 맞을 수 있습니다): {e}")
        return None
