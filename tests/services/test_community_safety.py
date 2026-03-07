"""
커뮤니티 안전 필터 단위 테스트 모듈.
"""

import unittest

from src.models import CommunityPost
from src.services.community_safety import (
    filter_community_posts,
    filter_community_posts_by_source,
    flatten_safe_community_posts,
)


class TestCommunitySafety(unittest.TestCase):
    """커뮤니티 소스 정책 및 제목 필터를 검증합니다."""

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


if __name__ == "__main__":
    unittest.main()
