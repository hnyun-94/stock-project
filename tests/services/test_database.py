"""
SQLite Database 단위 테스트 모듈.

src/utils/database.py의 Database 클래스 동작을 검증합니다.
테스트마다 임시 DB를 생성하여 격리합니다.

[Task 6.20, REQ-P06]
"""

import os
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
import sys
import tempfile
from pathlib import Path

sys.modules['src.utils.logger'] = MagicMock()

from src.utils.database import Database, close_db, get_db, resolve_db_path


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

    # --- 외부 커넥터 텔레메트리 테스트 ---

    def test_insert_and_get_connector_run(self):
        """외부 커넥터 실행 결과 저장/조회."""
        self.db.insert_connector_run(
            source_id="opendart",
            status="ok",
            count=12,
            latency_ms=153,
            detail="sample",
        )
        rows = self.db.get_recent_connector_runs(limit=5, source_id="opendart")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["count"], 12)
        self.assertEqual(rows[0]["latency_ms"], 153)

    def test_connector_success_rate(self):
        """source별 성공률 계산."""
        self.db.insert_connector_run("opendart", "ok", 3, 100)
        self.db.insert_connector_run("opendart", "error", 0, 200, "timeout")
        self.db.insert_connector_run("sec_edgar", "ok", 1, 90)

        rates = self.db.get_connector_success_rate(days=1)
        self.assertEqual(rates["opendart"], 0.5)
        self.assertEqual(rates["sec_edgar"], 1.0)

    def test_connector_health_summary_excludes_skip_from_samples(self):
        """운영 요약은 skip을 표본 수에서 제외한다."""
        self.db.insert_connector_run("opendart", "skip", 0, 50, "disabled")
        self.db.insert_connector_run("opendart", "ok", 2, 100, "ok")
        self.db.insert_connector_run("opendart", "error", 0, 300, "timeout")

        summary = self.db.get_connector_health_summary(hours=1)["opendart"]
        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["skip_count"], 1)
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["failure_count"], 1)
        self.assertEqual(summary["failure_rate"], 0.5)
        self.assertEqual(summary["avg_latency_ms"], 200)
        self.assertEqual(summary["latest_status"], "error")

    def test_connector_alert_event_cooldown(self):
        """같은 fingerprint 알림은 쿨다운 동안 중복 발송으로 간주한다."""
        fingerprint = "opendart:latest_error"
        self.assertFalse(self.db.has_recent_connector_alert(fingerprint, cooldown_minutes=60))

        self.db.insert_connector_alert_event(
            source_id="opendart",
            alert_type="latest_error",
            window_hours=1,
            fingerprint=fingerprint,
            message="failed",
        )

        self.assertTrue(self.db.has_recent_connector_alert(fingerprint, cooldown_minutes=60))

    def test_connector_daily_rollups_group_by_day_and_source(self):
        """일자별 롤업은 source/day 기준으로 성공률과 평균 지연을 계산한다."""
        self.db.insert_connector_run("opendart", "ok", 3, 100)
        self.db.insert_connector_run("opendart", "error", 0, 300, "timeout")
        self.db.insert_connector_run("opendart", "skip", 0, 50, "disabled")
        self.db.insert_connector_run("fred", "ok", 5, 200)

        rows = self.db.get_recent_connector_runs(limit=4)
        timestamps = {}
        for row in rows:
            key = (row["source_id"], row["status"])
            if key == ("fred", "ok"):
                timestamps[row["id"]] = "2026-03-06T07:00:00"
            elif key == ("opendart", "skip"):
                timestamps[row["id"]] = "2026-03-07T07:00:00"
            elif key == ("opendart", "error"):
                timestamps[row["id"]] = "2026-03-07T08:00:00"
            else:
                timestamps[row["id"]] = "2026-03-07T09:00:00"
        for row_id, ts in timestamps.items():
            self.db._conn.execute(
                "UPDATE external_connector_runs SET timestamp = ? WHERE id = ?",
                (ts, row_id),
            )
        self.db._conn.commit()

        rollups = self.db.get_connector_daily_rollups(days=14)
        opendart = [row for row in rollups if row["source_id"] == "opendart"][0]
        fred = [row for row in rollups if row["source_id"] == "fred"][0]

        self.assertEqual(opendart["day"], "2026-03-07")
        self.assertEqual(opendart["sample_count"], 2)
        self.assertEqual(opendart["skip_count"], 1)
        self.assertEqual(opendart["success_rate"], 0.5)
        self.assertEqual(opendart["avg_latency_ms"], 200)
        self.assertEqual(fred["day"], "2026-03-06")
        self.assertEqual(fred["success_rate"], 1.0)

    def test_get_recent_connector_failures_returns_latest_errors(self):
        """실패 사유 조회는 ok/skip을 제외하고 최신 오류만 반환한다."""
        self.db.insert_connector_run("opendart", "ok", 1, 100)
        self.db.insert_connector_run("fred", "error", 0, 500, "timeout")
        self.db.insert_connector_run("sec_edgar", "error", 0, 700, "http 503")

        failures = self.db.get_recent_connector_failures(days=1, limit=2)
        self.assertEqual(len(failures), 2)
        self.assertEqual(failures[0]["source_id"], "sec_edgar")
        self.assertIn("503", failures[0]["detail"])

    # --- 리포트 스냅샷 테스트 ---

    def test_insert_and_get_recent_report_snapshot(self):
        """사용자별 최근 리포트 스냅샷 저장/조회."""
        self.db.insert_report_snapshot(
            user_name="홍길동",
            headline="시장 심리 개선",
            snapshot_json='{"focus_keywords":["AI"]}',
            report_text="리포트 본문",
        )

        rows = self.db.get_recent_report_snapshots("홍길동", limit=2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["headline"], "시장 심리 개선")
        self.assertIn('"AI"', rows[0]["snapshot_json"])

    def test_get_report_snapshots_since_filters_by_user(self):
        """기간 조회가 사용자 기준으로 분리된다."""
        self.db.insert_report_snapshot("A", "헤드라인A", "{}", "본문A")
        self.db.insert_report_snapshot("B", "헤드라인B", "{}", "본문B")

        rows = self.db.get_report_snapshots_since("A", days=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user_name"], "A")

    def test_resolve_db_path_prefers_environment_variable(self):
        """환경변수 STOCK_DB_PATH가 기본 경로보다 우선한다."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, "runtime.db")
            with patch.dict(os.environ, {"STOCK_DB_PATH": env_path}, clear=False):
                self.assertEqual(resolve_db_path(), env_path)

    def test_get_db_uses_environment_path(self):
        """get_db()가 런타임 환경변수 경로를 반영한다."""
        close_db()
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, "runtime.db")
            with patch.dict(os.environ, {"STOCK_DB_PATH": env_path}, clear=False):
                db = get_db()
                self.assertEqual(db.db_path, env_path)
                db.insert_feedback("홍길동", 5)
                self.assertTrue(os.path.exists(env_path))
        close_db()

    def test_database_recovers_from_corrupted_file(self):
        """손상된 SQLite 파일이 있으면 백업 후 새 DB를 생성한다."""
        with tempfile.TemporaryDirectory() as temp_dir:
            broken_path = os.path.join(temp_dir, "broken.db")
            Path(broken_path).write_text("not-a-sqlite-db", encoding="utf-8")

            recovered = Database(broken_path)
            recovered.insert_feedback("복구", 4)
            rows = recovered.get_recent_feedbacks(days=1)
            recovered.close()

            self.assertEqual(len(rows), 1)
            backups = list(Path(temp_dir).glob("broken.db.corrupt-*"))
            self.assertTrue(backups)


if __name__ == "__main__":
    unittest.main()
