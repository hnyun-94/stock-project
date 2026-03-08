"""
토픽 뉴스 수집 보강 로직 테스트 모듈.
"""

import unittest

from src.models import CommunityPost, NewsArticle
from src.services.topic_news import filter_topic_news, select_topic_community_posts


class TestTopicNews(unittest.TestCase):
    """토픽 적합도 필터와 커뮤니티 선별 규칙을 검증합니다."""

    def test_filter_topic_news_prioritizes_relevant_articles_for_sp500(self):
        news_items = [
            NewsArticle(
                title="UKR AI NE INTERNATIONAL WOMEN'SDAY 특집",
                link="https://noise.example.com/1",
                summary="미국 증시와 무관한 글로벌 캠페인 기사입니다.",
            ),
            NewsArticle(
                title="S&P500, 빅테크 반등에 사상 최고치 근접",
                link="https://signal.example.com/1",
                summary="미국 증시에서 빅테크와 반도체가 지수 상승을 주도했습니다.",
            ),
            NewsArticle(
                title="미국 고용지표 대기 속 뉴욕증시 관망",
                link="https://signal.example.com/2",
                summary="연준 금리 경로와 국채금리 움직임이 S&P500 방향성의 변수로 꼽힙니다.",
            ),
        ]

        filtered = filter_topic_news("S&P500", news_items, limit=2)

        self.assertEqual(len(filtered), 2)
        self.assertTrue(any("S&P500" in item.title for item in filtered))
        self.assertTrue(any("뉴욕증시" in item.title for item in filtered))
        self.assertFalse(any("WOMEN'SDAY" in item.title for item in filtered))

    def test_select_topic_community_posts_matches_topic_aliases(self):
        community_posts = [
            CommunityPost(title="AI 서버 투자 다시 붙나…GPU랑 HBM이 핵심", link="https://community.example.com/1"),
            CommunityPost(title="이차전지는 리튬 가격부터 봐야 한다는 토론", link="https://community.example.com/2"),
            CommunityPost(title="오늘 장은 그냥 관망", link="https://community.example.com/3"),
        ]

        selected = select_topic_community_posts("인공지능", community_posts, limit=2)

        self.assertEqual(len(selected), 1)
        self.assertIn("GPU", selected[0].title)


if __name__ == "__main__":
    unittest.main()
