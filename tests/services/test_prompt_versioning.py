"""
프롬프트 버전 관리 및 A/B 테스트 단위 테스트 모듈.

[Task 6.23, REQ-F07]
"""

import os
import sys
import unittest
import tempfile
from unittest.mock import MagicMock

sys.modules['src.utils.logger'] = MagicMock()

from src.utils.database import Database
from src.services.prompt_versioning import PromptVersionManager
import src.services.prompt_versioning as pv_module


class TestPromptVersionManager(unittest.TestCase):
    """PromptVersionManager 테스트."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self._orig_get_db = pv_module.get_db
        pv_module.get_db = lambda: self.db

    def tearDown(self):
        pv_module.get_db = self._orig_get_db
        self.db.close()
        os.unlink(self.tmp.name)

    def test_single_version_returns_v1(self):
        """단일 버전 → 항상 v1 반환."""
        pvm = PromptVersionManager()
        v = pvm.assign_version("홍길동", "market_summary")
        self.assertEqual(v, "v1")

    def test_consistent_assignment(self):
        """같은 사용자는 항상 같은 버전 배정."""
        pvm = PromptVersionManager(
            versions={"market_summary": ["v1", "v2"]}
        )
        v1 = pvm.assign_version("홍길동", "market_summary")
        v2 = pvm.assign_version("홍길동", "market_summary")
        self.assertEqual(v1, v2)

    def test_ab_split(self):
        """다른 사용자는 다른 그룹에 배정될 수 있음."""
        pvm = PromptVersionManager(
            versions={"market_summary": ["v1", "v2"]}
        )
        versions = set()
        for i in range(20):
            v = pvm.assign_version(f"user_{i}", "market_summary")
            versions.add(v)
        # 20명이면 두 그룹 모두에 배정
        self.assertEqual(len(versions), 2)

    def test_record_and_get_stats(self):
        """사용 이력 기록 및 통계 조회."""
        pvm = PromptVersionManager()
        pvm.record_usage("A", "market_summary", "v1")
        pvm.record_usage("B", "market_summary", "v1")
        pvm.record_usage("C", "market_summary", "v2")
        stats = pvm.get_version_stats("market_summary")
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[0]["version"], "v1")
        self.assertEqual(stats[0]["count"], 2)

    def test_add_version(self):
        """새 버전 추가."""
        pvm = PromptVersionManager()
        pvm.add_version("market_summary", "v2")
        self.assertIn("v2", pvm._versions["market_summary"])

    def test_add_version_no_duplicate(self):
        """중복 버전 추가 방지."""
        pvm = PromptVersionManager()
        pvm.add_version("market_summary", "v1")
        self.assertEqual(pvm._versions["market_summary"].count("v1"), 1)


if __name__ == "__main__":
    unittest.main()
