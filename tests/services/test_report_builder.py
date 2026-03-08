"""
구조화 리포트 조립기 단위 테스트 모듈.
"""

import json
import unittest
from datetime import datetime

from src.models import CommunityPost, MarketIndex, NewsArticle, SearchTrend
from src.services.report_builder import (
    _signal_news_items,
    _truncate_text,
    build_report_payload,
    extract_key_points,
)


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

    def test_signal_news_items_filters_portal_noise(self):
        news_items = [
            NewsArticle(
                title="언론사 선정언론사가 선정한 주요기사 혹은 심층기획 기사입니다.",
                link="https://noise1",
                summary="네이버 메인에서 보고 싶은 언론사를 구독하세요.",
            ),
            NewsArticle(
                title="AI 서버 투자 확대",
                link="https://signal1",
                summary="데이터센터 투자가 늘며 GPU와 HBM 수요가 살아나는 흐름입니다.",
            ),
        ]

        filtered = _signal_news_items(news_items, limit=2)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "AI 서버 투자 확대")

    def test_signal_news_items_filters_low_signal_shortcuts(self):
        news_items = [
            NewsArticle(
                title="Keep에 바로가기",
                link="https://noise-shortcut",
            ),
            NewsArticle(
                title="AI 서버 투자 확대",
                link="https://signal1",
                summary="데이터센터 투자 확대와 GPU 수요 회복이 이어지고 있습니다.",
            ),
        ]

        filtered = _signal_news_items(news_items, limit=2)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "AI 서버 투자 확대")

    def test_truncate_text_keeps_complete_sentence_without_ellipsis(self):
        text = (
            "시장 판단은 지수 숫자 하나보다 수급, 환율, 거시 변수, 핵심 뉴스가 같은 방향을 가리키는지 함께 보는 것이 더 중요합니다. "
            "그래서 지금은 후속 숫자 확인이 먼저입니다."
        )

        truncated = _truncate_text(text, 70)

        self.assertNotIn("…", truncated)
        self.assertTrue(truncated.endswith("중요합니다."))

    def test_build_report_payload_creates_value_focused_sections(self):
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
                {"keyword": "AI", "briefing_md": "### AI\n- 수요가 재확대되고 있습니다.\n- 반도체 체인이 재평가됩니다."},
                {"keyword": "인공지능", "briefing_md": "### 인공지능\n- GPU 수요가 이어집니다."},
            ],
            theme_news_map={
                "AI": [NewsArticle(title="AI 서버 투자 확대", link="https://theme1")],
                "인공지능": [NewsArticle(title="GPU 수요 확대", link="https://theme2")],
            },
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
            holding_news_map={
                "삼성전자": [
                    NewsArticle(
                        title="삼성전자 HBM 공급 확대 기대",
                        link="https://holding1",
                        summary="HBM 공급 확대 기대가 살아나고 있습니다.",
                    )
                ]
            },
            community_posts=[CommunityPost(title="개장 전엔 AI 반도체가 핵심이라는 토론", link="https://community1")],
            recent_report_rows=recent_rows,
            weekly_report_rows=recent_rows,
            monthly_report_rows=recent_rows,
            connector_success_rate_7d={"opendart": 1.0},
            connector_success_rate_30d={"opendart": 0.95},
            avg_feedback_score_30d=4.2,
            avg_accuracy_30d=0.67,
            connector_daily_rollups_7d=[
                {
                    "day": "2026-03-07",
                    "source_id": "opendart",
                    "sample_count": 3,
                    "success_count": 3,
                    "failure_count": 0,
                    "skip_count": 0,
                    "success_rate": 1.0,
                    "avg_latency_ms": 120,
                },
                {
                    "day": "2026-03-07",
                    "source_id": "fred",
                    "sample_count": 2,
                    "success_count": 1,
                    "failure_count": 1,
                    "skip_count": 0,
                    "success_rate": 0.5,
                    "avg_latency_ms": 4200,
                },
            ],
            recent_connector_failures_7d=[
                {"source_id": "fred", "timestamp": "2026-03-07T08:00:00", "detail": "timeout"}
            ],
            connector_metric_trends_7d=[
                {
                    "source_id": "opendart",
                    "metric_key": "opendart:earnings",
                    "latest_day": "2026-03-07",
                    "latest_value": 6.0,
                    "prev_1d_value": 4.0,
                    "prev_7d_value": 2.0,
                    "delta_1d": 2.0,
                    "delta_7d": 4.0,
                    "pct_change_1d": 0.5,
                    "pct_change_7d": 2.0,
                },
                {
                    "source_id": "opendart",
                    "metric_key": "opendart:financing",
                    "latest_day": "2026-03-07",
                    "latest_value": 1.0,
                    "prev_1d_value": 1.0,
                    "prev_7d_value": 1.0,
                    "delta_1d": 0.0,
                    "delta_7d": 0.0,
                    "pct_change_1d": 0.0,
                    "pct_change_7d": 0.0,
                },
                {
                    "source_id": "fred",
                    "metric_key": "fred:series_value_x100",
                    "latest_day": "2026-03-07",
                    "latest_value": 450.0,
                    "prev_1d_value": 445.0,
                    "prev_7d_value": 430.0,
                    "delta_1d": 5.0,
                    "delta_7d": 20.0,
                    "pct_change_1d": 0.0112,
                    "pct_change_7d": 0.0465,
                },
            ],
            reference_time=datetime.fromisoformat("2026-03-07T08:45:00+09:00"),
        )

        self.assertEqual(payload["title"], "🌤️ 오늘의 주식 인사이트 리포트")
        self.assertEqual(payload["reliability_badge"]["label"], "높음")
        self.assertEqual(payload["reliability_badge"]["gauge"], "█████████░")
        self.assertEqual(len(payload["headline_changes"]), 3)
        self.assertEqual(payload["decision_tiles"][0]["label"], "시장 톤")
        self.assertEqual(payload["market_scoreboard"]["headers"][0], "항목")
        self.assertTrue(any(row[0] == "시장 심리" and "█" in row[1] for row in payload["market_scoreboard"]["rows"]))
        self.assertTrue(any(row[0] == "검색 관심" and "█" in row[1] for row in payload["market_scoreboard"]["rows"]))
        self.assertEqual(len(payload["insight_lenses"]), 3)
        self.assertEqual(payload["insight_lenses"][0]["title"], "경제 온도")
        self.assertEqual(payload["insight_lenses"][1]["title"], "자금 흐름")
        self.assertEqual(len(payload["time_windows"]), 4)
        self.assertIsNotNone(payload["quick_take"])
        self.assertEqual(payload["quick_take"]["related_links"][0]["url"], "https://news1")
        self.assertIsNotNone(payload["session_issue_section"])
        self.assertEqual(payload["session_issue_section"]["title"], "국장 개장 전 공통 이슈")
        self.assertTrue(payload["session_issue_section"]["related_links"])
        self.assertIsNotNone(payload["data_quality_section"])
        self.assertEqual(payload["data_quality_section"]["table_headers"][0], "날짜")
        self.assertIn("█", payload["data_quality_section"]["table_rows"][0][2])
        self.assertIn("· 빠름", payload["data_quality_section"]["table_rows"][0][3])
        self.assertEqual(payload["domain_signal_sections"][0]["title"], "OpenDART 공시 흐름")
        self.assertIn("▁", payload["domain_signal_sections"][0]["table_rows"][0][1])
        self.assertTrue(payload["domain_signal_sections"][0]["table_rows"][0][2].startswith("▲"))
        self.assertEqual(payload["theme_sections"][0]["keyword"], "인공지능(AI)")
        self.assertIn(
            payload["theme_sections"][0]["related_links"][0]["url"],
            {"https://theme1", "https://theme2"},
        )
        self.assertEqual(payload["holding_sections"][0]["holding"], "삼성전자")
        self.assertEqual(payload["holding_sections"][0]["related_links"][0]["url"], "https://holding1")
        self.assertEqual(snapshot["holding_actions"]["삼성전자"], "유지")
        self.assertIn("인공지능(AI)", snapshot["focus_keywords"])
        self.assertTrue(any(item["term"] == "AI" for item in payload["glossary"]))
        self.assertTrue(any(item["term"] == "OpenDART" for item in payload["glossary"]))
        self.assertTrue(payload["theme_sections"][0]["why_it_matters"])
        self.assertTrue(payload["theme_sections"][0]["watch_points"])
        self.assertTrue(payload["holding_sections"][0]["why_it_matters"])
        self.assertTrue(payload["holding_sections"][0]["watch_points"])
        self.assertEqual(payload["learning_card"]["term"], "AI")

    def test_build_report_payload_filters_failure_strings_from_sections(self):
        payload, _ = build_report_payload(
            user_name="홍길동",
            market_summary_md="시장 요약 생성 실패: RetryError[ClientError]",
            market_indices=[MarketIndex(name="KOSPI", value="2650.10", change="", investor_summary="외국인 순매수")],
            market_news=[NewsArticle(title="AI 서버 투자 확대", link="https://news1", summary="AI 투자 확대가 이어진다는 해석입니다.")],
            datalab_trends=[SearchTrend(keyword="AI", traffic="92")],
            theme_sections=[
                {"keyword": "AI", "briefing_md": "테마 브리핑 생성 실패 (AI): RetryError[ClientError]"}
            ],
            theme_news_map={
                "AI": [NewsArticle(title="GPU 수요 확대", link="https://theme1", summary="데이터센터 투자 확대로 GPU 수요가 늘고 있습니다.")]
            },
            sentiment_score=7,
            sentiment_label="🟡 중립",
            holding_insights=[],
            holding_news_map={},
            community_posts=[],
            recent_report_rows=[],
            weekly_report_rows=[],
            monthly_report_rows=[],
            connector_success_rate_7d={"opendart": 1.0},
            connector_success_rate_30d={"opendart": 1.0},
            avg_feedback_score_30d=0,
            avg_accuracy_30d=0,
            connector_daily_rollups_7d=[
                {
                    "day": "2026-03-07",
                    "source_id": "opendart",
                    "sample_count": 1,
                    "success_count": 1,
                    "failure_count": 0,
                    "skip_count": 0,
                    "success_rate": 1.0,
                    "avg_latency_ms": 100,
                }
            ],
            recent_connector_failures_7d=[],
            connector_metric_trends_7d=[],
        )

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("RetryError", serialized)
        self.assertNotIn("생성 실패", serialized)
        self.assertIn("GPU 수요 확대", serialized)
        self.assertIn("table_headers", serialized)

    def test_build_report_payload_differentiates_holding_watch_points(self):
        payload, _ = build_report_payload(
            user_name="홍길동",
            market_summary_md="## 📈 오늘의 시장 요약\nAI 반도체와 메모리 수요가 유지되고 있습니다.",
            market_indices=[],
            market_news=[],
            datalab_trends=[],
            theme_sections=[],
            theme_news_map={},
            sentiment_score=5,
            sentiment_label="🟡 중립",
            holding_insights=[
                {"holding": "삼성전자", "stance": "관찰", "summary": "최근 이슈는 옵션 가이드이며 톤은 혼조입니다.", "action": ""},
                {"holding": "엔비디아", "stance": "관찰", "summary": "최근 이슈는 옵션 가이드이며 톤은 혼조입니다.", "action": ""},
            ],
            holding_news_map={
                "삼성전자": [
                    NewsArticle(title="삼성전자 HBM 공급 확대", link="https://s1", summary="HBM 납품 확대 기대가 있습니다.")
                ],
                "엔비디아": [
                    NewsArticle(title="엔비디아 데이터센터 매출 성장", link="https://n1", summary="GPU 출하와 데이터센터 매출이 핵심입니다.")
                ],
            },
            community_posts=[],
            recent_report_rows=[],
            weekly_report_rows=[],
            monthly_report_rows=[],
            connector_success_rate_7d={},
            connector_success_rate_30d={},
            avg_feedback_score_30d=0,
            avg_accuracy_30d=0,
            connector_daily_rollups_7d=[],
            recent_connector_failures_7d=[],
            connector_metric_trends_7d=[],
        )

        samsung, nvidia = payload["holding_sections"]
        self.assertIn("HBM 납품 확대", samsung["watch_points"][0])
        self.assertIn("GPU 출하", nvidia["watch_points"][0])
        self.assertNotIn("옵션 가이드", samsung["summary"])

    def test_build_report_payload_keeps_holding_watch_points_from_cross_contamination(self):
        payload, _ = build_report_payload(
            user_name="홍길동",
            market_summary_md="## 📈 오늘의 시장 요약\n메모리 업종과 AI 수요 회복 기대가 이어집니다.",
            market_indices=[],
            market_news=[],
            datalab_trends=[],
            theme_sections=[],
            theme_news_map={},
            sentiment_score=3,
            sentiment_label="🟡 중립",
            holding_insights=[
                {"holding": "SK하이닉스", "stance": "관찰", "summary": "최근 이슈는 옵션 가이드이며 톤은 혼조입니다.", "action": ""},
            ],
            holding_news_map={
                "SK하이닉스": [
                    NewsArticle(
                        title="삼성전자·SK하이닉스 동반 강세…HBM 기대 재부각",
                        link="https://s1",
                        summary="HBM 가격과 고객사 발주 기대가 다시 부각됩니다.",
                    )
                ],
            },
            community_posts=[],
            recent_report_rows=[],
            weekly_report_rows=[],
            monthly_report_rows=[],
            connector_success_rate_7d={},
            connector_success_rate_30d={},
            avg_feedback_score_30d=0,
            avg_accuracy_30d=0,
            connector_daily_rollups_7d=[],
            recent_connector_failures_7d=[],
            connector_metric_trends_7d=[],
        )

        sk_hynix = payload["holding_sections"][0]
        self.assertIn("HBM ASP", sk_hynix["watch_points"][0])
        self.assertNotIn("파운드리 수율", " ".join(sk_hynix["watch_points"]))


if __name__ == "__main__":
    unittest.main()
