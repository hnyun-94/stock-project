"""
시장 신호 요약/통계 생성 모듈.

역할:
1. 수집된 지수 시계열에서 수익률/변동성/추세 라벨을 계산합니다.
2. 공시 이벤트 건수, 검색 관심도 변화율과 결합해 스냅샷을 생성합니다.
3. 리포트 본문에 삽입 가능한 Markdown 통계 섹션을 반환합니다.
"""

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import pstdev
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class PricePoint:
    """단일 시점 가격 데이터."""

    date: str
    close: float


@dataclass(frozen=True)
class IndexSignal:
    """지수별 계산 결과."""

    symbol: str
    change_1d_pct: Optional[float]
    change_5d_pct: Optional[float]
    volatility_20d_pct: Optional[float]
    trend_label: str


def _sort_points(points: Sequence[PricePoint]) -> List[PricePoint]:
    return sorted(points, key=lambda item: item.date)


def _pct_change(current: float, base: float) -> Optional[float]:
    if base == 0:
        return None
    return (current - base) / base * 100.0


def _calc_annualized_volatility(returns: Sequence[float]) -> Optional[float]:
    if len(returns) < 2:
        return None
    return pstdev(returns) * sqrt(252) * 100.0


def build_index_signal(symbol: str, points: Sequence[PricePoint]) -> IndexSignal:
    """지수 시계열을 기반으로 핵심 통계치를 계산합니다."""
    sorted_points = _sort_points(points)
    closes = [point.close for point in sorted_points if point.close > 0]
    if not closes:
        return IndexSignal(symbol, None, None, None, "insufficient_data")

    change_1d = None
    if len(closes) >= 2:
        change_1d = _pct_change(closes[-1], closes[-2])

    change_5d = None
    if len(closes) >= 6:
        change_5d = _pct_change(closes[-1], closes[-6])

    daily_returns = [
        _pct_change(closes[idx], closes[idx - 1]) or 0.0
        for idx in range(1, len(closes))
    ]
    volatility_20d = None
    if len(daily_returns) >= 20:
        volatility_20d = _calc_annualized_volatility(daily_returns[-20:])

    trend_label = "mixed"
    if change_1d is None and change_5d is None:
        trend_label = "insufficient_data"
    elif (change_1d or 0) > 0 and (change_5d or 0) > 0:
        trend_label = "uptrend"
    elif (change_1d or 0) < 0 and (change_5d or 0) < 0:
        trend_label = "downtrend"

    return IndexSignal(
        symbol=symbol,
        change_1d_pct=change_1d,
        change_5d_pct=change_5d,
        volatility_20d_pct=volatility_20d,
        trend_label=trend_label,
    )


def build_market_snapshot(
    index_series: Dict[str, Sequence[PricePoint]],
    event_counts: Optional[Dict[str, int]] = None,
    keyword_trend_change_pct: Optional[float] = None,
) -> Dict[str, object]:
    """전체 시장 스냅샷을 생성합니다."""
    signals = {
        symbol: asdict(build_index_signal(symbol, points))
        for symbol, points in index_series.items()
    }
    return {
        "indices": signals,
        "event_counts": event_counts or {},
        "keyword_trend_change_pct": keyword_trend_change_pct,
    }


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"


def render_market_snapshot_markdown(snapshot: Dict[str, object]) -> str:
    """시장 스냅샷을 Markdown 섹션으로 렌더링합니다."""
    lines = ["## 📊 정량 통계 스냅샷"]

    indices = snapshot.get("indices", {})
    if isinstance(indices, dict):
        for symbol, metrics in indices.items():
            if not isinstance(metrics, dict):
                continue
            lines.append(
                f"- {symbol}: 1D {_fmt_pct(metrics.get('change_1d_pct'))}, "
                f"5D {_fmt_pct(metrics.get('change_5d_pct'))}, "
                f"20D 변동성 {_fmt_pct(metrics.get('volatility_20d_pct'))}, "
                f"추세 `{metrics.get('trend_label', 'unknown')}`"
            )

    event_counts = snapshot.get("event_counts", {})
    if isinstance(event_counts, dict) and event_counts:
        formatted = ", ".join(f"{k} {v}건" for k, v in event_counts.items())
        lines.append(f"- 공시 이벤트 카운트: {formatted}")

    keyword_change = snapshot.get("keyword_trend_change_pct")
    if isinstance(keyword_change, (int, float)):
        lines.append(f"- 키워드 관심도 변화율: {_fmt_pct(float(keyword_change))}")

    return "\n".join(lines)


def to_price_points(rows: Iterable[Dict[str, object]]) -> List[PricePoint]:
    """dict 시퀀스를 PricePoint 리스트로 변환합니다."""
    points: List[PricePoint] = []
    for row in rows:
        date = str(row.get("date", "")).strip()
        close_raw = row.get("close")
        if not date or close_raw is None:
            continue
        try:
            close = float(close_raw)
        except (TypeError, ValueError):
            continue
        points.append(PricePoint(date=date, close=close))
    return points
