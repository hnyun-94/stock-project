"""
자동 프롬프트 튜닝 단위 테스트 모듈.

[Task 6.22, REQ-F06]
"""

import os
import sys
import unittest
import tempfile
from unittest.mock import MagicMock

sys.modules['src.utils.logger'] = MagicMock()

from src.utils.database import Database
from src.services.prompt_tuner import get_tuning_adjustments, apply_tuning_to_prompt
import src.services.prompt_tuner as tuner_module


class TestPromptTuner(unittest.TestCase):
    """프롬프트 튜닝 테스트."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        # prompt_tuner가 사용하는 get_db를 패치
        self._orig_get_db = tuner_module.get_db
        tuner_module.get_db = lambda: self.db

    def tearDown(self):
        tuner_module.get_db = self._orig_get_db
        self.db.close()
        os.unlink(self.tmp.name)

    def test_no_feedback_returns_defaults(self):
        """피드백 없을 때 기본값 반환."""
        adj = get_tuning_adjustments()
        self.assertEqual(adj["temperature_delta"], 0.0)
        self.assertEqual(adj["style_hint"], "")

    def test_low_score_triggers_tuning(self):
        """낮은 점수 → 조정 적용."""
        self.db.insert_feedback("A", 2)
        self.db.insert_feedback("B", 1)
        adj = get_tuning_adjustments()
        self.assertGreater(adj["temperature_delta"], 0)
        self.assertIn("구체적", adj["style_hint"])

    def test_high_score_stabilizes(self):
        """높은 점수 → 안정화."""
        for i in range(5):
            self.db.insert_feedback(f"U{i}", 5)
        adj = get_tuning_adjustments()
        self.assertLessEqual(adj["temperature_delta"], 0)

    def test_apply_tuning_adds_hint(self):
        """스타일 지시어가 프롬프트에 추가됨."""
        result = apply_tuning_to_prompt(
            "원본 프롬프트",
            {"style_hint": "더 구체적으로", "temperature_delta": 0.1}
        )
        self.assertIn("더 구체적으로", result)
        self.assertIn("원본 프롬프트", result)

    def test_apply_tuning_no_hint(self):
        """스타일 지시어 없으면 원본 유지."""
        result = apply_tuning_to_prompt(
            "원본 프롬프트",
            {"style_hint": "", "temperature_delta": 0.0}
        )
        self.assertEqual(result, "원본 프롬프트")


if __name__ == "__main__":
    unittest.main()
