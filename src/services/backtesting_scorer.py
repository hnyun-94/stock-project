"""
백테스팅 채점 모듈.

과거 AI 예측 스냅샷을 SQLite DB에서 로드하여 현재 시장과 비교 분석합니다.
기존 JSON 파일 방식에서 SQLite로 마이그레이션되었습니다. [REQ-P06]
"""

import json
from src.utils.logger import global_logger
from src.services.ai_summarizer import safe_gemini_call
from src.utils.database import get_db


async def generate_backtesting_report() -> str:
    """과거 AI 예측 스냅샷을 DB에서 로드하여 백테스팅 리포트를 생성합니다.

    Returns:
        마크다운 형식의 백테스팅 리포트. 데이터 없으면 빈 문자열.
    """
    db = get_db()
    snapshots = db.get_recent_snapshots(limit=3)

    if not snapshots:
        global_logger.info("과거 예측 스냅샷이 없어 백테스팅을 건너뜁니다.")
        return ""

    prompt = f"""
다음은 과거 시스템이 예측했던 주식 시장/종목 스냅샷 데이터입니다.
이 과거 데이터와 현재 시점을 비교하여 '과거 예측 적중률 분석' 리포트를 3~4문장의 마크다운으로 작성해주세요.
어떤 예측이 맞았고 틀렸는지 객관적으로 평가하는 느낌으로 작성해야 합니다.

[과거 스냅샷 데이터]
{json.dumps(snapshots, ensure_ascii=False, indent=2)}
    """

    try:
        global_logger.info("과거 예측 데이터 백테스팅(Scoring) AI 분석 시작...")
        analysis_result = await safe_gemini_call(prompt)
        return f"## 📈 과거 예측 적중률 분석 (Back-testing)\n\n{analysis_result}\n\n---\n"
    except Exception as e:
        global_logger.error(f"백테스팅 리포트 생성 실패: {e}")
        return ""
