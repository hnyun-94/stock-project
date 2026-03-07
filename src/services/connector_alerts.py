"""
External connector 운영 알림 서비스.

Codex reading guide:
1. `dispatch_connector_health_alerts()`가 현재 운영 알림의 단일 진입점입니다.
2. 입력은 SQLite에 누적된 `external_connector_runs` 집계이며, 출력은 텔레그램 관리자 알림입니다.
3. 동일 원인 반복 알림은 `connector_alert_events` 테이블 기반 쿨다운으로 억제합니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from src.services.notifier.telegram import TelegramSender
from src.utils.database import Database
from src.utils.logger import global_logger


@dataclass(frozen=True)
class ConnectorAlertThresholds:
    """운영 알림 판정 임계치."""

    min_samples: int
    failure_rate_1h: float
    failure_rate_24h: float
    avg_latency_ms: int
    cooldown_minutes: int


@dataclass(frozen=True)
class ConnectorAlertDecision:
    """알림 평가 결과."""

    source_id: str
    reasons: Tuple[str, ...]
    fingerprint: str
    subject: str
    content: str
    sent_chat_ids: Tuple[str, ...] = ()
    skipped_by_cooldown: bool = False


def _is_truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int_env(env_key: str, default_value: int) -> int:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return default_value
    try:
        parsed = int(raw)
    except ValueError:
        global_logger.warning("[ConnectorAlerts] %s 값이 정수가 아닙니다: %s", env_key, raw)
        return default_value
    return parsed if parsed > 0 else default_value


def _parse_float_env(env_key: str, default_value: float) -> float:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return default_value
    try:
        parsed = float(raw)
    except ValueError:
        global_logger.warning("[ConnectorAlerts] %s 값이 숫자가 아닙니다: %s", env_key, raw)
        return default_value
    return parsed if parsed >= 0 else default_value


def _load_thresholds() -> ConnectorAlertThresholds:
    """환경변수 기반 알림 임계치를 읽습니다."""
    return ConnectorAlertThresholds(
        min_samples=_parse_int_env("EXTERNAL_CONNECTOR_ALERT_MIN_SAMPLES", 2),
        failure_rate_1h=_parse_float_env("EXTERNAL_CONNECTOR_ALERT_FAILURE_RATE_1H", 0.5),
        failure_rate_24h=_parse_float_env("EXTERNAL_CONNECTOR_ALERT_FAILURE_RATE_24H", 0.3),
        avg_latency_ms=_parse_int_env("EXTERNAL_CONNECTOR_ALERT_AVG_LATENCY_MS", 4000),
        cooldown_minutes=_parse_int_env("EXTERNAL_CONNECTOR_ALERT_COOLDOWN_MINUTES", 180),
    )


def _resolve_admin_chat_ids() -> List[str]:
    """운영 알림 수신 chat_id 목록을 결정합니다."""
    raw = os.getenv("EXTERNAL_CONNECTOR_ALERT_CHAT_IDS", "").strip()
    if not raw:
        raw = os.getenv("ADMIN_TELEGRAM_CHAT_ID", "").strip()
    chat_ids = []
    for token in raw.split(","):
        chat_id = token.strip()
        if chat_id and chat_id not in chat_ids:
            chat_ids.append(chat_id)
    return chat_ids


def _format_rate(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def _trigger_labels(reason_codes: Iterable[str]) -> List[str]:
    label_map = {
        "latest_error": "방금 실행 실패",
        "failure_rate_1h": "1시간 실패율 경고",
        "failure_rate_24h": "24시간 실패율 경고",
        "latency_1h": "1시간 평균 지연 경고",
    }
    return [label_map.get(code, code) for code in reason_codes]


def _evaluate_reason_codes(
    summary_1h: Dict[str, object],
    summary_24h: Dict[str, object],
    thresholds: ConnectorAlertThresholds,
) -> List[str]:
    """1h/24h 윈도우를 기준으로 source 이상 징후를 판정합니다."""
    reasons: List[str] = []
    latest_status = str(summary_1h.get("latest_status") or summary_24h.get("latest_status") or "")
    sample_count_1h = int(summary_1h.get("sample_count") or 0)
    sample_count_24h = int(summary_24h.get("sample_count") or 0)
    failure_rate_1h = float(summary_1h.get("failure_rate") or 0.0)
    failure_rate_24h = float(summary_24h.get("failure_rate") or 0.0)
    avg_latency_1h = int(summary_1h.get("avg_latency_ms") or 0)

    if latest_status == "error":
        reasons.append("latest_error")
    if sample_count_1h >= thresholds.min_samples and failure_rate_1h >= thresholds.failure_rate_1h:
        reasons.append("failure_rate_1h")
    if sample_count_24h >= thresholds.min_samples and failure_rate_24h >= thresholds.failure_rate_24h:
        reasons.append("failure_rate_24h")
    if sample_count_1h >= 1 and avg_latency_1h >= thresholds.avg_latency_ms:
        reasons.append("latency_1h")
    return reasons


def _build_alert_message(
    source_id: str,
    reason_codes: List[str],
    summary_1h: Dict[str, object],
    summary_24h: Dict[str, object],
    thresholds: ConnectorAlertThresholds,
) -> Tuple[str, str]:
    """운영자가 바로 판단할 수 있는 알림 텍스트를 만듭니다."""
    labels = ", ".join(_trigger_labels(reason_codes))
    latest_status = str(summary_1h.get("latest_status") or summary_24h.get("latest_status") or "unknown")
    latest_detail = str(summary_1h.get("latest_detail") or summary_24h.get("latest_detail") or "")
    subject = f"[운영 알림] {source_id} 이상 감지"
    content = "\n".join(
        [
            f"source: {source_id}",
            f"감지 사유: {labels}",
            f"최근 상태: {latest_status}",
            (
                "1H 요약: "
                f"sample {int(summary_1h.get('sample_count') or 0)}, "
                f"success {int(summary_1h.get('success_count') or 0)}, "
                f"failure {int(summary_1h.get('failure_count') or 0)}, "
                f"failure_rate {_format_rate(float(summary_1h.get('failure_rate') or 0.0))}, "
                f"avg_latency {int(summary_1h.get('avg_latency_ms') or 0)}ms"
            ),
            (
                "24H 요약: "
                f"sample {int(summary_24h.get('sample_count') or 0)}, "
                f"success {int(summary_24h.get('success_count') or 0)}, "
                f"failure {int(summary_24h.get('failure_count') or 0)}, "
                f"failure_rate {_format_rate(float(summary_24h.get('failure_rate') or 0.0))}, "
                f"avg_latency {int(summary_24h.get('avg_latency_ms') or 0)}ms"
            ),
            (
                "임계치: "
                f"1H failure_rate>={_format_rate(thresholds.failure_rate_1h)}, "
                f"24H failure_rate>={_format_rate(thresholds.failure_rate_24h)}, "
                f"avg_latency>={thresholds.avg_latency_ms}ms"
            ),
            f"최근 상세: {latest_detail[:240] or 'n/a'}",
        ]
    )
    return subject, content


def dispatch_connector_health_alerts(
    db: Database,
    sender: Optional[TelegramSender] = None,
) -> List[ConnectorAlertDecision]:
    """최근 커넥터 실행 이력을 평가해 관리자 텔레그램 알림을 발송합니다."""
    if not _is_truthy(os.getenv("EXTERNAL_CONNECTOR_ALERTS_ENABLED", "true")):
        global_logger.info("[ConnectorAlerts] alerting disabled by env")
        return []

    chat_ids = _resolve_admin_chat_ids()
    if not chat_ids:
        global_logger.info("[ConnectorAlerts] admin chat id가 없어 알림 평가만 건너뜁니다.")
        return []

    thresholds = _load_thresholds()
    sender = sender or TelegramSender()
    summaries_1h = db.get_connector_health_summary(hours=1)
    summaries_24h = db.get_connector_health_summary(hours=24)
    source_ids = sorted(set(summaries_1h.keys()) | set(summaries_24h.keys()))
    decisions: List[ConnectorAlertDecision] = []

    for source_id in source_ids:
        summary_1h = summaries_1h.get(source_id, {"source_id": source_id})
        summary_24h = summaries_24h.get(source_id, {"source_id": source_id})
        reason_codes = _evaluate_reason_codes(summary_1h, summary_24h, thresholds)
        if not reason_codes:
            continue

        subject, content = _build_alert_message(
            source_id,
            reason_codes,
            summary_1h,
            summary_24h,
            thresholds,
        )
        fingerprint = f"{source_id}:{'|'.join(reason_codes)}"
        if db.has_recent_connector_alert(fingerprint, thresholds.cooldown_minutes):
            global_logger.info("[ConnectorAlerts] cooldown active: %s", fingerprint)
            decisions.append(
                ConnectorAlertDecision(
                    source_id=source_id,
                    reasons=tuple(reason_codes),
                    fingerprint=fingerprint,
                    subject=subject,
                    content=content,
                    skipped_by_cooldown=True,
                )
            )
            continue

        sent_chat_ids = []
        for chat_id in chat_ids:
            if sender.send_to_chat_id(chat_id, subject, content):
                sent_chat_ids.append(chat_id)

        if not sent_chat_ids:
            global_logger.warning("[ConnectorAlerts] alert send failed for %s", source_id)
            continue

        db.insert_connector_alert_event(
            source_id=source_id,
            alert_type=reason_codes[0],
            window_hours=24 if "failure_rate_24h" in reason_codes else 1,
            fingerprint=fingerprint,
            message=content,
        )
        decisions.append(
            ConnectorAlertDecision(
                source_id=source_id,
                reasons=tuple(reason_codes),
                fingerprint=fingerprint,
                subject=subject,
                content=content,
                sent_chat_ids=tuple(sent_chat_ids),
            )
        )
        global_logger.warning(
            "[ConnectorAlerts] sent source=%s reasons=%s chats=%s",
            source_id,
            ",".join(reason_codes),
            ",".join(sent_chat_ids),
        )

    return decisions
