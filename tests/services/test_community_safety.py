"""
커뮤니티 안전 필터 단위 테스트 모듈.
"""

import unittest

from src.models import CommunityPost
from src.services.community_safety import (
    filter_community_posts,
    filter_community_posts_by_source,
    flatten_safe_community_posts,
    get_enabled_community_sources,
)


class TestCommunitySafety(unittest.TestCase):
    """커뮤니티 소스 정책 및 제목 필터를 검증합니다."""

    def test_default_enabled_sources_include_stockplus(self):
        enabled = get_enabled_community_sources(raw_value="")

        self.assertIn("stockplus_insight", enabled)
        self.assertIn("reddit_wallstreetbets", enabled)

    def test_default_policy_skips_disabled_source(self):
        posts = [CommunityPost(title="[식갤] 일반 글", link="https://example.com")]
        result = filter_community_posts("dc_stock_gallery", posts)

        self.assertTrue(result.skipped)
        self.assertEqual(result.reason, "source_disabled")
        self.assertEqual(result.kept_posts, [])

    def test_high_risk_titles_are_filtered(self):
        posts = [
            CommunityPost(title="[WSB] 정상적인 수급 이야기", link="https://safe"),
            CommunityPost(title="[WSB] kill this stock now", link="https://risk"),
            CommunityPost(title="[WSB] 연락처 010-1234-5678", link="https://pii"),
        ]
        result = filter_community_posts("reddit_wallstreetbets", posts, max_items=5)

        self.assertFalse(result.skipped)
        self.assertEqual(len(result.kept_posts), 1)
        self.assertEqual(result.kept_posts[0].link, "https://safe")
        self.assertEqual(result.filtered_count, 2)

    def test_private_investment_titles_are_filtered(self):
        posts = [
            CommunityPost(title="[증권플러스 투표] AI 반도체 강세 지속", link="https://safe"),
            CommunityPost(title="[핫글] 수익률 120% 인증합니다", link="https://risk"),
            CommunityPost(title="[블라인드] 평단가 공개합니다", link="https://pii"),
        ]
        result = filter_community_posts(
            "stockplus_insight",
            posts,
            max_items=5,
            enabled_sources={"stockplus_insight"},
        )

        self.assertFalse(result.skipped)
        self.assertEqual(len(result.kept_posts), 1)
        self.assertEqual(result.kept_posts[0].link, "https://safe")
        self.assertEqual(result.filtered_count, 2)

    def test_blind_meta_is_preserved_when_source_enabled(self):
        posts = [
            CommunityPost(
                title="[블라인드] 반도체 체감은 아직 약함",
                link="https://blind",
                views="1.2만",
                likes="43",
                comments="112",
            )
        ]
        result = filter_community_posts(
            "blind_stock_lounge",
            posts,
            enabled_sources={"blind_stock_lounge"},
        )

        self.assertEqual(len(result.kept_posts), 1)
        self.assertEqual(result.kept_posts[0].source_id, "blind_stock_lounge")
        self.assertEqual(result.kept_posts[0].views, "1.2만")
        self.assertEqual(result.kept_posts[0].likes, "43")
        self.assertEqual(result.kept_posts[0].comments, "112")

    def test_flatten_safe_posts_merges_enabled_sources_only(self):
        results = filter_community_posts_by_source(
            {
                "dc_stock_gallery": [CommunityPost(title="[식갤] 제목", link="https://dc")],
                "reddit_wallstreetbets": [CommunityPost(title="[WSB] 시장 반등 기대", link="https://wsb")],
            }
        )
        merged = flatten_safe_community_posts(results)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].link, "https://wsb")

    def test_flatten_safe_posts_prioritizes_stockplus_over_reddit(self):
        results = filter_community_posts_by_source(
            {
                "reddit_wallstreetbets": [CommunityPost(title="[WSB] 시장 반등 기대", link="https://wsb")],
                "stockplus_insight": [CommunityPost(title="[증권플러스 투표] AI 반도체 강세 지속", link="https://stockplus")],
            },
            enabled_sources={"reddit_wallstreetbets", "stockplus_insight"},
        )
        merged = flatten_safe_community_posts(results, max_items=2)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].link, "https://stockplus")
        self.assertEqual(merged[1].link, "https://wsb")


if __name__ == "__main__":
    unittest.main()
