import json
import os
from datetime import datetime
from src.utils.logger import global_logger

TRACKER_FILE = "logging/ai_predictions.json"

def record_prediction_snapshot(user_name: str, holdings: str, analysis_text: str):
    """
    역할 (Role): 
        AI가 "포트폴리오 맞춤 분석"에서 생성한 견해를 JSON 등 영구 스토리지에 스냅샷 형태로 기록해 둡니다.
        추후 백테스팅 모듈이나 별도의 평가 데몬을 통해 "n주일 전 AI의 예측 분석 적중률" 리포트를 생산하는 데 사용됩니다.
    
    입력 (Input):
        user_name (str): 대상 유저 이름
        holdings (str): 당시의 보유 종목 문자열
        analysis_text (str): 제미나이가 예측/분석한 결과 텍스트 전문
    """
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    
    timestamp = datetime.now().isoformat()
    record = {
        "timestamp": timestamp,
        "user_name": user_name,
        "holdings": holdings,
        # 나중에 분석하기 편하도록 텍스트 크기를 1000자 이내 스니펫으로 자름
        "analysis_snip": analysis_text[:1000] 
    }
    
    data = []
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
            
    data.append(record)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    global_logger.info(f"🤖 [AITracker] '{user_name}'님의 포트폴리오 분석 스냅샷이 {TRACKER_FILE} 에 안전하게 기록되었습니다.")
