"""
구조화된 리포트 조립 서비스.

Codex reading guide:
1. public entry point는 `build_report_payload()` 하나입니다.
2. builder 책임은 "무엇을 보여줄지"와 "왜 그렇게 판단하는지"를 카드형 payload로 만드는 것입니다.
3. formatter는 payload를 렌더링만 하므로, 사용자 가치 판단 로직은 이 파일에 모입니다.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

from src.models import CommunityPost, MarketIndex, NewsArticle, SearchTrend

_KST = ZoneInfo("Asia/Seoul")
_NEW_YORK = ZoneInfo("America/New_York")

_POSITIVE_KEYWORDS = (
    "상승", "반등", "실적", "수주", "강세", "기대", "확대", "증가",
    "개선", "회복", "계약", "출시", "수요", "채택", "순매수", "신고가",
)
_NEGATIVE_KEYWORDS = (
    "하락", "급락", "우려", "소송", "악재", "부진", "감소", "약세",
    "리스크", "규제", "지연", "둔화", "경쟁", "부담", "매도", "고환율",
)

_THEME_ALIAS_MAP = {
    "ai": "인공지능(AI)",
    "artificialintelligence": "인공지능(AI)",
    "인공지능": "인공지능(AI)",
    "ai반도체": "인공지능(AI)",
}

_GLOSSARY = {
    "KOSPI": "한국거래소의 대표 주가지수입니다. 한국 대형주 흐름을 볼 때 가장 많이 씁니다.",
    "KOSDAQ": "기술주와 중소형주 비중이 큰 한국 주가지수입니다. 변동성이 KOSPI보다 큰 편입니다.",
    "AI": "인공지능입니다. 사람의 언어, 이미지, 데이터를 컴퓨터가 학습해 처리하는 기술입니다.",
    "HBM": "고대역폭 메모리입니다. AI 서버에 많이 쓰이는 고성능 메모리로, 메모리 반도체 업황을 볼 때 중요합니다.",
    "GPU": "그래픽처리장치입니다. 지금은 AI 연산용 핵심 칩으로 더 많이 쓰입니다.",
    "파운드리": "반도체를 대신 생산해 주는 사업입니다. 설계만 하는 회사와 구분할 때 자주 씁니다.",
    "수급": "누가 사고파는지의 흐름입니다. 개인, 외국인, 기관의 매수·매도 방향을 뜻합니다.",
    "변동성": "가격이 얼마나 크게 흔들리는지를 말합니다. 클수록 짧은 기간에 오르내림이 큽니다.",
    "모멘텀": "주가를 움직이는 힘입니다. 실적, 뉴스, 정책, 수급 같은 재료가 여기에 해당합니다.",
    "밸류에이션": "현재 주가가 기업 가치에 비해 비싼지 싼지 판단하는 기준입니다.",
    "환율": "원화와 달러 같은 통화의 교환 비율입니다. 수출주와 외국인 수급에 영향을 줍니다.",
    "순매수": "판 것보다 산 금액이 더 큰 상태입니다. 수급이 받쳐주는지 볼 때 씁니다.",
}

_NOISE_FRAGMENTS = (
    "생성 실패",
    "retryerror",
    "clienterror",
    "resource_exhausted",
    "circuit open",
    "quota",
    "응답 누락",
    "api 호출 실패",
)


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
    return [sentence.strip() for sentence in normalized.splitlines() if sentence.strip()]


def _is_noise_line(text: str) -> bool:
    lowered = text.lower()
    return any(fragment in lowered for fragment in _NOISE_FRAGMENTS)


def _dedupe_list(items: Iterable[str]) -> List[str]:
    deduped: List[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


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
        if _is_noise_line(line):
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
            if normalized and not _is_noise_line(normalized) and normalized not in points:
                points.append(normalized)
            if len(points) >= max_items:
                return points[:max_items]

    return _dedupe_list(points)[:max_items]


def _score_texts(texts: Sequence[str]) -> int:
    joined = " ".join(texts)
    score = sum(1 for keyword in _POSITIVE_KEYWORDS if keyword in joined)
    score -= sum(1 for keyword in _NEGATIVE_KEYWORDS if keyword in joined)
    return score


def _tone_label(score: int) -> str:
    if score >= 2:
        return "긍정 쪽"
    if score <= -2:
        return "부정 쪽"
    return "중립"


def _normalize_theme_keyword(keyword: str) -> str:
    compact = re.sub(r"\s+", "", keyword.strip().lower())
    if compact in _THEME_ALIAS_MAP:
        return _THEME_ALIAS_MAP[compact]
    return keyword.strip()


def _dedupe_news_items(news_items: Iterable[NewsArticle]) -> List[NewsArticle]:
    deduped: List[NewsArticle] = []
    seen_titles: set[str] = set()
    for item in news_items:
        title = item.title.strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        deduped.append(item)
    return deduped


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _topic_subject(subject: str) -> str:
    trimmed = subject.strip()
    if not trimmed:
        return subject
    last_char = trimmed[-1]
    if "가" <= last_char <= "힣":
        has_final_consonant = (ord(last_char) - ord("가")) % 28 != 0
        return f"{trimmed}{'은' if has_final_consonant else '는'}"
    return f"{trimmed}는"


def _attach_particle(subject: str, final_consonant_particle: str, no_final_consonant_particle: str) -> str:
    trimmed = subject.strip()
    if not trimmed:
        return subject
    last_char = trimmed[-1]
    if "가" <= last_char <= "힣":
        has_final_consonant = (ord(last_char) - ord("가")) % 28 != 0
        particle = final_consonant_particle if has_final_consonant else no_final_consonant_particle
        return f"{trimmed}{particle}"
    return f"{trimmed}{no_final_consonant_particle}"


def _describe_risk_factor(joined_context: str) -> str:
    if _contains_any(joined_context, ("환율", "달러")):
        return "환율 부담"
    if _contains_any(joined_context, ("이란", "중동", "전쟁", "지정학")):
        return "지정학 변수"
    if _contains_any(joined_context, ("금리", "고용", "연준", "CPI", "물가")):
        return "금리·경기 변수"
    if _contains_any(joined_context, ("밸류에이션", "고평가", "과열")):
        return "밸류에이션 부담"
    return "기대 선반영"


def _describe_why_it_matters(subject: str, joined_context: str) -> str:
    topic_subject = _topic_subject(subject)
    if _contains_any(joined_context, ("HBM", "메모리", "DDR", "낸드")):
        return f"{topic_subject} AI 서버용 메모리 수요와 가격 변화에 민감해, 공급 확대가 확인되면 실적 기대가 빠르게 높아질 수 있습니다."
    if _contains_any(joined_context, ("GPU", "AI", "인공지능", "데이터센터")):
        return f"{topic_subject} AI 투자 사이클과 연결돼 있어, 고객사 투자 확대가 확인되면 주가 재평가 속도가 빨라질 수 있습니다."
    if _contains_any(joined_context, ("파운드리", "공정", "수율")):
        return f"{topic_subject} 첨단 공정 수주와 생산 안정성이 좋아져야 실적 개선 기대가 실제 가치로 이어지기 쉽습니다."
    if _contains_any(joined_context, ("외국인", "기관", "순매수", "수급")):
        return f"{topic_subject} 누가 사는지에 따라 단기 방향이 달라질 수 있어, 뉴스보다 수급 방향이 더 중요할 수 있습니다."
    if _contains_any(joined_context, ("환율", "달러")):
        return f"{topic_subject} 환율 변화가 수익성과 외국인 매매 심리에 함께 영향을 줄 수 있어, 높은 환율은 경계 포인트가 됩니다."
    if _contains_any(joined_context, ("이란", "중동", "전쟁", "지정학")):
        return f"{topic_subject} 실적과 무관한 지정학 이슈에도 흔들릴 수 있어, 외부 변수로 위험 선호가 갑자기 식을 수 있습니다."
    if _contains_any(joined_context, ("금리", "고용", "연준", "CPI", "물가")):
        return f"{topic_subject} 미국 경기와 금리 기대에 따라 성장주 선호가 바뀔 수 있어, 거시 지표 해석이 중요합니다."
    return f"{topic_subject} 관련 뉴스가 실제 숫자와 자금 유입으로 이어지는지 확인해야 판단의 신뢰도가 높아집니다."


def _describe_monitor_points(joined_context: str) -> str:
    if _contains_any(joined_context, ("HBM", "메모리", "DDR", "낸드")):
        return "HBM 가격, 공급 계약, 고객사 발주"
    if _contains_any(joined_context, ("GPU", "AI", "인공지능", "데이터센터")):
        return "AI 투자 확대 기사, 서버 수요, 고객사 CAPEX"
    if _contains_any(joined_context, ("파운드리", "공정", "수율")):
        return "수율 개선, 첨단 공정 수주, 고객사 확보"
    if _contains_any(joined_context, ("외국인", "기관", "순매수", "수급")):
        return "외국인·기관 수급, 거래대금, 장중 재매수"
    if _contains_any(joined_context, ("환율", "달러")):
        return "원/달러 환율, 외국인 자금 방향, 수출주 반응"
    if _contains_any(joined_context, ("이란", "중동", "전쟁", "지정학")):
        return "국제 뉴스 속보, 유가, 안전자산 선호"
    if _contains_any(joined_context, ("금리", "고용", "연준", "CPI", "물가")):
        return "미국 지표 발표, 금리 기대 변화, 성장주 반응"
    return "후속 기사, 실적 가이던스, 거래대금 변화"


def _build_context_views(subject: str, joined_context: str) -> tuple[str, str, str, str]:
    topic_subject = _topic_subject(subject)
    why_it_matters = _describe_why_it_matters(subject, joined_context)
    monitor_points = _describe_monitor_points(joined_context)
    risk_factor = _describe_risk_factor(joined_context)
    positive_view = f"{monitor_points} 중 두세 가지가 같은 방향으로 확인되면 {subject} 해석은 더 긍정적으로 바뀔 수 있습니다."
    neutral_view = f"{why_it_matters} 그래서 지금은 한 번의 뉴스보다 후속 숫자와 수급 확인이 먼저입니다."
    negative_view = f"{topic_subject} {risk_factor}가 다시 커지거나 {monitor_points}가 비면 조정 압력이 커질 수 있습니다."
    outlook = f"다음 확인 포인트는 {monitor_points}입니다. 이 신호가 이어지면 판단 강도를 높이고, 꺾이면 보수적으로 보는 편이 좋습니다."
    return positive_view, neutral_view, negative_view, outlook


def _pick_primary_market_forces(
    market_points: Sequence[str],
    focus_keywords: Sequence[str],
) -> tuple[str, str]:
    joined_context = " ".join(market_points)
    if _contains_any(joined_context, ("AI", "인공지능", "반도체", "HBM", "GPU")):
        support = f"{', '.join(focus_keywords[:2]) or 'AI·반도체'} 기대"
    elif _contains_any(joined_context, ("외국인", "기관", "순매수", "수급")):
        support = "수급 개선 기대"
    elif _contains_any(joined_context, ("실적", "수주", "계약")):
        support = "실적 기대"
    else:
        support = "일부 대형주로의 자금 쏠림"

    if _contains_any(joined_context, ("환율", "달러")):
        risk = "높은 환율 부담"
    elif _contains_any(joined_context, ("이란", "중동", "전쟁", "지정학")):
        risk = "지정학 변수"
    elif _contains_any(joined_context, ("금리", "고용", "연준", "CPI", "물가")):
        risk = "미국 경기·금리 변수"
    else:
        risk = "확신이 약한 혼조 장세"
    return support, risk


# Section B: snapshot and schedule helpers


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


def _connector_health_note(connector_rates: Dict[str, float]) -> tuple[str, bool]:
    if not connector_rates:
        return "누적 외부 데이터가 아직 적어 중기 판단 신뢰도는 낮습니다.", True
    weakest_source, weakest_rate = min(connector_rates.items(), key=lambda item: item[1])
    strongest_source, strongest_rate = max(connector_rates.items(), key=lambda item: item[1])
    if weakest_rate < 0.8:
        return f"{weakest_source} 성공률이 {weakest_rate * 100:.0f}%로 낮아, 해석은 보수적으로 하는 편이 좋습니다.", True
    return f"{strongest_source} 포함 주요 커넥터가 안정적입니다(최고 {strongest_rate * 100:.0f}%).", False


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
