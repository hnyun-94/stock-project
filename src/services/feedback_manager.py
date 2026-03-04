"""
피드백 관리 모듈.

이 모듈은 AI 요약 리포트에 대한 사용자 피드백(별점, 코멘트)을 기록하고,
HMAC-SHA256 서명이 포함된 보안 피드백 링크를 생성하는 기능을 제공합니다.

저장소: SQLite DB (기존 JSON 파일에서 마이그레이션됨) [REQ-P06]
"""

import os
import hmac
import hashlib
from src.utils.database import get_db
from src.utils.logger import global_logger


def record_feedback(user_name: str, score: int, comment: str = ""):
    """피드백을 SQLite DB에 기록합니다.

    Args:
        user_name: 평가자 이름
        score: 별점 (1~5)
        comment: 추가 코멘트
    """
    db = get_db()
    db.insert_feedback(user_name, score, comment)


def _create_signature(user_name: str, score: int) -> str:
    """
    역할 (Role):
        주어진 사용자 이름과 별점에 대해 HMAC-SHA256 서명을 생성합니다.
        feedback_server.py의 verify_signature()와 동일한 알고리즘을 사용하여
        서버에서 검증이 통과되도록 합니다.

    입력 (Input):
        user_name (str): 사용자 이름
        score (int): 별점 (1~5)

    반환값 (Output):
        str: HMAC-SHA256 hex digest 문자열
    """
    secret = os.getenv("WEBHOOK_SECRET", "")
    if not secret:
        global_logger.warning("⚠️ WEBHOOK_SECRET 환경변수가 설정되지 않았습니다. 피드백 링크 서명이 작동하지 않습니다.")
        return ""

    payload = f"{user_name}:{score}".encode('utf-8')
    return hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()


def generate_feedback_link(user_name: str, score: int = 5) -> str:
    """
    역할 (Role):
        특정 별점에 대한 HMAC-SHA256 서명이 포함된 피드백 URL을 생성합니다.
        feedback_server.py의 verify_signature()를 통과할 수 있는 유효한 서명이 포함됩니다.

    입력 (Input):
        user_name (str): 사용자 이름
        score (int): 별점 (기본값 5, 범위 1~5)

    반환값 (Output):
        str: HMAC 서명이 포함된 완전한 피드백 URL
             예: "https://your-domain.com/api/feedback?user=홍길동&score=5&signature=abc123..."
    """
    base_url = os.getenv("FEEDBACK_BASE_URL", "https://your-domain.com")
    signature = _create_signature(user_name, score)
    return f"{base_url}/api/feedback?user={user_name}&score={score}&signature={signature}"


def generate_feedback_links_html(user_name: str) -> str:
    """
    역할 (Role):
        이메일/알림 본문 하단에 삽입할 별점 1~5점 피드백 링크를 마크다운으로 생성합니다.
        사용자는 원하는 별점을 클릭하여 바로 평가할 수 있습니다.

    입력 (Input):
        user_name (str): 피드백 대상 사용자 이름

    반환값 (Output):
        str: 별점 링크가 포함된 마크다운 텍스트
             예: "⭐ [1점](url) | ⭐⭐ [2점](url) | ... | ⭐⭐⭐⭐⭐ [5점](url)"
    """
    star_emojis = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    links = []
    for score in range(1, 6):
        url = generate_feedback_link(user_name, score)
        links.append(f"{star_emojis[score - 1]} [{score}점]({url})")
    return " | ".join(links)
