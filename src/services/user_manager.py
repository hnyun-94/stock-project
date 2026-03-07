"""
사용자 관리 서비스 모듈.

Notion API를 활용하여 사용자가 생성한 데이터베이스(Database)에서
주식 리포트 수신을 희망하는 사용자 목록(이름, 이메일, 관심 키워드)을 불러옵니다.
"""

import os
from typing import List, Dict, Any, Optional
from src.models import User
from src.utils.logger import global_logger


def _parse_user_result(result: Dict[str, Any]) -> Optional[User]:
    """Notion 사용자 row를 User 모델로 파싱합니다."""
    props = result.get("properties", {})

    # 사용자 이름 추출 (Title 속성 파싱)
    name = "알 수 없음"
    if "이름" in props and props["이름"].get("title"):
        name = props["이름"]["title"][0]["text"]["content"]

    # 이메일 추출 (Email 속성 파싱)
    email = ""
    if "이메일" in props and props["이메일"].get("email"):
        email = props["이메일"]["email"]

    # 관심키워드 추출 (Multi-select 또는 쉼표 구분 텍스트 모두 대응)
    keywords = []
    if "관심키워드" in props:
        kw_prop = props["관심키워드"]
        if kw_prop.get("type") == "multi_select" and kw_prop.get("multi_select"):
            keywords = [k["name"].strip() for k in kw_prop["multi_select"]]
        elif kw_prop.get("type") == "rich_text" and kw_prop.get("rich_text"):
            raw_text = "".join(item["text"]["content"] for item in kw_prop["rich_text"])
            keywords = [k.strip() for k in raw_text.split(",") if k.strip()]

    telegram_id = None
    if "텔레그램ID" in props and props["텔레그램ID"].get("rich_text"):
        raw_tg = props["텔레그램ID"]["rich_text"]
        if raw_tg:
            telegram_id = raw_tg[0]["text"]["content"].strip()

    channels = ["email"]
    if "수신 채널" in props and props["수신 채널"].get("multi_select"):
        channels = [c["name"].lower() for c in props["수신 채널"]["multi_select"]]

    is_active = True
    if "수신여부" in props and props["수신여부"].get("select"):
        val = props["수신여부"]["select"]["name"].upper()
        is_active = val in ["O", "Y", "활성", "TRUE", "예"]

    holdings = []
    if "보유종목" in props:
        h_prop = props["보유종목"]
        if h_prop.get("type") == "multi_select" and h_prop.get("multi_select"):
            holdings = [h["name"].strip() for h in h_prop["multi_select"]]
        elif h_prop.get("type") == "rich_text" and h_prop.get("rich_text"):
            raw_text = "".join(item["text"]["content"] for item in h_prop["rich_text"])
            holdings = [h.strip() for h in raw_text.split(",") if h.strip()]

    alert_threshold = None
    if "긴급알림 임계치" in props and props["긴급알림 임계치"].get("number") is not None:
        alert_threshold = float(props["긴급알림 임계치"]["number"])

    if not is_active or not (email or telegram_id):
        return None

    return User(
        name=name,
        email=email,
        keywords=keywords,
        telegram_id=telegram_id,
        channels=channels,
        holdings=holdings,
        alert_threshold=alert_threshold,
    )

def fetch_active_users() -> List[User]:
    """Notion DB에서 알림 활성화(Active) 상태인 사용자의 정보를 가져옵니다.

    Returns:
        List[User]: 사용자의 정보가 담긴 User DTO 리스트
    """
    notion_token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_ID")
    
    if not notion_token or not db_id:
        global_logger.warning("Notion 설정(NOTION_TOKEN, NOTION_DATABASE_ID)이 누락되었습니다. 빈 리스트를 반환합니다.")
        return []

    try:
        # Notion DB 쿼리 (notion-client 3.0 버그 우회를 위해 httpx 직접 호출)
        import httpx
        users = []
        next_cursor = None
        while True:
            payload: Dict[str, Any] = {}
            if next_cursor:
                payload["start_cursor"] = next_cursor

            response = httpx.post(
                f"https://api.notion.com/v1/databases/{db_id}/query",
                headers={
                    "Authorization": f"Bearer {notion_token}",
                    "Notion-Version": "2022-06-28"
                },
                json=payload,
                timeout=30.0  # Notion API 타임아웃 30초 [REQ-Q02]
            )
            response.raise_for_status()
            data = response.json()

            for result in data.get("results", []):
                parsed_user = _parse_user_result(result)
                if parsed_user is not None:
                    users.append(parsed_user)

            if not data.get("has_more"):
                break
            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break

        return users

    except Exception as e:
        global_logger.error(f"Notion DB 사용자 조회 실패: {e}")
        return []
