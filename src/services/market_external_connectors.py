"""
External market connector layer for free-source signal collection.

역할:
1. data.go/OpenDART/SEC/FRED 소스의 최소 지표(count)를 수집합니다.
2. API 키/URL 미설정 시 skip 처리하여 파이프라인을 중단하지 않습니다.
3. main 파이프라인에서 정량 스냅샷의 event_counts로 재사용합니다.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

from src.crawlers.http_client import get_session
from src.services.market_source_governance import parse_active_source_ids
from src.utils.logger import global_logger


@dataclass(frozen=True)
class ConnectorResult:
    """External source collection result."""

    source_id: str
    status: str
    count: int
    detail: str


ConnectorHandler = Callable[[], Awaitable[ConnectorResult]]


def _is_truthy(raw: Optional[str]) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


async def _fetch_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Performs an HTTP GET request and returns JSON payload."""
    session = await get_session()
    async with session.get(url, params=params or {}, headers=headers or {}) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


def _extract_data_go_count(payload: Dict[str, Any]) -> int:
    """Extracts row count from data.go style response payload."""
    body = payload.get("response", {}).get("body", {})
    total_count = _safe_int(body.get("totalCount"))
    if total_count > 0:
        return total_count

    items = body.get("items", {})
    if isinstance(items, dict):
        item = items.get("item")
        if isinstance(item, list):
            return len(item)
        if isinstance(item, dict):
            return 1
    return 0


async def _collect_data_go_stock_price_count() -> ConnectorResult:
    """Collects row count from data.go stock price endpoint."""
    api_key = os.getenv("DATA_GO_KR_API_KEY", "").strip()
    api_url = os.getenv("DATA_GO_KR_STOCK_PRICE_URL", "").strip()
    if not api_key or not api_url:
        return ConnectorResult(
            source_id="fsc_stock_price",
            status="skip",
            count=0,
            detail="DATA_GO_KR_API_KEY 또는 DATA_GO_KR_STOCK_PRICE_URL 미설정",
        )

    params = {
        "serviceKey": api_key,
        "numOfRows": _safe_int(os.getenv("DATA_GO_KR_NUM_ROWS", "20")) or 20,
        "pageNo": 1,
        "resultType": "json",
    }

    try:
        payload = await _fetch_json(api_url, params=params)
        count = _extract_data_go_count(payload if isinstance(payload, dict) else {})
        return ConnectorResult(
            source_id="fsc_stock_price",
            status="ok",
            count=max(0, count),
            detail="data.go stock price sample collected",
        )
    except Exception as exc:  # pragma: no cover - network branch
        return ConnectorResult(
            source_id="fsc_stock_price",
            status="error",
            count=0,
            detail=f"data.go request failed: {exc}",
        )


async def _collect_opendart_disclosure_count() -> ConnectorResult:
    """Collects today's OpenDART disclosure count."""
    api_key = os.getenv("OPEN_DART_API_KEY", "").strip()
    if not api_key:
        return ConnectorResult(
            source_id="opendart",
            status="skip",
            count=0,
            detail="OPEN_DART_API_KEY 미설정",
        )

    target_date = datetime.now().strftime("%Y%m%d")
    params = {
        "crtfc_key": api_key,
        "bgn_de": target_date,
        "end_de": target_date,
        "page_count": _safe_int(os.getenv("OPEN_DART_PAGE_COUNT", "20")) or 20,
    }

    try:
        payload = await _fetch_json("https://opendart.fss.or.kr/api/list.json", params=params)
        if not isinstance(payload, dict):
            return ConnectorResult("opendart", "error", 0, "unexpected payload")

        status = str(payload.get("status", ""))
        if status not in {"000", "013"}:
            return ConnectorResult(
                source_id="opendart",
                status="error",
                count=0,
                detail=f"status={status}",
            )

        rows = payload.get("list") or []
        return ConnectorResult(
            source_id="opendart",
            status="ok",
            count=len(rows) if isinstance(rows, list) else 0,
            detail="opendart disclosure count collected",
        )
    except Exception as exc:  # pragma: no cover - network branch
        return ConnectorResult("opendart", "error", 0, f"opendart request failed: {exc}")


async def _collect_sec_ticker_count() -> ConnectorResult:
    """Collects SEC ticker registry count as US source health signal."""
    user_agent = os.getenv(
        "SEC_USER_AGENT",
        "stock-project/1.0 (contact: support@example.com)",
    ).strip()
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    try:
        payload = await _fetch_json("https://www.sec.gov/files/company_tickers.json", headers=headers)
        if isinstance(payload, dict):
            count = len(payload)
        elif isinstance(payload, list):
            count = len(payload)
        else:
            count = 0
        return ConnectorResult(
            source_id="sec_edgar",
            status="ok",
            count=count,
            detail="sec ticker registry count collected",
        )
    except Exception as exc:  # pragma: no cover - network branch
        return ConnectorResult("sec_edgar", "error", 0, f"sec request failed: {exc}")


async def _collect_fred_observation_count() -> ConnectorResult:
    """Collects observation sample count from FRED series endpoint."""
    api_key = os.getenv("FRED_API_KEY", "").strip()
    if not api_key:
        return ConnectorResult(
            source_id="fred",
            status="skip",
            count=0,
            detail="FRED_API_KEY 미설정",
        )

    params = {
        "series_id": os.getenv("FRED_SERIES_ID", "DFF").strip() or "DFF",
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": _safe_int(os.getenv("FRED_SAMPLE_LIMIT", "20")) or 20,
    }

    try:
        payload = await _fetch_json(
            "https://api.stlouisfed.org/fred/series/observations",
            params=params,
        )
        observations = []
        if isinstance(payload, dict):
            raw = payload.get("observations")
            if isinstance(raw, list):
                observations = raw
        return ConnectorResult(
            source_id="fred",
            status="ok",
            count=len(observations),
            detail="fred observation sample collected",
        )
    except Exception as exc:  # pragma: no cover - network branch
        return ConnectorResult("fred", "error", 0, f"fred request failed: {exc}")


_CONNECTOR_HANDLERS: Dict[str, ConnectorHandler] = {
    "fsc_stock_price": _collect_data_go_stock_price_count,
    "fsc_listed_info": _collect_data_go_stock_price_count,
    "opendart": _collect_opendart_disclosure_count,
    "sec_edgar": _collect_sec_ticker_count,
    "fred": _collect_fred_observation_count,
}


def _resolve_external_sources(raw: Optional[str], default_source_ids: Iterable[str]) -> list[str]:
    return parse_active_source_ids(raw, default_source_ids=default_source_ids)


async def collect_external_source_metrics(
    active_source_ids: Optional[list[str]] = None,
) -> Dict[str, int]:
    """Collects count metrics from enabled external sources.

    Returns only successful metrics in `{source_id: count}` format.
    """
    if not _is_truthy(os.getenv("EXTERNAL_CONNECTORS_ENABLED", "false")):
        return {}

    default_sources = ["opendart", "sec_edgar", "fred", "fsc_stock_price"]
    source_ids = active_source_ids
    if source_ids is None:
        source_ids = _resolve_external_sources(
            os.getenv("ACTIVE_MARKET_SOURCES"),
            default_source_ids=default_sources,
        )

    tasks: list[Awaitable[ConnectorResult]] = []
    task_sources: list[str] = []
    for source_id in source_ids:
        handler = _CONNECTOR_HANDLERS.get(source_id)
        if handler is None:
            global_logger.info(f"[ExternalConnector] unsupported source skipped: {source_id}")
            continue
        tasks.append(handler())
        task_sources.append(source_id)

    if not tasks:
        return {}

    results = await asyncio.gather(*tasks, return_exceptions=True)
    metrics: Dict[str, int] = {}

    for source_id, result in zip(task_sources, results):
        if isinstance(result, Exception):
            global_logger.warning(f"[ExternalConnector] {source_id} failed: {result}")
            continue

        if result.status == "ok":
            metrics[result.source_id] = max(0, result.count)
            global_logger.info(
                f"[ExternalConnector] {result.source_id} ok count={result.count}"
            )
        elif result.status == "skip":
            global_logger.info(f"[ExternalConnector] {result.source_id} skipped: {result.detail}")
        else:
            global_logger.warning(
                f"[ExternalConnector] {result.source_id} error: {result.detail}"
            )

    return metrics
