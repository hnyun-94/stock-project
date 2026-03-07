"""
구조화 리포트 조립기 단위 테스트 모듈.
"""

import json
import unittest

from src.models import MarketIndex, NewsArticle, SearchTrend
from src.services.report_builder import build_report_payload, extract_key_points


class TestReportBuilder(unittest.TestCase):
    """리포트 payload 생성 규칙을 검증합니다."""

    def test_extract_key_points_limits_verbose_markdown(self):
        markdown_text = """
### 제목

첫 번째 문장입니다. 두 번째 문장입니다.
- 세 번째 포인트
- 네 번째 포인트
"""
        points = extract_key_points(markdown_text, max_items=3)

        self.assertEqual(len(points), 3)
        self.assertIn("첫 번째 문장입니다.", points[0])

    def test_build_report_payload_creates_headlines_and_windows(self):
        previous_snapshot = {
            "market_regime": "관망",
            "sentiment_score": -30,
            "focus_keywords": ["2차전지"],
            "holding_actions": {"삼성전자": "관찰"},
        }
        recent_rows = [
            {
                "headline": "이전 리포트",
                "timestamp": "2026-03-06T09:00:00",
                "snapshot_json": json.dumps(previous_snapshot, ensure_ascii=False),
            }
        ]

        payload, snapshot = build_report_payload(
            user_name="홍길동",
            market_summary_md="## 📈 오늘의 시장 요약\nAI와 반도체가 반등을 주도했습니다. 수급은 관망에서 개선으로 이동했습니다.",
            market_indices=[
                MarketIndex(name="KOSPI", value="2650.10", change="", investor_summary="외국인 순매수"),
                MarketIndex(name="KOSDAQ", value="860.22", change="", investor_summary="기관 순매수"),
            ],
            market_news=[NewsArticle(title="반도체 업종 반등", link="https://news1")],
            datalab_trends=[SearchTrend(keyword="AI", traffic="92")],
            theme_sections=[
                {"keyword": "AI", "briefing_md": "### AI\n- 수요가 재확대되고 있습니다.\n- 반도체 체인이 재평가됩니다."}
            ],
            sentiment_score=15,
            sentiment_label="🟡 중립",
            holding_insights=[
                {
                    "holding": "삼성전자",
                    "stance": "유지",
                    "summary": "HBM과 파운드리 수요가 동시 반영됩니다.",
                    "action": "단기 변동성보다 수요 추세를 확인합니다.",
                }
            ],
            recent_report_rows=recent_rows,
            weekly_report_rows=recent_rows,
            monthly_report_rows=recent_rows,
            connector_success_rate_7d={"opendart": 1.0},
            connector_success_rate_30d={"opendart": 0.95},
            avg_feedback_score_30d=4.2,
            avg_accuracy_30d=0.67,
        )

        self.assertEqual(payload["title"], "🌤️ 오늘의 주식 인사이트 리포트")
        self.assertEqual(len(payload["headline_changes"]), 3)
        self.assertEqual(len(payload["time_windows"]), 4)
        self.assertEqual(payload["holding_sections"][0]["holding"], "삼성전자")
        self.assertEqual(snapshot["holding_actions"]["삼성전자"], "유지")
        self.assertIn("AI", snapshot["focus_keywords"])


if __name__ == "__main__":
    unittest.main()
