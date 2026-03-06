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
            patch.dict(os.environ, {"EXTERNAL_CONNECTORS_ENABLED": "true"}, clear=False),
            patch.object(connectors, "_CONNECTOR_HANDLERS", handlers),
        ):
            result = await connectors.collect_external_source_metrics(
                active_source_ids=["opendart", "fred", "sec_edgar", "unknown"],
            )

        self.assertEqual(result, {"opendart": 12})

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
                },
                clear=False,
            ),
            patch.object(connectors, "_CONNECTOR_HANDLERS", handlers),
        ):
            result = await connectors.collect_external_source_metrics(active_source_ids=None)

        self.assertEqual(result, {"opendart": 3, "sec_edgar": 10})


if __name__ == "__main__":
    unittest.main()
