"""External connector 운영 알림 서비스 테스트."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.services.connector_alerts import dispatch_connector_health_alerts
from src.utils.database import Database


class TestConnectorAlerts(unittest.TestCase):
    """외부 커넥터 운영 알림 평가/쿨다운 테스트."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_dispatch_sends_latest_error_alert_and_records_event(self):
        """최근 실행 실패는 즉시 관리자 알림으로 전송된다."""
        self.db.insert_connector_run("opendart", "error", 0, 1500, "timeout")
        sender = MagicMock()
        sender.send_to_chat_id.return_value = True

        with patch.dict(
            os.environ,
            {
                "EXTERNAL_CONNECTOR_ALERTS_ENABLED": "true",
                "EXTERNAL_CONNECTOR_ALERT_CHAT_IDS": "111,222",
                "EXTERNAL_CONNECTOR_ALERT_AVG_LATENCY_MS": "99999",
                "EXTERNAL_CONNECTOR_ALERT_MIN_SAMPLES": "2",
            },
            clear=False,
        ):
            decisions = dispatch_connector_health_alerts(self.db, sender=sender)

        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].source_id, "opendart")
        self.assertIn("latest_error", decisions[0].reasons)
        self.assertEqual(decisions[0].sent_chat_ids, ("111", "222"))
        self.assertTrue(self.db.has_recent_connector_alert("opendart:latest_error", cooldown_minutes=180))
        self.assertEqual(sender.send_to_chat_id.call_count, 2)

    def test_dispatch_uses_failure_rate_alert_when_latest_status_is_ok(self):
        """최신 실행이 성공이어도 1시간 실패율이 높으면 경고한다."""
        self.db.insert_connector_run("fred", "error", 0, 500, "timeout")
        self.db.insert_connector_run("fred", "error", 0, 450, "bad response")
        self.db.insert_connector_run("fred", "ok", 10, 300, "recovered")
        sender = MagicMock()
        sender.send_to_chat_id.return_value = True

        with patch.dict(
            os.environ,
            {
                "EXTERNAL_CONNECTOR_ALERTS_ENABLED": "true",
                "EXTERNAL_CONNECTOR_ALERT_CHAT_IDS": "333",
                "EXTERNAL_CONNECTOR_ALERT_FAILURE_RATE_1H": "0.5",
                "EXTERNAL_CONNECTOR_ALERT_FAILURE_RATE_24H": "0.9",
                "EXTERNAL_CONNECTOR_ALERT_AVG_LATENCY_MS": "99999",
                "EXTERNAL_CONNECTOR_ALERT_MIN_SAMPLES": "2",
            },
            clear=False,
        ):
            decisions = dispatch_connector_health_alerts(self.db, sender=sender)

        self.assertEqual(len(decisions), 1)
        self.assertIn("failure_rate_1h", decisions[0].reasons)
        self.assertNotIn("latest_error", decisions[0].reasons)

    def test_dispatch_skips_recent_duplicate_alert(self):
        """같은 fingerprint는 쿨다운 동안 재발송하지 않는다."""
        self.db.insert_connector_run("sec_edgar", "error", 0, 1000, "http 503")
        sender = MagicMock()
        sender.send_to_chat_id.return_value = True

        env = {
            "EXTERNAL_CONNECTOR_ALERTS_ENABLED": "true",
            "EXTERNAL_CONNECTOR_ALERT_CHAT_IDS": "444",
            "EXTERNAL_CONNECTOR_ALERT_AVG_LATENCY_MS": "99999",
            "EXTERNAL_CONNECTOR_ALERT_MIN_SAMPLES": "2",
            "EXTERNAL_CONNECTOR_ALERT_COOLDOWN_MINUTES": "180",
        }
        with patch.dict(os.environ, env, clear=False):
            first = dispatch_connector_health_alerts(self.db, sender=sender)
            second = dispatch_connector_health_alerts(self.db, sender=sender)

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertFalse(first[0].skipped_by_cooldown)
        self.assertTrue(second[0].skipped_by_cooldown)
        self.assertEqual(sender.send_to_chat_id.call_count, 1)


if __name__ == "__main__":
    unittest.main()
