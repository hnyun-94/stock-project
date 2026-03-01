import os
import json
import logging
from typing import Dict, Any
from src.utils.logger import global_logger

FEEDBACK_FILE = "logging/user_feedback.json"

def record_feedback(user_name: str, score: int, comment: str = ""):
    """
    역할 (Role):
        AI 요약 리포트에 대한 사용자 피드백(평점, 코멘트)을 파일/DB에 적재합니다.
    입력 (Input):
        user_name (str): 평가를 남긴 구독자의 이름
        score (int): 평가 점수 (예: 1~5점)
        comment (str): 사용자의 추가 의견 (옵션)
    반환값 (Output): None
    """
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    
    from datetime import datetime
    record = {
        "timestamp": datetime.now().isoformat(),
        "user_name": user_name,
        "score": score,
        "comment": comment
    }
    
    data = []
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            global_logger.warning(f"피드백 파일 읽기 실패: {e}")
            
    data.append(record)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    global_logger.info(f"💌 [Feedback] {user_name}님의 피드백({score}점)이 기록되었습니다.")
    
def generate_feedback_link(user_name: str) -> str:
    """
    역할 (Role): 메일/텔레그램 하단에 첨부할 평가용 딥링크나 폼 URL을 동적으로 생성합니다.
    (실제 프로덕션에서는 서버의 Webhook 엔드포인트나 구글 폼 링크에 파라미터를 붙여 사용합니다.)
    """
    # 데모를 위해 임시 딥링크(Webhook Endpoint) 형태 문자열 반환
    base_url = "https://your-domain.com/api/feedback"
    return f"{base_url}?user={user_name}&score=5 (이 링크를 눌러 5점 만점을 주세요!)"
