"""
구조화된 리포트 조립 서비스.

Codex reading guide:
1. 이 모듈의 public entry point는 `build_report_payload()` 하나입니다.
2. 위 helper는 자유서술 입력을 짧은 bullet과 비교용 snapshot으로 정규화합니다.
3. payload 순서는 최종 리포트의 표시 순서와 동일하게 "최근 -> 장기"입니다.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence

from src.models import MarketIndex, NewsArticle, SearchTrend

# Section A: text normalization helpers


def _clean_markdown_line(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"^[-*]\s*", "", cleaned)
    cleaned = re.sub(r"^\d+\.\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("`", "").replace(">", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _truncate_text(text: str, limit: int = 110) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    normalized = re.sub(r"([.!?])\s+", r"\1\n", text)
    normalized = re.sub(r"다\.\s+", "다.\n", normalized)
    raw_sentences = normalized.splitlines()
    return [sentence.strip() for sentence in raw_sentences if sentence.strip()]


def extract_key_points(markdown_text: str, max_items: int = 3) -> List[str]:
    """자유서술형 Markdown에서 짧은 핵심 bullet을 추출합니다."""
    if not markdown_text:
        return []

    points: List[str] = []
    for raw_line in markdown_text.splitlines():
        if raw_line.lstrip().startswith("#"):
            continue
        line = _clean_markdown_line(raw_line)
        if not line:
            continue
        if re.fullmatch(r"[🌤️📈🎯💼🌡️🧭🕒🗺️💬⭐\-\s]+", line):
            continue
        if len(line) <= 4:
            continue
        if raw_line.lstrip().startswith(("-", "*")) or re.match(r"^\d+\.", raw_line.lstrip()):
            points.append(_truncate_text(line))
            continue
        for sentence in _split_sentences(line):
            normalized = _truncate_text(_clean_markdown_line(sentence))
            if normalized and normalized not in points:
                points.append(normalized)
            if len(points) >= max_items:
                return points[:max_items]

    deduped: List[str] = []
    seen: set[str] = set()
    for point in points:
        if point not in seen:
            deduped.append(point)
            seen.add(point)
        if len(deduped) >= max_items:
            break
    return deduped[:max_items]


# Section B: snapshot comparison helpers

def _deserialize_snapshot_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    for row in rows:
        payload = row.get("snapshot_json", "")
        try:
            loaded = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            loaded["timestamp"] = row.get("timestamp", "")
            loaded["headline"] = row.get("headline", "")
            snapshots.append(loaded)
    return snapshots


def _build_market_regime(sentiment_score: int, sentiment_label: str, market_points: Sequence[str]) -> str:
    if sentiment_score <= -20:
        return "방어적"
    if sentiment_score >= 20:
        return "공격적"
    joined = " ".join(market_points)
    if any(keyword in joined for keyword in ["불확실", "관망", "리스크", "경계"]):
        return "관망"
    return sentiment_label.replace("🟡 ", "").replace("🟢 ", "").replace("🟠 ", "").replace("🔴 ", "").replace("🔵 ", "")


def _recurring_focus_keywords(snapshots: Sequence[Dict[str, Any]], limit: int = 3) -> List[str]:
    counter: Counter[str] = Counter()
    for snapshot in snapshots:
        for keyword in snapshot.get("focus_keywords", []):
            if keyword:
                counter[str(keyword)] += 1
    return [keyword for keyword, _ in counter.most_common(limit)]


def _format_connector_health(connector_rates: Dict[str, float]) -> str:
    if not connector_rates:
        return "외부 커넥터 누적 데이터가 아직 부족합니다."
    weakest_source, weakest_rate = min(connector_rates.items(), key=lambda item: item[1])
    strongest_source, strongest_rate = max(connector_rates.items(), key=lambda item: item[1])
    if weakest_rate < 0.8:
        return f"{weakest_source} 안정성이 낮아({weakest_rate * 100:.0f}%) 해석 시 보수적으로 봐야 합니다."
    return f"{strongest_source} 포함 주요 커넥터가 안정적입니다(최고 {strongest_rate * 100:.0f}%)."


def _build_change_headlines(
    current_snapshot: Dict[str, Any],
    previous_snapshots: Sequence[Dict[str, Any]],
) -> List[str]:
    """직전 2회 리포트 대비 눈에 띄는 변화만 상단 headline용으로 추립니다."""
    headlines: List[str] = []
    prev = previous_snapshots[0] if previous_snapshots else {}
    prev_two_focus = set()
    for snapshot in previous_snapshots[:2]:
        prev_two_focus.update(snapshot.get("focus_keywords", []))

    if prev:
        current_score = int(current_snapshot.get("sentiment_score", 0))
        prev_score = int(prev.get("sentiment_score", 0))
        delta = current_score - prev_score
        if abs(delta) >= 15:
            direction = "개선" if delta > 0 else "둔화"
            headlines.append(
                f"시장 심리가 직전 리포트 대비 {direction}됐습니다 ({prev_score:+d} → {current_score:+d})."
            )

        current_regime = current_snapshot.get("market_regime", "")
        prev_regime = prev.get("market_regime", "")
        if current_regime and prev_regime and current_regime != prev_regime:
            headlines.append(f"장세 톤이 {prev_regime}에서 {current_regime}로 바뀌었습니다.")

        current_focus = set(current_snapshot.get("focus_keywords", []))
        new_focus = [keyword for keyword in current_focus if keyword not in prev_two_focus]
        if new_focus:
            headlines.append(f"새로 부각된 테마는 {', '.join(new_focus[:2])}입니다.")

        current_actions = current_snapshot.get("holding_actions", {})
        prev_actions = prev.get("holding_actions", {})
        for holding, action in current_actions.items():
            if holding in prev_actions and prev_actions[holding] != action:
                headlines.append(
                    f"{holding} 대응 의견이 '{prev_actions[holding]}'에서 '{action}'로 조정됐습니다."
                )
                break

    if not headlines:
        headlines.append(
            f"현재 시장 톤은 {current_snapshot.get('market_regime', '중립')}이며 심리 점수는 {current_snapshot.get('sentiment_score', 0):+d}입니다."
        )
    if len(headlines) < 2:
        focus_keywords = current_snapshot.get("focus_keywords", [])
        if focus_keywords:
            headlines.append(f"오늘 먼저 볼 테마는 {', '.join(focus_keywords[:3])}입니다.")
    if len(headlines) < 3:
        holding_actions = current_snapshot.get("holding_actions", {})
        if holding_actions:
            action_points = [f"{holding} {action}" for holding, action in list(holding_actions.items())[:2]]
            headlines.append(f"보유 종목 포인트는 {', '.join(action_points)}입니다.")

    return headlines[:3]


# Section C: public payload builder

def build_report_payload(
    *,
    user_name: str,
    market_summary_md: str,
    market_indices: Sequence[MarketIndex],
    market_news: Sequence[NewsArticle],
    datalab_trends: Sequence[SearchTrend],
    theme_sections: Sequence[Dict[str, str]],
    sentiment_score: int,
    sentiment_label: str,
    holding_insights: Sequence[Dict[str, str]],
    recent_report_rows: Sequence[Dict[str, Any]],
    weekly_report_rows: Sequence[Dict[str, Any]],
    monthly_report_rows: Sequence[Dict[str, Any]],
    connector_success_rate_7d: Dict[str, float],
    connector_success_rate_30d: Dict[str, float],
    avg_feedback_score_30d: float,
    avg_accuracy_30d: float,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """리포트 렌더링 payload와 저장용 스냅샷을 생성합니다."""
    market_points = extract_key_points(market_summary_md, max_items=3)
    previous_snapshots = _deserialize_snapshot_rows(recent_report_rows)
    weekly_snapshots = _deserialize_snapshot_rows(weekly_report_rows)
    monthly_snapshots = _deserialize_snapshot_rows(monthly_report_rows)

    theme_cards = []
    focus_keywords: List[str] = []
    for section in theme_sections[:3]:
        keyword = section.get("keyword", "").strip()
        if not keyword:
            continue
        focus_keywords.append(keyword)
        theme_cards.append(
            {
                "keyword": keyword,
                "points": extract_key_points(section.get("briefing_md", ""), max_items=3),
            }
        )

    holding_cards = []
    holding_actions: Dict[str, str] = {}
    for insight in holding_insights:
        symbol = insight.get("holding", "").strip()
        if not symbol:
            continue
        stance = insight.get("stance", "관찰")
        action = insight.get("action", "추가 확인")
        holding_actions[symbol] = stance
        holding_cards.append(
            {
                "holding": symbol,
                "stance": stance,
                "summary": _truncate_text(insight.get("summary", ""), limit=120),
                "action": _truncate_text(action, limit=100),
            }
        )

    recent_trend_points = []
    for article in list(market_news)[:2]:
        recent_trend_points.append(_truncate_text(article.title, 100))
    for trend in list(datalab_trends or [])[:2]:
        label = _truncate_text(f"{trend.keyword} 관심도 {trend.traffic or 'N/A'}", 100)
        if label not in recent_trend_points:
            recent_trend_points.append(label)

    daily_points = []
    for market_index in list(market_indices)[:3]:
        investor_summary = _truncate_text(market_index.investor_summary or "시장 지표", 70)
        daily_points.append(
            _truncate_text(f"{market_index.name} {market_index.value} | {investor_summary}", 120)
        )
    daily_points.append(f"시장 심리: {sentiment_score:+d} / {sentiment_label}")

    weekly_focus = _recurring_focus_keywords(weekly_snapshots)
    weekly_points = []
    if weekly_focus:
        weekly_points.append(f"최근 7일 반복 테마: {', '.join(weekly_focus[:3])}")
    weekly_points.append(f"최근 7일 리포트 누적: {len(weekly_report_rows)}회")
    weekly_points.append(_format_connector_health(connector_success_rate_7d))

    monthly_focus = _recurring_focus_keywords(monthly_snapshots)
    monthly_points = []
    if monthly_focus:
        monthly_points.append(f"최근 30일 장기 축 테마: {', '.join(monthly_focus[:3])}")
    if avg_accuracy_30d > 0:
        monthly_points.append(f"최근 30일 예측 적중률 평균: {avg_accuracy_30d * 100:.0f}%")
    else:
        monthly_points.append("최근 30일 예측 적중률 데이터는 아직 누적 중입니다.")
    if avg_feedback_score_30d > 0:
        monthly_points.append(f"최근 30일 사용자 만족도 평균: {avg_feedback_score_30d:.1f}/5")
    monthly_points.append(_format_connector_health(connector_success_rate_30d))

    market_regime = _build_market_regime(sentiment_score, sentiment_label, market_points)
    # snapshot은 비교에 필요한 최소 필드만 저장해 DB 부피를 억제합니다.
    current_snapshot = {
        "user_name": user_name,
        "market_regime": market_regime,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
        "focus_keywords": focus_keywords,
        "holding_actions": holding_actions,
        "market_points": market_points,
    }
    headline_changes = _build_change_headlines(current_snapshot, previous_snapshots)
    current_snapshot["headline_changes"] = headline_changes

    long_term_plan = []
    if monthly_focus:
        long_term_plan.append(f"장기 추적 테마는 {', '.join(monthly_focus[:3])} 중심으로 유지합니다.")
    else:
        long_term_plan.append(
            f"현재 강도가 높은 테마인 {', '.join(focus_keywords[:2]) or '시장 지수'}를 장기 감시축으로 둡니다."
        )
    long_term_plan.append(
        "단기 뉴스보다 1주/1개월 누적 변화와 적중률, 만족도 추세를 같이 보며 비중을 조정합니다."
    )
    long_term_plan.append(_format_connector_health(connector_success_rate_30d))

    # payload 순서는 화면 상단에서 하단으로 읽히는 실제 리포트 구조와 동일합니다.
    payload = {
        "title": "🌤️ 오늘의 주식 인사이트 리포트",
        "subtitle": "최근 흐름 중심으로 재구성한 5~10분 요약 리포트",
        "headline_changes": headline_changes,
        "recent_focus": market_points,
        "time_windows": [
            {
                "label": "1H",
                "title": "최근 동향",
                "bullets": recent_trend_points[:3] or ["최신 뉴스 데이터가 부족해 다음 실행에서 보강됩니다."],
            },
            {
                "label": "1D",
                "title": "오늘 장 마감 요약",
                "bullets": daily_points[:4],
            },
            {
                "label": "1W",
                "title": "최근 1주 반복 신호",
                "bullets": weekly_points[:3],
            },
            {
                "label": "1M",
                "title": "최근 1개월 장기 판단",
                "bullets": monthly_points[:4],
            },
        ],
        "theme_sections": theme_cards,
        "holding_sections": holding_cards,
        "long_term_plan": long_term_plan[:3],
        "footer_note": "본 리포트는 자동화된 AI 및 스크래핑 시스템에 의해 수집/편집되었습니다.",
    }
    return payload, current_snapshot
