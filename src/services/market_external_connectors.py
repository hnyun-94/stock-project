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
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

from src.crawlers.http_client import get_session
from src.services.market_source_governance import parse_active_source_ids
from src.utils.database import get_db
from src.utils.logger import global_logger


@dataclass(frozen=True)
class ConnectorResult:
    """External source collection result."""

    source_id: str
    status: str
    count: int
    detail: str
    latency_ms: int = 0
    extra_metrics: Optional[Dict[str, int]] = None


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


def _extract_fred_latest_value_x100(payload: Dict[str, Any]) -> Optional[int]:
    """Extracts the latest numeric FRED observation value and scales it by 100."""
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return None

    for row in observations:
        raw_value = str((row or {}).get("value", "")).strip()
        if not raw_value or raw_value == ".":
            continue
        try:
            return int(round(float(raw_value) * 100))
        except (TypeError, ValueError):
            continue
    return None


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


def _categorize_opendart_reports(rows: list[Dict[str, Any]]) -> Dict[str, int]:
    """Categorizes OpenDART reports to high-level buckets."""
    categories = {
        "earnings": 0,
        "financing": 0,
        "ownership": 0,
        "other": 0,
    }
    for row in rows:
        report_name = str(row.get("report_nm", ""))
        if any(keyword in report_name for keyword in ["잠정", "매출액", "영업", "분기", "반기", "사업보고서"]):
            categories["earnings"] += 1
        elif any(keyword in report_name for keyword in ["유상증자", "무상증자", "전환사채", "교환사채", "신주인수권"]):
            categories["financing"] += 1
        elif any(keyword in report_name for keyword in ["최대주주", "임원", "대량보유", "주식등의대량보유"]):
            categories["ownership"] += 1
        else:
            categories["other"] += 1
    return categories


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
        extra_metrics = {}
        if isinstance(rows, list):
            classified = _categorize_opendart_reports(rows)
            for category, value in classified.items():
                extra_metrics[f"opendart:{category}"] = value

        return ConnectorResult(
            source_id="opendart",
            status="ok",
            count=len(rows) if isinstance(rows, list) else 0,
            detail="opendart disclosure count collected",
            extra_metrics=extra_metrics or None,
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
            extra_metrics={"sec_edgar:registry_count": count},
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
        extra_metrics = {"fred:observation_count": len(observations)}
        latest_value_x100 = _extract_fred_latest_value_x100(payload if isinstance(payload, dict) else {})
        if latest_value_x100 is not None:
            extra_metrics["fred:series_value_x100"] = latest_value_x100
        return ConnectorResult(
            source_id="fred",
            status="ok",
            count=len(observations),
            detail="fred observation sample collected",
            extra_metrics=extra_metrics,
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


async def _execute_handler_with_timing(source_id: str, handler: ConnectorHandler) -> ConnectorResult:
    """Executes connector handler with latency telemetry."""
    started = time.perf_counter()
    try:
        result = await handler()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ConnectorResult(
            source_id=result.source_id,
            status=result.status,
            count=result.count,
            detail=result.detail,
            latency_ms=elapsed_ms,
            extra_metrics=result.extra_metrics,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ConnectorResult(
            source_id=source_id,
            status="error",
            count=0,
            detail=f"unhandled exception: {exc}",
            latency_ms=elapsed_ms,
        )


def _expand_result_metrics(result: ConnectorResult, metrics: Dict[str, int]) -> None:
    """Adds source-level and extra metrics from connector result."""
    metrics[result.source_id] = max(0, result.count)
    if result.extra_metrics:
        for key, value in result.extra_metrics.items():
            metrics[key] = max(0, value)


def render_external_connector_telemetry_markdown(results: list[ConnectorResult]) -> str:
    """Renders connector runtime status to markdown section."""
    if not results:
        return ""

    lines = ["## 🛰 외부 소스 텔레메트리"]
    for result in results:
        lines.append(
            f"- {result.source_id}: status `{result.status}`, "
            f"count {result.count}건, latency {result.latency_ms}ms"
        )
        if result.status != "ok":
            lines.append(f"  - detail: {result.detail}")
    return "\n".join(lines)


def _persist_connector_result(result: ConnectorResult) -> None:
    """Persists connector telemetry into SQLite when enabled."""
    if not _is_truthy(os.getenv("EXTERNAL_CONNECTOR_TELEMETRY_DB", "true")):
        return

    try:
        db = get_db()
        db.insert_connector_run(
            source_id=result.source_id,
            status=result.status,
            count=result.count,
            latency_ms=result.latency_ms,
            detail=result.detail,
        )
        if result.status == "ok":
            db.insert_connector_metric_point(
                source_id=result.source_id,
                metric_key=f"{result.source_id}:count",
                metric_value=result.count,
            )
            if result.extra_metrics:
                for metric_key, metric_value in result.extra_metrics.items():
                    db.insert_connector_metric_point(
                        source_id=result.source_id,
                        metric_key=metric_key,
                        metric_value=metric_value,
                    )
    except Exception as exc:
        global_logger.warning(
            f"[ExternalConnector] telemetry DB save failed ({result.source_id}): {exc}"
        )


async def collect_external_source_snapshot(
    active_source_ids: Optional[list[str]] = None,
) -> tuple[Dict[str, int], list[ConnectorResult]]:
    """Collects external source metrics with detailed telemetry."""
    if not _is_truthy(os.getenv("EXTERNAL_CONNECTORS_ENABLED", "false")):
        return {}, []

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
        tasks.append(_execute_handler_with_timing(source_id, handler))
        task_sources.append(source_id)

    if not tasks:
        return {}, []

    results = await asyncio.gather(*tasks)
    metrics: Dict[str, int] = {}
    telemetry: list[ConnectorResult] = []

    for source_id, result in zip(task_sources, results):
        telemetry.append(result)
        _persist_connector_result(result)

        if result.status == "ok":
            _expand_result_metrics(result, metrics)
            global_logger.info(
                f"[ExternalConnector] {result.source_id} ok "
                f"count={result.count}, latency={result.latency_ms}ms"
            )
        elif result.status == "skip":
            global_logger.info(f"[ExternalConnector] {result.source_id} skipped: {result.detail}")
        else:
            global_logger.warning(
                f"[ExternalConnector] {result.source_id} error: {result.detail}"
            )

    return metrics, telemetry


async def collect_external_source_metrics(
    active_source_ids: Optional[list[str]] = None,
) -> Dict[str, int]:
    """Backwards-compatible wrapper returning only count metrics."""
    metrics, _ = await collect_external_source_snapshot(active_source_ids=active_source_ids)
    return metrics
