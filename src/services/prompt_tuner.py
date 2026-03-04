"""
자동 프롬프트 튜닝 모듈.

사용자 피드백(별점) 데이터를 분석하여 AI 프롬프트의 temperature와
스타일 지시어를 자동으로 조정합니다.

동작 원리:
1. 최근 30일간 평균 별점 조회
2. 별점 3.0 이하 → "개선 필요" → temperature 상향 + 스타일 지시어 추가
3. 별점 4.0 이상 → "양호" → 현재 설정 유지
4. 조정 내용을 로그에 기록하여 추적 가능

사용법:
    from src.services.prompt_tuner import get_tuning_adjustments

    adjustments = get_tuning_adjustments()
    # adjustments = {"temperature_delta": +0.1, "style_hint": "더 구체적인 데이터 포함"}

[Task 6.22, REQ-F06]
"""

from typing import Dict, Any
from src.utils.database import get_db
from src.utils.logger import global_logger


def get_tuning_adjustments() -> Dict[str, Any]:
    """피드백 데이터를 기반으로 프롬프트 조정값을 반환합니다.

    Returns:
        조정 딕셔너리:
        - temperature_delta: temperature 변경량 (-0.1 ~ +0.2)
        - style_hint: AI 프롬프트에 추가할 스타일 지시어
        - feedback_summary: 현재 피드백 상태 요약
    """
    db = get_db()
    avg_score = db.get_average_score(days=30)
    recent_feedbacks = db.get_recent_feedbacks(days=7)
    feedback_count = len(recent_feedbacks)

    adjustments = {
        "temperature_delta": 0.0,
        "style_hint": "",
        "feedback_summary": f"최근 30일 평균 {avg_score}점 ({feedback_count}건/7일)",
    }

    if feedback_count == 0:
        # 피드백 데이터 없음 → 기본값 유지
        adjustments["feedback_summary"] = "피드백 데이터 없음 (기본값 유지)"
        return adjustments

    if avg_score <= 2.0:
        # 매우 낮은 평가 → 공격적 조정
        adjustments["temperature_delta"] = 0.2
        adjustments["style_hint"] = (
            "주의: 사용자 만족도가 매우 낮습니다. "
            "더 구체적인 수치 데이터를 포함하고, "
            "투자 판단에 실질적으로 도움이 되는 실천적 포인트를 제시해주세요. "
            "추상적이거나 모호한 표현을 피하세요."
        )
        global_logger.warning(f"⚠️ [Tuner] 평균 별점 {avg_score} → 공격적 프롬프트 조정 적용")

    elif avg_score <= 3.0:
        # 낮은 평가 → 부드러운 조정
        adjustments["temperature_delta"] = 0.1
        adjustments["style_hint"] = (
            "사용자 피드백 반영: 분석의 구체성을 높이고, "
            "핵심 인사이트를 더 명확하게 전달해주세요."
        )
        global_logger.info(f"📊 [Tuner] 평균 별점 {avg_score} → 프롬프트 미세 조정 적용")

    elif avg_score >= 4.5:
        # 매우 높은 평가 → temperature 약간 낮춰 안정화
        adjustments["temperature_delta"] = -0.1
        adjustments["style_hint"] = ""
        global_logger.info(f"🌟 [Tuner] 평균 별점 {avg_score} → 현재 스타일 유지 (안정화)")

    else:
        # 보통 수준 → 조정 불필요
        global_logger.info(f"✅ [Tuner] 평균 별점 {avg_score} → 조정 불필요")

    return adjustments


def apply_tuning_to_prompt(base_prompt: str, adjustments: Dict[str, Any]) -> str:
    """스타일 지시어를 기존 프롬프트에 추가합니다.

    Args:
        base_prompt: 원본 프롬프트 텍스트
        adjustments: get_tuning_adjustments()의 반환값

    Returns:
        조정된 프롬프트 텍스트
    """
    style_hint = adjustments.get("style_hint", "")
    if not style_hint:
        return base_prompt

    return f"{base_prompt}\n\n[자동 품질 조정]\n{style_hint}"
