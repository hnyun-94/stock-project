"""External market connector service tests."""

import os
import unittest
from unittest.mock import patch

from src.services import market_external_connectors as connectors
from src.services.market_external_connectors import ConnectorResult


class TestDataGoCountExtraction(unittest.TestCase):
    """data.go payload parsing tests."""

    def test_extract_count_from_total_count(self):
        payload = {
            "response": {
                "body": {
                    "totalCount": "17",
                    "items": {"item": []},
                }
            }
        }
        self.assertEqual(connectors._extract_data_go_count(payload), 17)

    def test_extract_count_from_item_list(self):
        payload = {
            "response": {
                "body": {
                    "items": {
                        "item": [{"a": 1}, {"a": 2}, {"a": 3}],
                    }
                }
            }
        }
        self.assertEqual(connectors._extract_data_go_count(payload), 3)


class TestOpenDartCategorization(unittest.TestCase):
    """OpenDART report categorization tests."""

    def test_categorize_reports(self):
        rows = [
            {"report_nm": "영업(잠정)실적(공정공시)"},
            {"report_nm": "유상증자결정"},
            {"report_nm": "최대주주 변경"},
            {"report_nm": "기타 공시"},
        ]
        categories = connectors._categorize_opendart_reports(rows)
        self.assertEqual(categories["earnings"], 1)
        self.assertEqual(categories["financing"], 1)
        self.assertEqual(categories["ownership"], 1)
        self.assertEqual(categories["other"], 1)


class TestCollectExternalMetrics(unittest.IsolatedAsyncioTestCase):
    """External connector orchestration tests."""

    async def test_collect_returns_empty_when_disabled(self):
        with patch.dict(
            os.environ,
            {
                "EXTERNAL_CONNECTORS_ENABLED": "false",
                "ACTIVE_MARKET_SOURCES": "opendart,sec_edgar",
            },
            clear=False,
        ):
            result = await connectors.collect_external_source_metrics()

        self.assertEqual(result, {})

    async def test_collect_uses_only_ok_results(self):
        async def ok_handler() -> ConnectorResult:
            return ConnectorResult("opendart", "ok", 12, "ok")

        async def skip_handler() -> ConnectorResult:
            return ConnectorResult("fred", "skip", 0, "missing key")

        async def error_handler() -> ConnectorResult:
            return ConnectorResult("sec_edgar", "error", 0, "failed")

        handlers = {
            "opendart": ok_handler,
            "fred": skip_handler,
            "sec_edgar": error_handler,
        }

        with (
            patch.dict(
                os.environ,
                {
                    "EXTERNAL_CONNECTORS_ENABLED": "true",
                    "EXTERNAL_CONNECTOR_TELEMETRY_DB": "false",
                },
                clear=False,
            ),
            patch.object(connectors, "_CONNECTOR_HANDLERS", handlers),
        ):
            result = await connectors.collect_external_source_metrics(
                active_source_ids=["opendart", "fred", "sec_edgar", "unknown"],
            )

        self.assertEqual(result, {"opendart": 12})

    async def test_collect_expands_extra_metrics(self):
        async def opendart_handler() -> ConnectorResult:
            return ConnectorResult(
                "opendart",
                "ok",
                4,
                "ok",
                extra_metrics={"opendart:earnings": 2, "opendart:other": 2},
            )

        with (
            patch.dict(
                os.environ,
                {
                    "EXTERNAL_CONNECTORS_ENABLED": "true",
                    "EXTERNAL_CONNECTOR_TELEMETRY_DB": "false",
                },
                clear=False,
            ),
            patch.object(connectors, "_CONNECTOR_HANDLERS", {"opendart": opendart_handler}),
        ):
            result = await connectors.collect_external_source_metrics(
                active_source_ids=["opendart"],
            )

        self.assertEqual(
            result,
            {"opendart": 4, "opendart:earnings": 2, "opendart:other": 2},
        )

    async def test_collect_resolves_sources_from_environment(self):
        async def opendart_handler() -> ConnectorResult:
            return ConnectorResult("opendart", "ok", 3, "ok")

        async def sec_handler() -> ConnectorResult:
            return ConnectorResult("sec_edgar", "ok", 10, "ok")

        handlers = {
            "opendart": opendart_handler,
            "sec_edgar": sec_handler,
        }

        with (
            patch.dict(
                os.environ,
                {
                    "EXTERNAL_CONNECTORS_ENABLED": "true",
                    "ACTIVE_MARKET_SOURCES": " opendart, sec_edgar ",
                    "EXTERNAL_CONNECTOR_TELEMETRY_DB": "false",
                },
                clear=False,
            ),
            patch.object(connectors, "_CONNECTOR_HANDLERS", handlers),
        ):
            result = await connectors.collect_external_source_metrics(active_source_ids=None)

        self.assertEqual(result, {"opendart": 3, "sec_edgar": 10})

    def test_render_telemetry_markdown(self):
        results = [
            ConnectorResult("opendart", "ok", 5, "ok", latency_ms=120),
            ConnectorResult("fred", "skip", 0, "missing key", latency_ms=0),
        ]
        markdown = connectors.render_external_connector_telemetry_markdown(results)
        self.assertIn("외부 소스 텔레메트리", markdown)
        self.assertIn("opendart", markdown)
        self.assertIn("latency 120ms", markdown)
        self.assertIn("missing key", markdown)


if __name__ == "__main__":
    unittest.main()
