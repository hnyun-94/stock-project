"""
피드백 서버 보안 렌더링 테스트 모듈.
"""

import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules['src.utils.logger'] = MagicMock()
sys.modules['src.services.feedback_manager'] = MagicMock()


class TestFeedbackServerRendering(unittest.TestCase):
    """피드백 완료 페이지의 HTML escape 동작을 검증합니다."""

    def test_render_feedback_success_html_escapes_user_name(self):
        with patch.dict(os.environ, {"WEBHOOK_SECRET": "test-secret"}, clear=False):
            sys.modules.pop("src.apps.feedback_server", None)
            feedback_server = importlib.import_module("src.apps.feedback_server")

        html = feedback_server.render_feedback_success_html('<script>alert(1)</script>', 5)

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)


if __name__ == "__main__":
    unittest.main()
