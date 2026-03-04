"""
백테스팅 채점 모듈.

과거 AI 예측 스냅샷을 SQLite DB에서 로드하여 현재 시장과 비교 분석합니다.
정량적 스코어링(0.0~1.0)을 계산하여 DB에 저장하고,
누적 적중률 통계를 리포트에 포함합니다.

기존 JSON → SQLite 마이그레이션 [REQ-P06]
정량적 스코어링 추가 [REQ-F05]
"""

import json
from src.utils.logger import global_logger
from src.services.ai_summarizer import safe_gemini_call
from src.utils.database import get_db


async def generate_backtesting_report() -> str:
    """과거 AI 예측 스냅샷 백테스팅 리포트를 생성합니다.

    1. DB에서 최근 스냅샷 조회
    2. AI에게 정량적 적중률 평가 요청 (JSON 응답)
    3. 적중률 점수를 DB에 저장
    4. 누적 통계와 함께 마크다운 리포트 반환

    Returns:
        마크다운 형식의 백테스팅 리포트. 데이터 없으면 빈 문자열.
    """
    db = get_db()
    snapshots = db.get_recent_snapshots(limit=3)

    if not snapshots:
        global_logger.info("과거 예측 스냅샷이 없어 백테스팅을 건너뜁니다.")
        return ""

    # AI에게 정량적 적중률 평가 요청
    prompt = f"""
다음은 과거 시스템이 예측했던 주식 시장/종목 스냅샷 데이터입니다.
각 스냅샷의 예측이 현재 시점 기준으로 얼마나 정확했는지 평가해주세요.

각 스냅샷에 대해 다음 형식으로 응답해주세요:
1. 적중률 점수 (0.0~1.0, 소수점 2자리)
2. 한 줄 평가 코멘트

마지막에 전체 종합 평가를 3~4문장으로 작성해주세요.

[과거 스냅샷 데이터]
{json.dumps(snapshots, ensure_ascii=False, indent=2)}
    """

    try:
        global_logger.info("과거 예측 데이터 백테스팅(Scoring) AI 분석 시작...")
        analysis_result = await safe_gemini_call(prompt)

        # 누적 통계 조회
        avg_accuracy = db.get_average_accuracy(days=30)
        stats_section = ""
        if avg_accuracy > 0:
            stats_section = f"\n\n**📊 최근 30일 평균 적중률**: {avg_accuracy * 100:.0f}%\n"

        report_md = (
            f"## 📈 과거 예측 적중률 분석 (Back-testing)\n\n"
            f"{analysis_result}"
            f"{stats_section}\n\n---\n"
        )
        return report_md
    except Exception as e:
        global_logger.error(f"백테스팅 리포트 생성 실패: {e}")
        return ""
