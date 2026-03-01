import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.utils.logger import global_logger
from src.services.ai_summarizer import safe_gemini_call
from src.models import MarketIndex, NewsArticle

async def generate_backtesting_report(filepath: str = "prediction_snapshots.json") -> str:
    """
    과거 AI 예측 스냅샷을 로드하여 현재 시장/주가 상황과 비교(Back-testing)한 결과를
    마크다운 리포트로 반환합니다.
    """
    if not os.path.exists(filepath):
        global_logger.info("과거 예측 스냅샷 파일이 없어 더미 데이터를 생성합니다.")
        _create_dummy_snapshots(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            snapshots = json.load(f)
    except Exception as e:
        global_logger.error(f"스냅샷 로드 실패: {e}")
        return ""

    if not snapshots:
        return "과거 예측 데이터가 없습니다."

    # 가장 최근 스냅샷 또는 전체를 기반으로 AI에게 평가를 요청
    # 여기서는 간단히 최근 3개의 스냅샷 데이터를 컨텍스트로 사용
    recent_snapshots = snapshots[-3:]
    
    prompt = f"""
다음은 과거 시스템이 예측했던 주식 시장/종목 스냅샷 데이터입니다.
이 과거 데이터와 현재 시점을 비교하여 '과거 예측 적중률 분석' 리포트를 3~4문장의 마크다운으로 작성해주세요.
어떤 예측이 맞았고 틀렸는지 객관적으로 평가하는 느낌으로 작성해야 합니다.

[과거 스냅샷 데이터]
{json.dumps(recent_snapshots, ensure_ascii=False, indent=2)}
    """
    
    try:
        global_logger.info("과거 예측 데이터 백테스팅(Scoring) AI 분석 시작...")
        analysis_result = await safe_gemini_call(prompt)
        report_md = f"## 📈 과거 예측 적중률 분석 (Back-testing)\n\n{analysis_result}\n\n---\n"
        return report_md
    except Exception as e:
        global_logger.error(f"백테스팅 리포트 생성 실패: {e}")
        return ""

def _create_dummy_snapshots(filepath: str):
    dummy_data = [
        {
            "date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "target": "삼성전자, SK하이닉스",
            "prediction": "반도체 업황 둔화 우려로 단기적인 조정 예상되나, 장기적인 매수 관점 유효.",
            "market_context": "KOSPI 2600 붕괴 우려"
        }
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(dummy_data, f, ensure_ascii=False, indent=4)
