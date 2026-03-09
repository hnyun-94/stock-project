"""
국내 커뮤니티 수집 파서 회귀 테스트 모듈.
"""

import unittest

from src.crawlers.community import (
    _build_stockplus_poll_post,
    _extract_stockplus_poll_candidates,
)
from src.crawlers.dynamic_community import _extract_blind_metric


class TestCommunityCollection(unittest.TestCase):
    """증권플러스/블라인드 파서의 핵심 규칙을 검증합니다."""

    def test_extract_stockplus_poll_candidates_only_keeps_poll_articles(self):
        html = """
        <html>
          <body>
            <a href="/articles/6276">[개미의 선택] 루닛 반등, 계속될까?</a>
            <a href="/articles/6277">[개미의 핫글] 수익금 1.9억 인증</a>
            <a href="/articles/6278">일반 기사</a>
          </body>
        </html>
        """

        candidates = _extract_stockplus_poll_candidates(html, max_items=3)

        self.assertEqual(candidates, [("[개미의 선택] 루닛 반등, 계속될까?", "https://insight.stockplus.com/articles/6276")])

    def test_build_stockplus_poll_post_extracts_ratios_and_participants(self):
        html = """
        <html>
          <body>
            <p>2,554명이 참여</p>
            <p>77.6%는 계속된다!</p>
            <p>22.4%는 멈춘다!</p>
          </body>
        </html>
        """

        post = _build_stockplus_poll_post(
            "[개미의 선택] 루닛 반등, 계속될까?",
            html,
            "https://insight.stockplus.com/articles/6276",
        )

        self.assertEqual(post.source_id, "stockplus_insight")
        self.assertEqual(post.views, "2,554")
        self.assertIn("77.6% / 22.4%", post.title)
        self.assertIn("2,554명 참여", post.title)

    def test_extract_blind_metric_reads_numeric_meta(self):
        text = "조회수 1.2만 좋아요 43 댓글 112"

        self.assertEqual(_extract_blind_metric(text, "조회수"), "1.2만")
        self.assertEqual(_extract_blind_metric(text, "좋아요"), "43")
        self.assertEqual(_extract_blind_metric(text, "댓글"), "112")


if __name__ == "__main__":
    unittest.main()
