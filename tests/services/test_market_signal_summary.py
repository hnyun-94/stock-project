"""
시장 신호 통계/요약 생성 테스트 모듈.
"""

import unittest

from src.services.market_signal_summary import (
    PricePoint,
    build_index_signal,
    build_market_snapshot,
    render_market_snapshot_markdown,
    to_price_points,
)


class TestMarketSignalSummary(unittest.TestCase):
    """시장 시그널 계산 테스트."""

    def test_build_index_signal_with_uptrend_data(self):
        points = [
            PricePoint(date=f"2026-02-{day:02d}", close=100 + day)
            for day in range(1, 27)
        ]
        signal = build_index_signal("KOSPI", points)

        self.assertEqual(signal.symbol, "KOSPI")
        self.assertEqual(signal.trend_label, "uptrend")
        self.assertIsNotNone(signal.change_1d_pct)
        self.assertIsNotNone(signal.change_5d_pct)
        self.assertIsNotNone(signal.volatility_20d_pct)
        self.assertGreater(signal.change_1d_pct, 0)
        self.assertGreater(signal.change_5d_pct, 0)

    def test_market_snapshot_markdown_contains_expected_sections(self):
        index_series = {
            "KOSPI": [
                PricePoint(date="2026-03-01", close=2500.0),
                PricePoint(date="2026-03-02", close=2525.0),
                PricePoint(date="2026-03-03", close=2510.0),
                PricePoint(date="2026-03-04", close=2530.0),
                PricePoint(date="2026-03-05", close=2545.0),
                PricePoint(date="2026-03-06", close=2555.0),
            ],
            "S&P500": [
                PricePoint(date="2026-03-01", close=5000.0),
                PricePoint(date="2026-03-02", close=4980.0),
                PricePoint(date="2026-03-03", close=4995.0),
                PricePoint(date="2026-03-04", close=5010.0),
                PricePoint(date="2026-03-05", close=5030.0),
                PricePoint(date="2026-03-06", close=5040.0),
            ],
        }
        snapshot = build_market_snapshot(
            index_series=index_series,
            event_counts={"KR": 12, "US": 21},
            keyword_trend_change_pct=8.4,
        )
        markdown = render_market_snapshot_markdown(snapshot)

        self.assertIn("정량 통계 스냅샷", markdown)
        self.assertIn("KOSPI", markdown)
        self.assertIn("S&P500", markdown)
        self.assertIn("공시 이벤트 카운트", markdown)
        self.assertIn("키워드 관심도 변화율", markdown)

    def test_to_price_points_filters_invalid_rows(self):
        rows = [
            {"date": "2026-03-01", "close": "2500.1"},
            {"date": "2026-03-02", "close": 2510.2},
            {"date": "2026-03-03", "close": None},
            {"date": "", "close": 2520.3},
            {"date": "2026-03-05", "close": "not-a-number"},
        ]

        points = to_price_points(rows)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].date, "2026-03-01")
        self.assertAlmostEqual(points[1].close, 2510.2)


if __name__ == "__main__":
    unittest.main()
