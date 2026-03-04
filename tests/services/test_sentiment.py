"""
감정 지표(Sentiment) 단위 테스트 모듈.

[Task 6.19, REQ-F04]
"""

import unittest
from unittest.mock import MagicMock
import sys

sys.modules['src.utils.logger'] = MagicMock()

from src.utils.sentiment import _score_text, analyze_sentiment, format_sentiment_section
from src.models import NewsArticle, CommunityPost


class TestScoreText(unittest.TestCase):
    """_score_text() 함수 테스트."""

    def test_positive_keyword(self):
        """긍정 키워드 점수 계산."""
        self.assertGreater(_score_text("삼성전자 급등"), 0)

    def test_negative_keyword(self):
        """부정 키워드 점수 계산."""
        self.assertLess(_score_text("코스피 폭락 공포"), 0)

    def test_neutral_text(self):
        """중립 텍스트는 0점."""
        self.assertEqual(_score_text("오늘 날씨가 좋습니다"), 0)

    def test_mixed_keywords(self):
        """긍정+부정 혼합 시 상쇄."""
        score = _score_text("급등 후 급락")
        # 급등(+2) + 급락(-2) = 0
        self.assertEqual(score, 0)


class TestAnalyzeSentiment(unittest.TestCase):
    """analyze_sentiment() 함수 테스트."""

    def test_positive_sentiment(self):
        """긍정적 데이터 → 양수 점수."""
        news = [NewsArticle(title="삼성전자 급등 신고가 돌파", link="a.com")]
        posts = [CommunityPost(title="대박 불장이다", link="b.com")]
        score, label = analyze_sentiment(news, posts)
        self.assertGreater(score, 0)
        self.assertTrue("긍정" in label or "탐욕" in label)

    def test_negative_sentiment(self):
        """부정적 데이터 → 음수 점수."""
        news = [NewsArticle(title="코스피 폭락 패닉", link="a.com")]
        posts = [CommunityPost(title="손절 공포 하락", link="b.com")]
        score, label = analyze_sentiment(news, posts)
        self.assertLess(score, 0)

    def test_empty_data(self):
        """빈 데이터 → 중립."""
        score, label = analyze_sentiment([], [])
        self.assertEqual(score, 0)
        self.assertIn("중립", label)

    def test_score_range(self):
        """점수가 -100 ~ +100 범위 내인지 검증."""
        news = [NewsArticle(title="급등 폭등 대박 로켓 불장", link="a.com")] * 10
        score, _ = analyze_sentiment(news, [])
        self.assertGreaterEqual(score, -100)
        self.assertLessEqual(score, 100)


class TestFormatSentimentSection(unittest.TestCase):
    """format_sentiment_section() 함수 테스트."""

    def test_contains_gauge(self):
        """게이지 바가 포함되는지 검증."""
        md = format_sentiment_section(50, "🟢 긍정적")
        self.assertIn("▓", md)
        self.assertIn("░", md)

    def test_contains_score(self):
        """점수가 포함되는지 검증."""
        md = format_sentiment_section(-30, "🟠 부정적")
        self.assertIn("-30", md)
        self.assertIn("부정적", md)

    def test_contains_header(self):
        """온도계 헤더가 포함되는지 검증."""
        md = format_sentiment_section(0, "🟡 중립")
        self.assertIn("시장 심리 온도계", md)


if __name__ == "__main__":
    unittest.main()
