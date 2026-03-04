"""
피드백 매니저(FeedbackManager) 단위 테스트 모듈.

src/services/feedback_manager.py의 주요 함수들을 검증합니다.
- HMAC 서명 생성
- 피드백 링크 생성
- 피드백 링크 HTML 생성

[Task 6.17, REQ-Q03]
"""

import unittest
from unittest.mock import patch, MagicMock
import sys

# logger mock 설정
sys.modules['src.utils.logger'] = MagicMock()

from src.services.feedback_manager import (
    _create_signature,
    generate_feedback_link,
    generate_feedback_links_html
)


class TestCreateSignature(unittest.TestCase):
    """_create_signature() 함수 테스트."""

    @patch.dict('os.environ', {'WEBHOOK_SECRET': 'test_secret'})
    def test_signature_generation(self):
        """HMAC 서명이 올바르게 생성되는지 검증."""
        sig = _create_signature("홍길동", 5)
        self.assertIsInstance(sig, str)
        self.assertTrue(len(sig) > 0)

    @patch.dict('os.environ', {'WEBHOOK_SECRET': 'test_secret'})
    def test_signature_consistency(self):
        """동일 입력에 대해 동일 서명 생성."""
        sig1 = _create_signature("홍길동", 5)
        sig2 = _create_signature("홍길동", 5)
        self.assertEqual(sig1, sig2)

    @patch.dict('os.environ', {'WEBHOOK_SECRET': 'test_secret'})
    def test_different_scores_different_signatures(self):
        """다른 별점은 다른 서명 생성."""
        sig1 = _create_signature("홍길동", 1)
        sig2 = _create_signature("홍길동", 5)
        self.assertNotEqual(sig1, sig2)

    @patch.dict('os.environ', {'WEBHOOK_SECRET': ''})
    def test_empty_secret_returns_empty(self):
        """WEBHOOK_SECRET 미설정 시 빈 문자열 반환."""
        sig = _create_signature("홍길동", 5)
        self.assertEqual(sig, "")


class TestGenerateFeedbackLink(unittest.TestCase):
    """generate_feedback_link() 함수 테스트."""

    @patch.dict('os.environ', {
        'WEBHOOK_SECRET': 'test_secret',
        'FEEDBACK_BASE_URL': 'https://test.example.com'
    })
    def test_link_format(self):
        """생성된 링크가 올바른 형식인지 검증."""
        link = generate_feedback_link("홍길동", 5)
        self.assertIn("https://test.example.com/api/feedback", link)
        self.assertIn("user=홍길동", link)
        self.assertIn("score=5", link)
        self.assertIn("signature=", link)


class TestGenerateFeedbackLinksHtml(unittest.TestCase):
    """generate_feedback_links_html() 함수 테스트."""

    @patch.dict('os.environ', {
        'WEBHOOK_SECRET': 'test_secret',
        'FEEDBACK_BASE_URL': 'https://test.example.com'
    })
    def test_five_star_links(self):
        """1~5점 별점 링크가 모두 포함되는지 검증."""
        html = generate_feedback_links_html("홍길동")
        for score in range(1, 6):
            self.assertIn(f"{score}점", html)

    @patch.dict('os.environ', {
        'WEBHOOK_SECRET': 'test_secret',
        'FEEDBACK_BASE_URL': 'https://test.example.com'
    })
    def test_contains_star_emojis(self):
        """별점 이모지가 포함되는지 검증."""
        html = generate_feedback_links_html("홍길동")
        self.assertIn("⭐", html)

    @patch.dict('os.environ', {
        'WEBHOOK_SECRET': 'test_secret',
        'FEEDBACK_BASE_URL': 'https://test.example.com'
    })
    def test_pipe_separators(self):
        """별점 사이에 | 구분자가 있는지 검증."""
        html = generate_feedback_links_html("홍길동")
        self.assertEqual(html.count(" | "), 4)  # 5개 링크 사이 4개 구분자


if __name__ == "__main__":
    unittest.main()
