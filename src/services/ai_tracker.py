"""
AI 예측 스냅샷 기록 모듈.

포트폴리오 맞춤 분석 결과를 SQLite DB에 저장합니다.
백테스팅 모듈에서 과거 예측 적중률을 분석할 때 사용됩니다.

기존 JSON 파일 방식에서 SQLite로 마이그레이션되었습니다. [REQ-P06]
"""

from src.utils.database import get_db


def record_prediction_snapshot(user_name: str, holdings: str, analysis_text: str):
    """AI 포트폴리오 분석 스냅샷을 DB에 기록합니다.

    Args:
        user_name: 대상 유저 이름
        holdings: 보유 종목 문자열
        analysis_text: AI 분석 텍스트 (최대 1000자로 자름)
    """
    db = get_db()
    db.insert_snapshot(user_name, holdings, analysis_text)
