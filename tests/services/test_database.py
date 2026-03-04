"""
SQLite Database 단위 테스트 모듈.

src/utils/database.py의 Database 클래스 동작을 검증합니다.
테스트마다 임시 DB를 생성하여 격리합니다.

[Task 6.20, REQ-P06]
"""

import os
import unittest
from unittest.mock import MagicMock
import sys
import tempfile

sys.modules['src.utils.logger'] = MagicMock()

from src.utils.database import Database


class TestDatabase(unittest.TestCase):
    """Database 클래스 단위 테스트."""

    def setUp(self):
        """각 테스트 전에 임시 DB 생성."""
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        """테스트 후 임시 DB 삭제."""
        self.db.close()
        os.unlink(self.tmp.name)

    # --- 피드백 테스트 ---

    def test_insert_and_get_feedback(self):
        """피드백 삽입 및 조회."""
        self.db.insert_feedback("홍길동", 5, "좋아요")
        feedbacks = self.db.get_recent_feedbacks(days=1)
        self.assertEqual(len(feedbacks), 1)
        self.assertEqual(feedbacks[0]["user_name"], "홍길동")
        self.assertEqual(feedbacks[0]["score"], 5)

    def test_average_score(self):
        """평균 점수 계산."""
        self.db.insert_feedback("A", 5)
        self.db.insert_feedback("B", 3)
        avg = self.db.get_average_score(days=1)
        self.assertEqual(avg, 4.0)

    def test_average_score_empty(self):
        """데이터 없을 때 0.0 반환."""
        avg = self.db.get_average_score()
        self.assertEqual(avg, 0.0)

    # --- 스냅샷 테스트 ---

    def test_insert_and_get_snapshot(self):
        """스냅샷 삽입 및 조회."""
        self.db.insert_snapshot("홍길동", "삼성전자", "AI 분석 텍스트")
        snapshots = self.db.get_recent_snapshots(limit=1)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["user_name"], "홍길동")

    def test_snapshot_text_truncation(self):
        """1000자 이상 텍스트 자르기 검증."""
        long_text = "A" * 2000
        self.db.insert_snapshot("테스트", "종목", long_text)
        snap = self.db.get_recent_snapshots(limit=1)[0]
        self.assertEqual(len(snap["analysis_snip"]), 1000)

    def test_multiple_snapshots_order(self):
        """최신순 정렬 검증."""
        self.db.insert_snapshot("A", "종목A", "분석A")
        self.db.insert_snapshot("B", "종목B", "분석B")
        snapshots = self.db.get_recent_snapshots(limit=2)
        self.assertEqual(snapshots[0]["user_name"], "B")  # 최신이 먼저
    # --- 스코어링 테스트 [REQ-F05] ---

    def test_update_snapshot_score(self):
        """스냅샷 적중률 점수 업데이트."""
        self.db.insert_snapshot("A", "종목A", "분석A")
        snap = self.db.get_recent_snapshots(limit=1)[0]
        self.db.update_snapshot_score(snap["id"], 0.85)
        updated = self.db.get_recent_snapshots(limit=1)[0]
        self.assertEqual(updated["accuracy_score"], 0.85)

    def test_average_accuracy(self):
        """평균 적중률 계산."""
        self.db.insert_snapshot("A", "종목A", "분석A")
        self.db.insert_snapshot("B", "종목B", "분석B")
        snaps = self.db.get_recent_snapshots(limit=2)
        self.db.update_snapshot_score(snaps[0]["id"], 0.8)
        self.db.update_snapshot_score(snaps[1]["id"], 0.6)
        avg = self.db.get_average_accuracy(days=1)
        self.assertEqual(avg, 0.7)

    def test_unscored_snapshots(self):
        """미채점 스냅샷 조회."""
        self.db.insert_snapshot("A", "종목A", "분석A")
        self.db.insert_snapshot("B", "종목B", "분석B")
        snaps = self.db.get_recent_snapshots(limit=2)
        self.db.update_snapshot_score(snaps[0]["id"], 0.5)
        unscored = self.db.get_unscored_snapshots()
        self.assertEqual(len(unscored), 1)


if __name__ == "__main__":
    unittest.main()
