"""
뉴스 중복 제거(Deduplicator) 단위 테스트 모듈.

src/utils/deduplicator.py의 deduplicate_news()가 올바르게 동작하는지 검증합니다.
- 제목 정규화
- 유사도 계산
- 중복 뉴스 필터링

[Task 6.17, REQ-Q03]
"""

import unittest
from unittest.mock import patch, MagicMock
import sys

# logger mock 설정
sys.modules['src.utils.logger'] = MagicMock()

from src.utils.deduplicator import _normalize_title, _similarity, deduplicate_news
from src.models import NewsArticle


class TestNormalizeTitle(unittest.TestCase):
    """_normalize_title() 함수 테스트."""

    def test_remove_brackets(self):
        """대괄호 태그 제거 검증."""
        self.assertEqual(_normalize_title("[속보] 삼성전자 실적 발표"), "삼성전자 실적 발표")

    def test_remove_multiple_brackets(self):
        """여러 대괄호 태그 제거."""
        self.assertEqual(
            _normalize_title("[종합] [단독] 주가 급등"),
            "주가 급등"
        )

    def test_remove_ellipsis(self):
        """말줄임표 제거."""
        self.assertEqual(_normalize_title("삼성전자..."), "삼성전자")

    def test_strip_whitespace(self):
        """앞뒤 공백 제거."""
        self.assertEqual(_normalize_title("  뉴스 제목  "), "뉴스 제목")


class TestSimilarity(unittest.TestCase):
    """_similarity() 함수 테스트."""

    def test_identical_strings(self):
        """동일 문자열은 유사도 1.0."""
        self.assertEqual(_similarity("hello", "hello"), 1.0)

    def test_completely_different(self):
        """완전 다른 문자열은 낮은 유사도."""
        self.assertLess(_similarity("abc", "xyz"), 0.5)

    def test_similar_strings(self):
        """유사한 문자열은 높은 유사도."""
        sim = _similarity("삼성전자 4분기 실적 발표", "삼성전자 4분기 실적 공개")
        self.assertGreater(sim, 0.7)


class TestDeduplicateNews(unittest.TestCase):
    """deduplicate_news() 함수 테스트."""

    def test_no_duplicates(self):
        """중복이 없는 경우 모든 뉴스 유지."""
        news = [
            NewsArticle(title="삼성전자 급등", link="a.com"),
            NewsArticle(title="코스피 하락", link="b.com"),
        ]
        result = deduplicate_news(news)
        self.assertEqual(len(result), 2)

    def test_exact_duplicates(self):
        """제목이 완전히 같은 뉴스 제거."""
        news = [
            NewsArticle(title="삼성전자 급등", link="a.com"),
            NewsArticle(title="삼성전자 급등", link="b.com"),
        ]
        result = deduplicate_news(news)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].link, "a.com")  # 먼저 등장한 뉴스 유지

    def test_similar_duplicates(self):
        """유사한 제목(85% 이상) 뉴스 제거."""
        news = [
            NewsArticle(title="삼성전자 4분기 실적 발표 예정", link="a.com"),
            NewsArticle(title="삼성전자 4분기 실적 공식 발표", link="b.com"),
            NewsArticle(title="코스피 2500 돌파", link="c.com"),
        ]
        result = deduplicate_news(news, threshold=0.7)
        self.assertEqual(len(result), 2)

    def test_empty_list(self):
        """빈 리스트 입력 처리."""
        result = deduplicate_news([])
        self.assertEqual(len(result), 0)

    def test_bracket_tags_ignored(self):
        """태그가 다른 같은 뉴스 필터링."""
        news = [
            NewsArticle(title="[속보] 삼성전자 실적 발표", link="a.com"),
            NewsArticle(title="[단독] 삼성전자 실적 발표", link="b.com"),
        ]
        result = deduplicate_news(news)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
