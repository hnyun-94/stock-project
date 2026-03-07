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
from datetime import date, datetime, timedelta
from datetime import time as dt_time
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
    "OpenDART": "금융감독원 전자공시 시스템입니다. 기업의 실적, 자금조달, 지분 변화 공시를 확인할 때 씁니다.",
    "FRED": "미국 세인트루이스 연은의 경제지표 데이터 서비스입니다. 금리·물가·고용 같은 거시 지표를 볼 때 자주 씁니다.",
    "SEC": "미국 증권거래위원회입니다. 공시와 상장 기업 데이터를 제공해 미국 시장 보조 지표로 활용할 수 있습니다.",
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

_PORTAL_NOISE_FRAGMENTS = (
    "언론사가 선정한 주요기사",
    "주요기사 혹은 심층기획 기사입니다",
    "혹은 심층기획 기사입니다",
    "네이버 메인에서 보고 싶은 언론사를 구독하세요",
    "언론사 선정",
)

_LOW_SIGNAL_TITLES = {
    "옵션 가이드",
    "Keep에 바로가기",
}

_LOW_SIGNAL_FRAGMENTS = (
    "바로가기",
    "구독하세요",
    "주유소 북새통",
    "오찬종의 매일뉴욕",
)

_MARKET_SIGNAL_KEYWORDS = (
    "코스피", "코스닥", "증시", "주식", "환율", "달러", "외국인", "기관",
    "반도체", "HBM", "GPU", "AI", "인공지능", "실적", "수주", "공시",
    "엔비디아", "삼성전자", "SK하이닉스", "금리", "연준", "유가",
)

_MARKET_WEAK_SIGNAL_KEYWORDS = (
    "중동", "전쟁", "안전자산", "유가", "경기", "고용",
)

_HIGH_SIGNAL_KEYWORDS = (
    "실적", "수주", "계약", "발주", "환율", "금리", "관세", "가이던스",
    "매출", "영업이익", "CAPEX", "공급", "HBM", "GPU", "데이터센터",
    "메모리", "공시", "순매수", "순매도", "출하", "규제", "고용", "유가",
)

_LOW_VALUE_SIGNAL_KEYWORDS = (
    "채용", "성과급", "총파업", "파업", "주총", "행동주의", "연봉",
    "행사", "포럼", "인터뷰", "복지", "브랜드", "마케팅",
)

_POLISH_REPLACEMENTS = {
    "필요없는": "필요 없는",
    "인공지능반도체": "인공지능 반도체",
    "환율 부담가": "환율 부담이",
    "기대 선반영가": "기대 선반영이",
    "지정학 변수가": "지정학 변수가",
}

_HOLDING_WATCHPOINTS = {
    "삼성전자": ["HBM 납품 확대", "파운드리 수율", "대형 고객사 CAPEX"],
    "SK하이닉스": ["HBM ASP", "메모리 가격", "주요 고객사 발주"],
    "엔비디아": ["GPU 출하", "데이터센터 매출", "대중국 규제"],
}

_HOLDING_WHY_IT_MATTERS = {
    "삼성전자": "삼성전자는 메모리와 파운드리를 함께 보는 종목이라, HBM 확장과 첨단 공정 안정화가 동시에 확인돼야 재평가 폭이 커집니다.",
    "SK하이닉스": "SK하이닉스는 AI 서버용 메모리 수요의 직접 수혜주라, HBM 가격과 고객사 발주 변화가 실적 기대에 바로 연결되기 쉽습니다.",
    "엔비디아": "엔비디아는 AI 투자 사이클의 중심축이라, 데이터센터 투자와 GPU 출하 흐름이 꺾이는지가 가장 중요한 판단 포인트입니다.",
}

_LEARNING_TOPIC_LIBRARY = {
    "환율": {
        "definition": "환율은 원화와 달러 같은 통화의 교환 비율입니다.",
        "why_today": "오늘 리포트에서 환율은 외국인 수급과 시장 불안 심리를 함께 해석하는 기준으로 중요했습니다.",
        "how_to_read": "보통 원/달러 환율이 빠르게 오르면 시장이 불안을 더 크게 느낀다고 해석하는 경우가 많습니다.",
    },
    "수급": {
        "definition": "수급은 개인, 외국인, 기관 중 누가 더 많이 사고파는지의 흐름입니다.",
        "why_today": "오늘 리포트에서는 지수 숫자보다 누가 시장을 지지하고 있는지가 더 중요한 판단 포인트였습니다.",
        "how_to_read": "보통 외국인과 기관이 같은 방향으로 순매수하면 단기 해석의 신뢰도가 조금 더 높아집니다.",
    },
    "금리": {
        "definition": "금리는 돈의 가격으로, 높아지면 성장주에 부담이 되고 낮아지면 미래 기대주에 우호적일 수 있습니다.",
        "why_today": "오늘 리포트에서 금리는 환율과 함께 시장 스타일이 공격형인지 방어형인지 판단하는 배경 변수입니다.",
        "how_to_read": "보통 금리 기대가 올라가면 비싸게 평가된 성장주는 흔들리고, 낮아지면 다시 선호를 받을 수 있습니다.",
    },
    "HBM": {
        "definition": "HBM은 AI 서버에 많이 쓰이는 고성능 메모리입니다.",
        "why_today": "오늘 리포트에서는 AI 반도체와 메모리 수요를 읽는 핵심 축으로 반복 등장했습니다.",
        "how_to_read": "보통 HBM 가격과 고객사 발주가 같이 좋아지면 메모리 관련 종목 기대도 함께 커집니다.",
    },
    "AI": {
        "definition": "AI는 데이터를 학습해 문장, 이미지, 예측을 처리하는 인공지능 기술입니다.",
        "why_today": "오늘 리포트에서 AI는 시장 전체의 성장 기대와 반도체 투자 흐름을 설명하는 중심 테마였습니다.",
        "how_to_read": "보통 AI 뉴스는 단순 화제보다 실제 고객사 투자, 데이터센터 수요, 실적 연결 여부가 더 중요합니다.",
    },
}


# Section A: text normalization helpers


def _clean_markdown_line(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"^[-*]\s*", "", cleaned)
    cleaned = re.sub(r"^\d+\.\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("`", "").replace(">", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _polish_signal_text(text: str) -> str:
    polished = str(text or "")
    for source, target in _POLISH_REPLACEMENTS.items():
        polished = polished.replace(source, target)
    polished = re.sub(
        r"(?<=[가-힣])(?=(삼성전자|SK하이닉스|엔비디아|채용|총파업|반도체|인공지능|금리|환율))",
        " ",
        polished,
    )
    polished = re.sub(r"(?<=[A-Za-z0-9])(?=[가-힣])", " ", polished)
    polished = re.sub(r"(?<=[가-힣])(?=[A-Za-z0-9])", " ", polished)
    return polished


def _normalize_signal_text(text: str) -> str:
    cleaned = _clean_markdown_line(_polish_signal_text(text or ""))
    for fragment in _PORTAL_NOISE_FRAGMENTS:
        cleaned = cleaned.replace(fragment, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,:;|-")
    return re.sub(r"\s+", " ", cleaned).strip()


def _truncate_text(text: str, limit: int = 110) -> str:
    compact = _normalize_signal_text(text)
    if len(compact) <= limit:
        return compact

    sentences = _split_sentences(compact)
    if sentences:
        collected: List[str] = []
        for sentence in sentences:
            candidate = " ".join(collected + [sentence]).strip()
            if len(candidate) <= limit:
                collected.append(sentence)
                continue
            break
        if collected:
            return " ".join(collected)
        return sentences[0]

    soft_chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[,:;])\s+|\s+-\s+", compact)
        if chunk.strip()
    ]
    if soft_chunks:
        collected_chunks: List[str] = []
        for chunk in soft_chunks:
            candidate = " ".join(collected_chunks + [chunk]).strip()
            if len(candidate) <= limit:
                collected_chunks.append(chunk)
                continue
            break
        if collected_chunks:
            return " ".join(collected_chunks).strip()

    return compact


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    normalized = re.sub(r"([.!?])\s+", r"\1\n", text)
    normalized = re.sub(r"다\.\s+", "다.\n", normalized)
    return [sentence.strip() for sentence in normalized.splitlines() if sentence.strip()]


def _is_noise_line(text: str) -> bool:
    lowered = _normalize_signal_text(text).lower()
    return any(fragment in lowered for fragment in _NOISE_FRAGMENTS)


def _is_low_signal_text(text: str) -> bool:
    raw = str(text or "").strip()
    lowered_raw = raw.lower()
    normalized = _normalize_signal_text(raw)
    if not normalized:
        return True
    if not re.search(r"[0-9A-Za-z가-힣]", normalized):
        return True
    if _is_noise_line(normalized):
        return True
    if any(fragment in lowered_raw for fragment in _PORTAL_NOISE_FRAGMENTS):
        return True
    if any(fragment.lower() in lowered_raw for fragment in _LOW_SIGNAL_FRAGMENTS):
        return True
    if normalized in _LOW_SIGNAL_TITLES:
        return True
    if "구독하세요" in lowered_raw or "주요기사" in lowered_raw:
        return True
    return False


def _dedupe_list(items: Iterable[str]) -> List[str]:
    deduped: List[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_signal_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _clean_text_items(items: Iterable[str], limit: int = 3) -> List[str]:
    cleaned: List[str] = []
    for item in _dedupe_list(items):
        if _is_low_signal_text(item):
            continue
        cleaned.append(_truncate_text(item, 120))
        if len(cleaned) >= limit:
            break
    return cleaned


def _build_related_links(
    news_items: Iterable[NewsArticle],
    limit: int = 2,
) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in news_items:
        url = str(item.link or "").strip()
        label = _truncate_text(item.title or "", 90)
        if not url or not label or _is_low_signal_text(label) or url in seen_urls:
            continue
        seen_urls.add(url)
        links.append({"label": label, "url": url})
        if len(links) >= limit:
            break
    return links


def extract_key_points(markdown_text: str, max_items: int = 3) -> List[str]:
    """자유서술형 Markdown에서 짧은 핵심 bullet을 추출합니다."""
    if not markdown_text:
        return []

    points: List[str] = []
    for raw_line in markdown_text.splitlines():
        if raw_line.lstrip().startswith("#"):
            continue
        line = _normalize_signal_text(raw_line)
        if not line:
            continue
        if _is_low_signal_text(line):
            continue
        if re.fullmatch(r"[🌤️📈🎯💼🌡️🧭🕒🗺️💬⭐\-\s]+", line):
            continue
        if len(line) <= 4:
            continue
        if raw_line.lstrip().startswith(("-", "*")) or re.match(r"^\d+\.", raw_line.lstrip()):
            points.append(_truncate_text(line))
            continue
        for sentence in _split_sentences(line):
            normalized = _truncate_text(_normalize_signal_text(sentence))
            if normalized and not _is_low_signal_text(normalized) and normalized not in points:
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


def _signal_news_items(news_items: Iterable[NewsArticle], limit: int = 3) -> List[NewsArticle]:
    scored_items: List[tuple[int, int, NewsArticle]] = []
    for index, item in enumerate(_dedupe_news_items(news_items)):
        title = _normalize_signal_text(item.title)
        summary = _normalize_signal_text(item.summary or "")
        if _is_low_signal_text(title):
            continue
        if summary and _is_low_signal_text(summary):
            summary = ""
        joined_text = f"{title} {summary}"
        relevance_score = sum(2 for keyword in _MARKET_SIGNAL_KEYWORDS if keyword in joined_text)
        relevance_score += sum(1 for keyword in _MARKET_WEAK_SIGNAL_KEYWORDS if keyword in joined_text)
        relevance_score += sum(3 for keyword in _HIGH_SIGNAL_KEYWORDS if keyword in joined_text)
        relevance_score -= sum(2 for keyword in _LOW_VALUE_SIGNAL_KEYWORDS if keyword in joined_text)
        relevance_score -= sum(3 for fragment in _LOW_SIGNAL_FRAGMENTS if fragment in joined_text)
        if summary:
            relevance_score += 1
        scored_items.append(
            (
                relevance_score,
                -index,
                NewsArticle(
                    title=title,
                    link=item.link,
                    summary=summary or None,
                    date=item.date,
                    publisher=item.publisher,
                ),
            )
        )

    if not scored_items:
        return []

    scored_items.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    if any(score > 0 for score, _, _ in scored_items):
        scored_items = [entry for entry in scored_items if entry[0] >= 0]

    filtered: List[NewsArticle] = []
    for _, _, article in scored_items:
        filtered.append(
            NewsArticle(
                title=article.title,
                link=article.link,
                summary=article.summary,
                date=article.date,
                publisher=article.publisher,
            )
        )
        if len(filtered) >= limit:
            break
    return filtered


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
    if subject in _HOLDING_WHY_IT_MATTERS:
        return _HOLDING_WHY_IT_MATTERS[subject]
    if subject in {"시장", "오늘 장", "최근 동향", "국장 개장 전 공통 이슈", "국장 마감 직후 공통 이슈", "미장 개장 전 공통 이슈", "미장 마감 직후 공통 이슈"}:
        return "시장 판단은 지수 숫자 하나보다 수급, 환율, 거시 변수, 핵심 뉴스가 같은 방향을 가리키는지 함께 보는 것이 더 중요합니다."
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
    for holding, points in _HOLDING_WATCHPOINTS.items():
        if holding in joined_context:
            return ", ".join(points)
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


def _split_watch_points(raw_text: str) -> List[str]:
    items = [item.strip() for item in raw_text.split(",") if item.strip()]
    return _clean_text_items(items, limit=3)


def _summary_needs_rebuild(summary: str) -> bool:
    normalized = _normalize_signal_text(summary)
    if _is_low_signal_text(normalized):
        return True
    generic_fragments = ("최근 이슈는", "이며 톤은", "직접 연계 뉴스가 적어")
    return any(fragment in normalized for fragment in generic_fragments)


def _build_context_views(subject: str, joined_context: str) -> tuple[str, str, str, str]:
    topic_subject = _topic_subject(subject)
    why_it_matters = _describe_why_it_matters(subject, joined_context)
    monitor_points = _describe_monitor_points(joined_context)
    risk_factor = _describe_risk_factor(joined_context)
    positive_view = f"{monitor_points}가 같이 좋아지면 상방 해석이 쉬워집니다."
    if subject in {"시장", "오늘 장", "최근 동향", "국장 개장 전 공통 이슈", "국장 마감 직후 공통 이슈", "미장 개장 전 공통 이슈", "미장 마감 직후 공통 이슈"}:
        neutral_view = "지금은 한 방향으로 베팅하기보다 수급·환율·거시 지표가 같은 쪽으로 모이는지 확인하는 편이 좋습니다."
    else:
        neutral_view = f"{why_it_matters} 그래서 지금은 후속 숫자 확인이 먼저입니다."
    negative_view = (
        f"{topic_subject} {_attach_particle(risk_factor, '이', '가')} 커지거나 "
        f"{_attach_particle(monitor_points, '이', '가')} 약하면 보수적으로 봐야 합니다."
    )
    outlook = f"다음 체크포인트는 {monitor_points}입니다."
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
                counter[_normalize_theme_keyword(str(keyword))] += 1
    return [keyword for keyword, _ in counter.most_common(limit)]


def _connector_health_note(connector_rates: Dict[str, float]) -> tuple[str, bool]:
    if not connector_rates:
        return "누적 외부 데이터가 아직 적어 중기 판단 신뢰도는 낮습니다.", True
    weakest_source, weakest_rate = min(connector_rates.items(), key=lambda item: item[1])
    strongest_source, strongest_rate = max(connector_rates.items(), key=lambda item: item[1])
    if weakest_rate < 0.8:
        return f"{weakest_source} 성공률이 {weakest_rate * 100:.0f}%로 낮아, 해석은 보수적으로 하는 편이 좋습니다.", True
    return f"{strongest_source} 포함 주요 커넥터가 안정적입니다(최고 {strongest_rate * 100:.0f}%).", False


def _format_rate_text(rate: float) -> str:
    return f"{rate * 100:.0f}%"


def _format_metric_value(metric_key: str, value: Optional[float]) -> str:
    if value is None:
        return "데이터 부족"
    if metric_key.endswith("series_value_x100"):
        return f"{value / 100:.2f}%"
    return f"{int(round(value))}건"


def _format_metric_delta(metric_key: str, value: Optional[float]) -> str:
    if value is None:
        return "비교값 부족"
    if metric_key.endswith("series_value_x100"):
        return f"{value / 100:+.2f}%p"
    return f"{int(round(value)):+d}건"


def _connector_rollup_label(row: Dict[str, Any]) -> str:
    success_rate = float(row.get("success_rate") or 0.0)
    avg_latency_ms = int(row.get("avg_latency_ms") or 0)
    if success_rate >= 0.95 and avg_latency_ms < 1500:
        return "안정"
    if success_rate < 0.8 or avg_latency_ms >= 4000:
        return "주의"
    return "보통"


def _build_data_quality_card(
    *,
    connector_daily_rollups_7d: Sequence[Dict[str, Any]],
    recent_connector_failures_7d: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not connector_daily_rollups_7d:
        return None

    latest_by_source: Dict[str, Dict[str, Any]] = {}
    for row in connector_daily_rollups_7d:
        source_id = str(row.get("source_id") or "")
        if not source_id:
            continue
        if source_id not in latest_by_source:
            latest_by_source[source_id] = row

    latest_rows = list(latest_by_source.values())
    if not latest_rows:
        return None

    strongest_row = max(
        latest_rows,
        key=lambda row: (float(row.get("success_rate") or 0.0), -int(row.get("avg_latency_ms") or 0)),
    )
    weakest_row = min(
        latest_rows,
        key=lambda row: (float(row.get("success_rate") or 0.0), -int(row.get("avg_latency_ms") or 0)),
    )
    warning_count = sum(1 for row in latest_rows if _connector_rollup_label(row) == "주의")

    if warning_count == 0:
        summary = "최근 7일 외부 데이터 수집 품질은 전반적으로 안정적이라, 리포트 해석의 기본 신뢰도는 양호한 편입니다."
    elif warning_count == len(latest_rows):
        summary = "최근 7일 외부 데이터 수집 품질은 전반적으로 불안정해, 숫자 해석을 평소보다 더 보수적으로 보는 편이 좋습니다."
    else:
        summary = "최근 7일 외부 데이터 수집 품질은 혼조입니다. 안정적인 소스와 주의가 필요한 소스가 함께 보입니다."

    details = []
    details.append(
        (
            f"안정 소스: {strongest_row['source_id']} | 최근 {strongest_row['day']} 성공률 "
            f"{_format_rate_text(float(strongest_row['success_rate']))}, 평균 지연 {int(strongest_row['avg_latency_ms'])}ms"
        )
    )
    if strongest_row["source_id"] == weakest_row["source_id"]:
        details.append(
            (
                f"최근 관찰치: {weakest_row['source_id']} | 실패 {int(weakest_row['failure_count'])}회, "
                f"표본 {int(weakest_row['sample_count'])}회"
            )
        )
    else:
        details.append(
            (
                f"주의 소스: {weakest_row['source_id']} | 최근 {weakest_row['day']} 성공률 "
                f"{_format_rate_text(float(weakest_row['success_rate']))}, 평균 지연 {int(weakest_row['avg_latency_ms'])}ms, "
                f"실패 {int(weakest_row['failure_count'])}회"
            )
        )

    if recent_connector_failures_7d:
        failure_notes = []
        seen: set[str] = set()
        for row in recent_connector_failures_7d:
            note = f"{row.get('source_id')}({_truncate_text(str(row.get('detail') or '오류 상세 없음'), 40)})"
            if note in seen:
                continue
            seen.add(note)
            failure_notes.append(note)
            if len(failure_notes) >= 2:
                break
        details.append(f"최근 오류 사유: {', '.join(failure_notes)}")
    else:
        details.append(f"최근 7일 관찰 source는 {len(latest_rows)}개입니다.")

    card = _build_card(
        summary=summary,
        details=details,
        positive_view="최근 며칠 동안 높은 성공률이 유지되면, 리포트의 근거 데이터도 조금 더 자신 있게 해석할 수 있습니다.",
        neutral_view="데이터 품질은 시장 방향 그 자체보다, 지금 보고 있는 해석을 얼마나 믿을지 판단하는 보조 지표로 보면 됩니다.",
        negative_view="성공률이 낮거나 평균 지연이 길면 오늘 해석이 실제 시장보다 늦거나 일부 신호를 놓쳤을 가능성을 열어둬야 합니다.",
        outlook="다음 리포트에서는 같은 소스가 다시 흔들리는지, 아니면 하루짜리 일시 장애였는지를 같이 확인하세요.",
    )
    card["table_headers"] = ["날짜", "소스", "성공률", "평균 지연", "판단"]
    card["table_rows"] = [
        [
            str(row.get("day") or ""),
            str(row.get("source_id") or ""),
            _format_rate_text(float(row.get("success_rate") or 0.0)),
            f"{int(row.get('avg_latency_ms') or 0)}ms",
            _connector_rollup_label(row),
        ]
        for row in list(connector_daily_rollups_7d)[:6]
    ]
    return card


def _find_metric_trend(
    connector_metric_trends_7d: Sequence[Dict[str, Any]],
    source_id: str,
    metric_key: str,
) -> Optional[Dict[str, Any]]:
    for row in connector_metric_trends_7d:
        if row.get("source_id") == source_id and row.get("metric_key") == metric_key:
            return row
    return None


def _build_reliability_badge(
    *,
    connector_success_rate_7d: Dict[str, float],
    connector_daily_rollups_7d: Sequence[Dict[str, Any]],
    connector_metric_trends_7d: Sequence[Dict[str, Any]],
    reference_time: Optional[datetime],
) -> Optional[Dict[str, Any]]:
    if not connector_success_rate_7d and not connector_daily_rollups_7d:
        return None

    avg_success = (
        sum(connector_success_rate_7d.values()) / len(connector_success_rate_7d)
        if connector_success_rate_7d else 0.0
    )
    latest_by_source: Dict[str, Dict[str, Any]] = {}
    for row in connector_daily_rollups_7d:
        source_id = str(row.get("source_id") or "")
        if source_id and source_id not in latest_by_source:
            latest_by_source[source_id] = row

    caution_sources = sum(1 for row in latest_by_source.values() if _connector_rollup_label(row) == "주의")
    reference_kst = (reference_time or datetime.now(_KST)).astimezone(_KST)
    latest_days = [
        datetime.fromisoformat(str(row.get("day"))).date()
        for row in connector_daily_rollups_7d
        if row.get("day")
    ]
    latest_days.extend(
        datetime.fromisoformat(str(row.get("latest_day"))).date()
        for row in connector_metric_trends_7d
        if row.get("latest_day")
    )
    freshest_day = max(latest_days) if latest_days else reference_kst.date()
    freshness_gap = max(0, (reference_kst.date() - freshest_day).days)

    score = 40 + int(avg_success * 40)
    if freshness_gap <= 1:
        score += 15
    elif freshness_gap <= 3:
        score += 8
    else:
        score -= 12
    if connector_metric_trends_7d:
        score += 5
    score -= caution_sources * 10
    score = max(0, min(score, 100))

    if score >= 80:
        label = "높음"
    elif score >= 60:
        label = "보통"
    else:
        label = "주의"

    reason = (
        f"최근 7일 평균 성공률 {avg_success * 100:.0f}%, "
        f"최신 데이터 {freshness_gap}일 전, "
        f"주의 source {caution_sources}개"
    )
    return {"label": label, "score": score, "reason": reason}


def _infer_market_style(
    *,
    market_regime: str,
    focus_keywords: Sequence[str],
    market_points: Sequence[str],
) -> str:
    joined_context = " ".join(list(focus_keywords) + list(market_points))
    if market_regime in {"방어적", "관망"} or _contains_any(joined_context, ("환율", "금리", "불확실", "경계")):
        return "방어형"
    if _contains_any(joined_context, ("AI", "인공지능", "반도체", "HBM", "GPU")):
        return "성장형"
    if _contains_any(joined_context, ("실적", "수주", "계약", "공시")):
        return "실적형"
    return "혼조형"


def _build_learning_card(
    *,
    market_points: Sequence[str],
    focus_keywords: Sequence[str],
    holding_cards: Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    serialized_parts = list(market_points) + list(focus_keywords)
    serialized_parts.extend(card.get("summary", "") for card in holding_cards[:2])
    serialized = " ".join(serialized_parts)

    term_signals = {
        "AI": ("AI", "인공지능", "GPU"),
        "HBM": ("HBM", "고대역폭 메모리"),
        "환율": ("환율", "원/달러", "달러"),
        "금리": ("금리", "국채", "채권"),
        "수급": ("수급", "외국인", "기관", "개인"),
    }
    priority_order = ("AI", "HBM", "환율", "금리", "수급")

    normalized_focus = " ".join(focus_keywords)
    normalized_holdings = " ".join(card.get("summary", "") for card in holding_cards[:2])

    selected_term = "수급"
    for term in priority_order:
        signals = term_signals[term]
        if _contains_any(normalized_focus, signals):
            selected_term = term
            break
        if _contains_any(normalized_holdings, signals):
            selected_term = term
            break
        if _contains_any(serialized, signals):
            selected_term = term
            break

    topic = _LEARNING_TOPIC_LIBRARY[selected_term]
    return {
        "term": selected_term,
        "summary": topic["definition"],
        "why_today": topic["why_today"],
        "how_to_read": topic["how_to_read"],
    }


def _build_domain_signal_sections(
    *,
    connector_metric_trends_7d: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []

    earnings = _find_metric_trend(connector_metric_trends_7d, "opendart", "opendart:earnings")
    financing = _find_metric_trend(connector_metric_trends_7d, "opendart", "opendart:financing")
    ownership = _find_metric_trend(connector_metric_trends_7d, "opendart", "opendart:ownership")
    if any([earnings, financing, ownership]):
        earnings_delta = float((earnings or {}).get("delta_7d") or 0.0)
        financing_delta = float((financing or {}).get("delta_7d") or 0.0)
        ownership_delta = float((ownership or {}).get("delta_7d") or 0.0)

        if financing_delta > earnings_delta and financing_delta > 0:
            summary = "OpenDART 공시는 최근 자금조달 성격이 더 두드러져, 자금 확보 이슈나 희석 우려를 함께 봐야 하는 구간입니다."
        elif earnings_delta > 0:
            summary = "OpenDART 공시는 최근 실적·영업 관련 비중이 늘어, 실적 시즌 기대가 조금 더 강해진 흐름으로 읽힙니다."
        elif ownership_delta > 0:
            summary = "OpenDART 공시는 최근 지분·최대주주 변화가 늘어, 기업별 지배구조 변수와 수급 이슈를 같이 봐야 합니다."
        else:
            summary = "OpenDART 공시는 최근 큰 방향 전환 없이 혼조라, 특정 공시 한두 건보다 누적 흐름을 보는 편이 좋습니다."

        details = []
        rows = []
        for label, row in [
            ("실적/영업", earnings),
            ("자금조달", financing),
            ("지분 변화", ownership),
        ]:
            if not row:
                continue
            details.append(
                (
                    f"{label}: 최근 {row['latest_day']} "
                    f"{_format_metric_value(str(row['metric_key']), row.get('latest_value'))}, "
                    f"1D {_format_metric_delta(str(row['metric_key']), row.get('delta_1d'))}, "
                    f"7D {_format_metric_delta(str(row['metric_key']), row.get('delta_7d'))}"
                )
            )
            rows.append(
                [
                    label,
                    _format_metric_value(str(row["metric_key"]), row.get("latest_value")),
                    _format_metric_delta(str(row["metric_key"]), row.get("delta_1d")),
                    _format_metric_delta(str(row["metric_key"]), row.get("delta_7d")),
                ]
            )

        card = _build_card(
            summary=summary,
            details=details,
            positive_view="실적/영업 공시 비중이 늘면 실적 시즌 기대가 살아 있다는 신호로 해석할 수 있습니다.",
            neutral_view="공시 건수는 시장 방향을 직접 결정한다기보다, 지금 시장이 어떤 종류의 재료에 반응하는지 보여주는 보조 신호입니다.",
            negative_view="자금조달 공시가 빠르게 늘면 희석 우려나 현금 압박 이슈가 부각될 수 있어, 같은 테마라도 종목별 체감이 달라질 수 있습니다.",
            outlook="다음에는 실적 공시 비중이 유지되는지, 아니면 자금조달·지분 이슈로 무게가 이동하는지를 계속 확인하세요.",
        )
        card["title"] = "OpenDART 공시 흐름"
        card["table_headers"] = ["지표", "최근값", "1D 변화", "7D 변화"]
        card["table_rows"] = rows
        sections.append(card)

    fred = _find_metric_trend(connector_metric_trends_7d, "fred", "fred:series_value_x100")
    sec = _find_metric_trend(connector_metric_trends_7d, "sec_edgar", "sec_edgar:registry_count")
    if any([fred, sec]):
        fred_delta_7d = float((fred or {}).get("delta_7d") or 0.0)
        sec_delta_7d = float((sec or {}).get("delta_7d") or 0.0)

        if fred and fred_delta_7d > 0:
            summary = "FRED 금리 지표가 최근 1주 상승해 성장주와 고밸류 주식에는 부담이 조금 더 커진 흐름입니다."
        elif fred and fred_delta_7d < 0:
            summary = "FRED 금리 지표가 최근 1주 완만히 낮아져, 성장주 부담은 다소 완화된 쪽으로 읽을 수 있습니다."
        elif sec and abs(sec_delta_7d) > 0:
            summary = "SEC 샘플 지표에 변화가 보여 미국 커버리지 환경을 함께 점검할 필요가 있습니다."
        else:
            summary = "FRED/SEC 보조 지표는 최근 큰 변화 없이 유지돼, 거시 압력과 커버리지 환경은 비교적 안정적으로 보입니다."

        details = []
        rows = []
        if fred:
            details.append(
                (
                    f"FRED 금리 지표: 최근 {fred['latest_day']} "
                    f"{_format_metric_value('fred:series_value_x100', fred.get('latest_value'))}, "
                    f"1D {_format_metric_delta('fred:series_value_x100', fred.get('delta_1d'))}, "
                    f"7D {_format_metric_delta('fred:series_value_x100', fred.get('delta_7d'))}"
                )
            )
            rows.append(
                [
                    "FRED 금리",
                    _format_metric_value("fred:series_value_x100", fred.get("latest_value")),
                    _format_metric_delta("fred:series_value_x100", fred.get("delta_1d")),
                    _format_metric_delta("fred:series_value_x100", fred.get("delta_7d")),
                ]
            )
        if sec:
            details.append(
                (
                    f"SEC 샘플 지표: 최근 {sec['latest_day']} "
                    f"{_format_metric_value(str(sec['metric_key']), sec.get('latest_value'))}, "
                    f"1D {_format_metric_delta(str(sec['metric_key']), sec.get('delta_1d'))}, "
                    f"7D {_format_metric_delta(str(sec['metric_key']), sec.get('delta_7d'))}"
                )
            )
            rows.append(
                [
                    "SEC 샘플",
                    _format_metric_value(str(sec["metric_key"]), sec.get("latest_value")),
                    _format_metric_delta(str(sec["metric_key"]), sec.get("delta_1d")),
                    _format_metric_delta(str(sec["metric_key"]), sec.get("delta_7d")),
                ]
            )

        card = _build_card(
            summary=summary,
            details=details,
            positive_view="금리 지표가 안정되거나 내려오면 성장주와 AI 테마 해석에는 상대적으로 우호적일 수 있습니다.",
            neutral_view="FRED/SEC 수치는 매수·매도 신호라기보다, 거시 압력과 데이터 커버리지 환경을 같이 보는 보조 축입니다.",
            negative_view="금리 지표가 다시 올라가면 같은 실적 뉴스라도 밸류에이션 부담 때문에 주가 반응이 약할 수 있습니다.",
            outlook="다음 리포트에서는 FRED 금리 흐름이 이어지는지, SEC 샘플 값이 평소 범위를 벗어나는지 같이 보세요.",
        )
        card["title"] = "FRED·SEC 시계열"
        card["table_headers"] = ["지표", "최근값", "1D 변화", "7D 변화"]
        card["table_rows"] = rows
        sections.append(card)

    return sections


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
    if len(headlines) < 2 and current_snapshot.get("focus_keywords"):
        headlines.append(f"오늘 먼저 볼 테마는 {', '.join(current_snapshot['focus_keywords'][:2])}입니다.")
    if len(headlines) < 3 and current_snapshot.get("holding_actions"):
        action_points = [
            f"{holding} {action}"
            for holding, action in list(current_snapshot["holding_actions"].items())[:2]
        ]
        headlines.append(f"보유 종목 포인트는 {', '.join(action_points)}입니다.")

    return headlines[:3]


def _as_kst(reference_time: Optional[datetime]) -> datetime:
    if reference_time is None:
        return datetime.now(_KST)
    if reference_time.tzinfo is None:
        return reference_time.replace(tzinfo=_KST)
    return reference_time.astimezone(_KST)


def _kr_window_for_day(target_day: date, start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> tuple[datetime, datetime]:
    start = datetime.combine(target_day, dt_time(start_hour, start_minute), tzinfo=_KST)
    end = datetime.combine(target_day, dt_time(end_hour, end_minute), tzinfo=_KST)
    return start, end


def _us_window_candidates(reference_kst: datetime) -> List[tuple[str, datetime, datetime]]:
    candidates: List[tuple[str, datetime, datetime]] = []
    current_ny_date = reference_kst.astimezone(_NEW_YORK).date()
    for delta in (-1, 0, 1):
        ny_day = current_ny_date + timedelta(days=delta)
        pre_open_start = datetime.combine(ny_day, dt_time(9, 0), tzinfo=_NEW_YORK).astimezone(_KST)
        pre_open_end = datetime.combine(ny_day, dt_time(9, 30), tzinfo=_NEW_YORK).astimezone(_KST)
        post_close_start = datetime.combine(ny_day, dt_time(16, 0), tzinfo=_NEW_YORK).astimezone(_KST)
        post_close_end = datetime.combine(ny_day, dt_time(16, 30), tzinfo=_NEW_YORK).astimezone(_KST)
        candidates.extend(
            [
                ("미장 개장 전 공통 이슈", pre_open_start, pre_open_end),
                ("미장 마감 직후 공통 이슈", post_close_start, post_close_end),
            ]
        )
    return candidates


def _detect_active_session_window(reference_time: Optional[datetime]) -> Optional[str]:
    reference_kst = _as_kst(reference_time)
    kr_candidates = [
        ("국장 개장 전 공통 이슈", *_kr_window_for_day(reference_kst.date(), 8, 30, 9, 0)),
        ("국장 마감 직후 공통 이슈", *_kr_window_for_day(reference_kst.date(), 15, 30, 16, 0)),
    ]
    candidates = kr_candidates + _us_window_candidates(reference_kst)
    for label, start_at, end_at in candidates:
        if start_at <= reference_kst <= end_at:
            return label
    return None


# Section C: card builders


def _build_card(
    *,
    summary: str,
    details: Sequence[str],
    positive_view: str,
    neutral_view: str,
    negative_view: str,
    outlook: str,
    action: str = "",
    stance: str = "",
    why_it_matters: str = "",
    watch_points: Optional[Sequence[str]] = None,
    related_links: Optional[Sequence[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    cleaned_details = _clean_text_items(details, limit=3)
    return {
        "summary": _truncate_text(summary, 150),
        "details": cleaned_details,
        "why_it_matters": (
            _truncate_text(why_it_matters, 170)
            if why_it_matters and not _is_low_signal_text(why_it_matters)
            else ""
        ),
        "watch_points": _clean_text_items(watch_points or [], limit=3),
        "positive_view": _truncate_text(positive_view, 140),
        "neutral_view": _truncate_text(neutral_view, 140),
        "negative_view": _truncate_text(negative_view, 140),
        "outlook": _truncate_text(outlook, 150),
        "action": _truncate_text(action, 140) if action else "",
        "stance": stance,
        "related_links": [
            {
                "label": _truncate_text(str(link.get("label") or ""), 90),
                "url": str(link.get("url") or "").strip(),
            }
            for link in list(related_links or [])
            if str(link.get("label") or "").strip() and str(link.get("url") or "").strip()
        ][:2],
    }


def _build_quick_take_card(
    market_points: Sequence[str],
    market_indices: Sequence[MarketIndex],
    market_news: Sequence[NewsArticle],
    focus_keywords: Sequence[str],
    sentiment_score: int,
    market_regime: str,
) -> Dict[str, Any]:
    support, risk = _pick_primary_market_forces(market_points, focus_keywords)
    signal_news = _signal_news_items(market_news, limit=2)
    joined_context = " ".join(
        list(market_points)
        + list(focus_keywords)
        + [f"{item.name} {item.investor_summary or ''}" for item in list(market_indices)[:2]]
        + [item.title for item in signal_news]
    )
    why_it_matters = _describe_why_it_matters("시장", joined_context)
    summary = (
        f"지금 시장은 {support}가 버팀목이지만 {risk}도 커서, 급하게 방향을 정하기보다 {market_regime} 시각으로 보는 편이 안전합니다."
    )
    details = [f"버팀목: {support}"]
    if market_indices:
        details.append(
            _truncate_text(
                f"{market_indices[0].name} {market_indices[0].value}, {market_indices[0].investor_summary or '수급 확인 필요'}",
                120,
            )
        )
    watch_points: List[str] = []
    if market_indices:
        watch_points.append("외국인·기관 수급")
    if "환율" in risk:
        watch_points.append("원/달러 환율")
    elif "지정학" in risk:
        watch_points.append("국제 뉴스 속보")
    elif "금리" in risk:
        watch_points.append("미국 금리·고용 지표")
    if focus_keywords:
        watch_points.append(f"{focus_keywords[0]} 후속 뉴스")
    return _build_card(
        summary=summary,
        details=details[:3],
        positive_view=_truncate_text(
            f"{support}와 관련된 뉴스, 수급, 거래대금이 함께 살아나면 심리 점수 {sentiment_score:+d}보다 더 강한 반등 해석이 가능해집니다.",
            120,
        ),
        neutral_view=_truncate_text(
            f"{support}와 {_attach_particle(risk, '이', '가')} 같이 존재하는 구간이라, 지금은 낙관이나 비관보다 확인 매매 관점이 더 자연스럽습니다.",
            120,
        ),
        negative_view=_truncate_text(
            f"{_attach_particle(risk, '이', '가')} 다시 커지면 오늘의 기대감은 빠르게 식을 수 있어, 뉴스보다 환율·수급 같은 숫자를 먼저 보는 편이 좋습니다.",
            120,
        ),
        outlook=_truncate_text(
            f"다음 한두 거래일은 {support} 지속 여부와 {risk} 완화 여부를 함께 확인해야 합니다. 특히 {', '.join(focus_keywords[:2]) or '대표 지수'} 후속 뉴스가 핵심입니다.",
            120,
        ),
        why_it_matters=why_it_matters,
        watch_points=watch_points or _split_watch_points(_describe_monitor_points(joined_context)),
        related_links=_build_related_links(signal_news, limit=2),
    )


def _build_session_issue_card(
    *,
    reference_time: Optional[datetime],
    market_news: Sequence[NewsArticle],
    community_posts: Sequence[CommunityPost],
    datalab_trends: Sequence[SearchTrend],
) -> Optional[Dict[str, Any]]:
    label = _detect_active_session_window(reference_time)
    if not label:
        return None

    signal_news = _signal_news_items(market_news, limit=3)
    news_titles = [item.title for item in signal_news]
    top_news = ", ".join(_truncate_text(title, 50) for title in news_titles[:2]) or "관련 헤드라인 부족"
    joined_context = " ".join(news_titles + [post.title for post in list(community_posts)[:2]])
    summary = f"{label}에는 {top_news} 이슈가 시장 대화의 중심이며, 장 시작 전후 해석 차이가 크게 벌어질 수 있습니다."
    details: List[str] = []
    if signal_news:
        details.append(f"무슨 일이 있었나: {', '.join(_truncate_text(item.title, 55) for item in signal_news[:2])}")
    if datalab_trends:
        details.append(
            "왜 주목하나: "
            + ", ".join(_truncate_text(f"{item.keyword} {item.traffic}", 40) for item in list(datalab_trends)[:2])
        )
    if community_posts:
        details.append(f"지금 논쟁거리: {_truncate_text(community_posts[0].title, 90)}")

    score = _score_texts(news_titles + [post.title for post in list(community_posts)[:2]])
    positive_view, neutral_view, negative_view, outlook = _build_context_views(label, joined_context)
    return {
        "title": label,
        **_build_card(
            summary=summary,
            details=details[:3],
            positive_view=positive_view,
            neutral_view=neutral_view,
            negative_view=negative_view,
            outlook=_truncate_text(
                f"현재 공통 이슈의 전체 톤은 {_tone_label(score)}입니다. {outlook}",
                120,
            ),
            why_it_matters=_describe_why_it_matters(label, joined_context),
            watch_points=_split_watch_points(_describe_monitor_points(joined_context)),
            related_links=_build_related_links(signal_news, limit=2),
        ),
    }


def _build_recent_window_card(
    *,
    market_news: Sequence[NewsArticle],
    datalab_trends: Sequence[SearchTrend],
) -> Dict[str, Any]:
    signal_news = _signal_news_items(market_news, limit=2)
    recent_titles = [_truncate_text(article.title, 70) for article in signal_news]
    trend_titles = [
        _truncate_text(f"{trend.keyword} 관심도 {trend.traffic or 'N/A'}", 70)
        for trend in list(datalab_trends)[:2]
    ]
    joined_context = " ".join(recent_titles + trend_titles)
    summary = (
        f"가장 최근 화제는 {recent_titles[0] if recent_titles else '새 헤드라인 부족'}이며, "
        "지금은 뉴스 내용 자체보다 그 뉴스가 얼마나 빠르게 확산되는지가 더 중요합니다."
    )
    details = (recent_titles + trend_titles)[:2]
    score = _score_texts(recent_titles)
    positive_view, neutral_view, negative_view, outlook = _build_context_views("최근 동향", joined_context)
    return _build_card(
        summary=summary,
        details=details or ["최신 뉴스 데이터가 적어 다음 실행에서 보강됩니다."],
        positive_view=positive_view,
        neutral_view=neutral_view,
        negative_view=negative_view,
        outlook=_truncate_text(f"현재 1H 톤은 {_tone_label(score)}입니다. {outlook}", 120),
        why_it_matters=_describe_why_it_matters("최근 동향", joined_context),
        watch_points=_split_watch_points(_describe_monitor_points(joined_context)),
        related_links=_build_related_links(signal_news, limit=2),
    )


def _build_daily_window_card(
    *,
    market_indices: Sequence[MarketIndex],
    market_news: Sequence[NewsArticle],
    market_points: Sequence[str],
    sentiment_score: int,
) -> Dict[str, Any]:
    first_index = market_indices[0] if market_indices else None
    signal_news = _signal_news_items(market_news, limit=2)
    joined_context = " ".join(
        list(market_points)
        + [f"{item.name} {item.value} {item.investor_summary}" for item in list(market_indices)[:3]]
        + [item.title for item in signal_news]
    )
    summary = (
        f"오늘 장은 {first_index.name if first_index else '주요 지수'}보다도 수급과 뉴스 해석이 더 중요했던 날로, "
        f"전반 톤은 {('조심스러운 반등' if sentiment_score > 10 else '혼조' if sentiment_score > -10 else '방어적')}에 가깝습니다."
    )
    index_details = [
        _truncate_text(
            f"{item.name} {item.value} | {item.investor_summary or '수급 데이터 확인 필요'}",
            120,
        )
        for item in list(market_indices)[:2]
    ]
    details = index_details or list(market_points[:2])
    positive_view, neutral_view, negative_view, outlook = _build_context_views("오늘 장", joined_context)
    return _build_card(
        summary=summary,
        details=details[:3],
        positive_view=positive_view,
        neutral_view=neutral_view,
        negative_view=negative_view,
        outlook=outlook,
        why_it_matters=_describe_why_it_matters("오늘 장", joined_context),
        watch_points=_split_watch_points(_describe_monitor_points(joined_context)),
        related_links=_build_related_links(signal_news, limit=2),
    )


def _build_weekly_window_card(
    *,
    weekly_snapshots: Sequence[Dict[str, Any]],
    weekly_focus: Sequence[str],
    connector_success_rate_7d: Dict[str, float],
) -> Dict[str, Any]:
    health_note, is_low_confidence = _connector_health_note(connector_success_rate_7d)
    if weekly_focus:
        summary = f"지난 일주일은 {', '.join(weekly_focus[:2])}가 반복해서 등장해 단기 관심 테마가 비교적 선명했습니다."
        details = [
            f"반복 테마: {', '.join(weekly_focus[:3])}",
            f"최근 리포트 관찰치: {len(weekly_snapshots)}회",
            health_note,
        ]
    else:
        summary = "최근 일주일은 아직 반복해서 확인된 주도 테마가 뚜렷하지 않아, 단기 유행과 실제 추세를 구분해서 봐야 합니다."
        details = [f"최근 리포트 관찰치: {len(weekly_snapshots)}회", health_note]

    return _build_card(
        summary=summary,
        details=details,
        positive_view="같은 테마가 여러 번 반복되면 단순 뉴스보다 실제 수급 흐름으로 이어질 가능성이 높아집니다.",
        neutral_view="1주 데이터는 짧아, 테마가 보여도 아직 추세 전환이라고 단정하긴 이릅니다.",
        negative_view="누적 데이터가 얇거나 소스 안정성이 낮으면, 최근 유행이 과장됐을 가능성도 열어둬야 합니다." if is_low_confidence else "이번 주 화제가 이어져도 실적이나 수주로 연결되지 않으면 금방 식을 수 있습니다.",
        outlook="다음 주에는 같은 테마가 다시 나오고, 실제 종목 수익률과 연결되는지 확인해야 합니다.",
        why_it_matters="1주 구간은 지금 시장이 어디에 반복 반응하는지 보여주는 짧은 체감 지표라, 단기 주도 테마를 읽는 데 도움이 됩니다.",
        watch_points=["같은 테마 재등장", "실제 종목 수익률 연결", "소스 안정성 유지"],
    )


def _build_monthly_window_card(
    *,
    monthly_snapshots: Sequence[Dict[str, Any]],
    monthly_focus: Sequence[str],
    connector_success_rate_30d: Dict[str, float],
    avg_feedback_score_30d: float,
    avg_accuracy_30d: float,
) -> Dict[str, Any]:
    health_note, is_low_confidence = _connector_health_note(connector_success_rate_30d)
    if monthly_focus:
        summary = f"최근 한 달은 {', '.join(monthly_focus[:2])}가 장기 감시축으로 남아, 완전히 새로운 장세로 바뀌었다고 보긴 어렵습니다."
    else:
        summary = "최근 한 달 데이터는 아직 적어 장기 주도축을 강하게 단정하기보다 누적 신호를 더 모아야 합니다."

    details = [health_note, f"최근 30일 관찰치: {len(monthly_snapshots)}회"]
    if avg_accuracy_30d > 0:
        details.append(f"예측 적중률 평균: {avg_accuracy_30d * 100:.0f}%")
    if avg_feedback_score_30d > 0:
        details.append(f"사용자 만족도 평균: {avg_feedback_score_30d:.1f}/5")

    return _build_card(
        summary=summary,
        details=details,
        positive_view="장기 축이 유지되면 단기 흔들림이 와도 큰 흐름은 쉽게 꺾이지 않을 수 있습니다.",
        neutral_view="한 달 데이터도 아직 충분하지 않으면, 장기 판단은 비중 조정보다 관찰 비중을 높이는 편이 낫습니다.",
        negative_view="누적 데이터가 적거나 신뢰도가 낮으면 장기 테마 해석이 실제 시장보다 느릴 수 있습니다." if is_low_confidence else "장기 테마가 살아 있어도 밸류에이션 부담이 커지면 체감 수익은 약할 수 있습니다.",
        outlook="장기 계획은 한 달 누적 테마가 실제 실적과 얼마나 연결되는지 확인하면서 천천히 조정하는 편이 좋습니다.",
        why_it_matters="1개월 구간은 하루 이슈보다 반복되는 축을 보는 단계라, 비중 조정보다 추세 지속 여부를 판단하는 데 더 적합합니다.",
        watch_points=["한 달 반복 테마 유지", "실적 확인", "데이터 신뢰도 개선"],
    )


def _merge_theme_sections(
    theme_sections: Sequence[Dict[str, str]],
    theme_news_map: Dict[str, Sequence[NewsArticle]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    for section in theme_sections:
        original_keyword = section.get("keyword", "").strip()
        if not original_keyword:
            continue
        canonical_keyword = _normalize_theme_keyword(original_keyword)
        if canonical_keyword not in merged:
            order.append(canonical_keyword)
            merged[canonical_keyword] = {
                "keyword": canonical_keyword,
                "source_keywords": [],
                "points": [],
                "news_items": [],
            }

        bucket = merged[canonical_keyword]
        bucket["source_keywords"].append(original_keyword)
        bucket["points"].extend(extract_key_points(section.get("briefing_md", ""), max_items=4))
        bucket["news_items"].extend(theme_news_map.get(original_keyword, []))

    merged_sections: List[Dict[str, Any]] = []
    for keyword in order:
        bucket = merged[keyword]
        merged_sections.append(
            {
                "keyword": keyword,
                "source_keywords": _dedupe_list(bucket["source_keywords"]),
                "points": _dedupe_list(bucket["points"]),
                "news_items": _dedupe_news_items(bucket["news_items"]),
            }
        )
    return merged_sections


def _theme_outlook(keyword: str, joined_context: str) -> str:
    if "HBM" in joined_context or "메모리" in joined_context:
        return "다음 체크포인트는 HBM 공급 확대와 메모리 가격 반응입니다."
    if "GPU" in joined_context or "AI" in joined_context or "인공지능" in keyword:
        return "다음 체크포인트는 AI 투자 사이클이 실제 수주와 실적으로 이어지는지입니다."
    if "반도체" in joined_context:
        return "다음 체크포인트는 고객사 발주와 업황 회복 속도입니다."
    return "다음 체크포인트는 뉴스가 실제 실적과 자금 유입으로 이어지는지입니다."


def _build_theme_cards(
    theme_sections: Sequence[Dict[str, str]],
    theme_news_map: Dict[str, Sequence[NewsArticle]],
) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for merged in _merge_theme_sections(theme_sections, theme_news_map)[:2]:
        keyword = merged["keyword"]
        news_items = _signal_news_items(merged["news_items"], limit=2)
        point_items = _clean_text_items(merged["points"], limit=3)
        joined_context = " ".join([keyword] + point_items + [news.title for news in news_items])
        news_titles = [item.title for item in news_items[:2]]
        score = _score_texts(news_titles + point_items)

        if news_titles:
            summary = f"{keyword}는 지금 '{_truncate_text(news_titles[0], 55)}' 같은 이슈 때문에 다시 주목받고 있습니다."
        elif point_items:
            summary = f"{keyword}는 최근 리포트에서 반복해서 보인 테마라, 완전히 식었다고 보긴 어렵습니다."
        else:
            summary = f"{keyword}는 최근 관찰 대상이지만 직접 연결된 재료는 아직 적습니다."

        details = []
        for news in news_items[:2]:
            details.append(f"무슨 일이 있었나: {_truncate_text(news.title, 90)}")
            if news.summary:
                details.append(f"핵심 설명: {_truncate_text(news.summary, 90)}")
                break
        if not details:
            details = [f"최근 포인트: {point}" for point in point_items[:2]]

        positive_view, neutral_view, negative_view, outlook = _build_context_views(keyword, joined_context)
        cards.append(
            {
                "keyword": keyword,
                **_build_card(
                    summary=summary,
                    details=details[:3],
                    positive_view=positive_view,
                    neutral_view=neutral_view,
                    negative_view=negative_view,
                    outlook=_truncate_text(
                        f"{_theme_outlook(keyword, joined_context)} 현재 톤은 {_tone_label(score)}입니다. {outlook}",
                        120,
                    ),
                    why_it_matters=_describe_why_it_matters(keyword, joined_context),
                    watch_points=_split_watch_points(_describe_monitor_points(joined_context)),
                    related_links=_build_related_links(news_items, limit=2),
                ),
            }
        )
    return cards


def _build_holding_cards(
    *,
    holding_insights: Sequence[Dict[str, str]],
    holding_news_map: Dict[str, Sequence[NewsArticle]],
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    cards: List[Dict[str, Any]] = []
    holding_actions: Dict[str, str] = {}

    for insight in holding_insights:
        holding = insight.get("holding", "").strip()
        if not holding:
            continue

        stance = insight.get("stance", "관찰").strip() or "관찰"
        holding_actions[holding] = stance
        raw_summary = insight.get("summary", "").strip()
        news_items = _signal_news_items(holding_news_map.get(holding, []), limit=2)
        summary = raw_summary or f"{holding}는 직접 연계 뉴스가 적어 추가 확인이 필요합니다."
        if _summary_needs_rebuild(summary):
            if news_items:
                summary = f"{holding}는 '{_truncate_text(news_items[0].title, 45)}' 이슈가 핵심이며, 지금은 {stance} 관점이 적절합니다."
            else:
                summary = f"{holding}는 직접 연계 재료가 얇아 당장은 {stance} 관점에서 확인이 필요합니다."
        joined_context = " ".join([holding, summary, insight.get("action", "")] + [news.title for news in news_items] + [news.summary or "" for news in news_items])
        details = []
        for news in news_items:
            details.append(f"무슨 일이 있었나: {_truncate_text(news.title, 90)}")
            if news.summary:
                details.append(f"핵심 설명: {_truncate_text(news.summary, 90)}")
                break
        if not details:
            details.append("직접 연계 뉴스가 적어 시장 전체 흐름과 함께 보는 편이 좋습니다.")

        positive_view, neutral_view, negative_view, outlook = _build_context_views(holding, joined_context)
        outlook = insight.get("action", "").strip() or "다음 뉴스와 수급 변화를 확인하세요."
        if stance == "유지":
            outlook = f"{outlook} 지금은 기존 포지션을 서두르지 않고 유지하는 쪽이 더 자연스럽습니다."
        elif stance == "경계":
            outlook = f"{outlook} 지금은 낙관보다 손실 관리 쪽을 먼저 생각하는 편이 좋습니다."

        cards.append(
            {
                "holding": holding,
                **_build_card(
                    summary=summary,
                    details=details[:3],
                    positive_view=positive_view,
                    neutral_view=neutral_view,
                    negative_view=negative_view,
                    outlook=_truncate_text(
                        f"현재 톤은 {_tone_label(_score_texts([joined_context]))}입니다. {outlook} {_describe_monitor_points(joined_context)}를 계속 보세요.",
                        120,
                    ),
                    action=insight.get("action", "").strip(),
                    stance=stance,
                    why_it_matters=_describe_why_it_matters(holding, joined_context),
                    watch_points=_HOLDING_WATCHPOINTS.get(
                        holding,
                        _split_watch_points(_describe_monitor_points(joined_context)),
                    ),
                    related_links=_build_related_links(news_items, limit=2),
                ),
            }
        )
    return cards, holding_actions


def _build_long_term_card(
    *,
    monthly_focus: Sequence[str],
    avg_accuracy_30d: float,
    avg_feedback_score_30d: float,
    connector_success_rate_30d: Dict[str, float],
) -> Dict[str, Any]:
    health_note, is_low_confidence = _connector_health_note(connector_success_rate_30d)
    if monthly_focus:
        summary = f"장기 추적축은 아직 {', '.join(monthly_focus[:2])} 쪽에 무게가 있어, 완전히 다른 장세로 바뀌었다고 보긴 이릅니다."
    else:
        summary = "장기 누적 데이터가 아직 적어, 한 달 단위 방향은 섣불리 단정하지 않는 편이 안전합니다."

    details = [health_note]
    if avg_accuracy_30d > 0:
        details.append(f"최근 30일 예측 적중률 평균은 {avg_accuracy_30d * 100:.0f}%입니다.")
    else:
        details.append("예측 적중률 데이터는 아직 충분히 쌓이지 않았습니다.")
    if avg_feedback_score_30d > 0:
        details.append(f"최근 30일 사용자 만족도 평균은 {avg_feedback_score_30d:.1f}/5입니다.")

    return _build_card(
        summary=summary,
        details=details,
        positive_view="장기 테마가 유지되면 단기 흔들림을 지나 다시 같은 주도주로 자금이 모일 수 있습니다.",
        neutral_view="장기 계획은 한 번에 바꾸기보다, 같은 신호가 반복되는지 확인하면서 조금씩 조정하는 편이 좋습니다.",
        negative_view="누적 데이터 신뢰도가 낮으면 장기 해석이 실제 시장보다 늦을 수 있습니다." if is_low_confidence else "장기 테마가 살아 있어도 비싸진 종목은 기대만큼 오르지 않을 수 있습니다.",
        outlook="장기 비중 조정은 다음 달에도 같은 테마가 남는지, 그리고 실제 실적이 따라오는지를 같이 보며 진행하세요.",
    )


def _build_decision_tiles(
    *,
    market_regime: str,
    focus_keywords: Sequence[str],
    holding_actions: Dict[str, str],
    quick_take: Dict[str, Any],
    reliability_badge: Optional[Dict[str, Any]],
) -> List[Dict[str, str]]:
    tiles = [
        {
            "label": "시장 톤",
            "value": market_regime,
            "detail": (quick_take.get("details") or ["수급과 환율을 같이 봅니다."])[0],
        },
        {
            "label": "먼저 볼 테마",
            "value": ", ".join(focus_keywords[:2]) or "핵심 테마 관찰",
            "detail": "반복 등장한 테마가 실제 수급과 연결되는지 확인합니다.",
        },
        {
            "label": "보유 종목",
            "value": ", ".join(
                f"{holding} {action}"
                for holding, action in list(holding_actions.items())[:2]
            )
            or "보유 종목 관찰",
            "detail": "종목별 공통 해석보다 각 종목 체크포인트를 따로 봅니다.",
        },
        {
            "label": "지금 체크포인트",
            "value": ", ".join(quick_take.get("watch_points", [])[:2]) or "수급, 환율",
            "detail": (
                f"현재 리포트 신뢰도는 {reliability_badge.get('label', '보통')}입니다."
                if reliability_badge
                else "다음 실행에서 데이터 신뢰도를 함께 확인합니다."
            ),
        },
    ]
    return tiles


def _build_market_scoreboard(
    *,
    market_indices: Sequence[MarketIndex],
    market_regime: str,
    sentiment_score: int,
    focus_keywords: Sequence[str],
    datalab_trends: Sequence[SearchTrend],
) -> Dict[str, Any]:
    rows: List[List[str]] = []
    for item in list(market_indices)[:2]:
        rows.append(
            [
                item.name,
                item.value or "수치 없음",
                _truncate_text(item.investor_summary or "수급 방향 확인 필요", 72),
            ]
        )

    rows.append(
        [
            "시장 심리",
            f"{sentiment_score:+d} / {market_regime}",
            "숫자와 장세 톤을 같이 보며 과도한 낙관·비관을 피합니다.",
        ]
    )

    if focus_keywords:
        rows.append(
            [
                "우선 테마",
                ", ".join(focus_keywords[:2]),
                "반복 등장 테마가 후속 뉴스와 수급으로 이어지는지 확인합니다.",
            ]
        )

    if datalab_trends:
        top_trend = datalab_trends[0]
        rows.append(
            [
                "검색 관심",
                _truncate_text(f"{top_trend.keyword} {top_trend.traffic or 'N/A'}", 40),
                "실제 매수세로 이어지는지 함께 보지 않으면 과열 해석이 될 수 있습니다.",
            ]
        )

    return {
        "headers": ["항목", "현재 값", "읽는 법"],
        "rows": rows[:5],
    }


def _build_insight_lenses(
    *,
    market_regime: str,
    market_points: Sequence[str],
    quick_take: Dict[str, Any],
    daily_window: Dict[str, Any],
    recent_window: Dict[str, Any],
    session_issue_section: Optional[Dict[str, Any]],
    theme_cards: Sequence[Dict[str, Any]],
    holding_cards: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    first_theme = theme_cards[0] if theme_cards else {}
    first_holding = holding_cards[0] if holding_cards else {}
    event_source = session_issue_section or recent_window
    market_style = _infer_market_style(
        market_regime=market_regime,
        focus_keywords=[card.get("keyword", "") for card in theme_cards[:2]],
        market_points=market_points,
    )

    flow_details = list(daily_window.get("details", [])[:2])
    if first_theme.get("keyword"):
        flow_details.append(f"우선 테마: {first_theme['keyword']}")
    if first_holding.get("holding"):
        flow_details.append(
            f"대표 종목: {first_holding['holding']} {first_holding.get('stance', '관찰')}"
        )

    return [
        {
            "title": "경제 온도",
            "summary": (
                f"지금 경제 환경은 {quick_take.get('details', ['수급 개선 기대'])[0].replace('버팀목: ', '')}와 "
                f"{_describe_risk_factor(' '.join(market_points))}가 함께 있는 {market_style} 구간으로 보는 편이 자연스럽습니다."
            ),
            "details": _clean_text_items(
                [
                    f"현재 시장 스타일: {market_style}",
                    f"시장 톤: {market_regime}",
                    *(quick_take.get("details", [])[:2]),
                ],
                limit=3,
            ),
            "why_it_matters": "경제 환경은 지금 어떤 종목군이 유리한지와, 같은 뉴스에 시장이 얼마나 민감하게 반응할지를 정하는 배경입니다.",
            "watch_points": quick_take.get("watch_points", [])[:2],
            "positive_view": quick_take.get("positive_view", ""),
            "neutral_view": quick_take.get("neutral_view", ""),
            "negative_view": quick_take.get("negative_view", ""),
            "related_links": quick_take.get("related_links", [])[:2],
        },
        {
            "title": "자금 흐름",
            "summary": (
                f"오늘은 누가 사고 있는지와 {first_theme.get('keyword', '핵심 테마')}가 "
                "실제 종목 수익률로 번지는지를 같이 보는 편이 좋습니다."
            ),
            "details": _clean_text_items(flow_details, limit=3),
            "why_it_matters": daily_window.get("why_it_matters", ""),
            "watch_points": daily_window.get("watch_points", [])[:2],
            "positive_view": daily_window.get("positive_view", ""),
            "neutral_view": daily_window.get("neutral_view", ""),
            "negative_view": daily_window.get("negative_view", ""),
            "related_links": daily_window.get("related_links", [])[:2],
        },
        {
            "title": "시장 화제",
            "summary": event_source.get("summary", ""),
            "details": event_source.get("details", [])[:2],
            "why_it_matters": event_source.get("why_it_matters", ""),
            "watch_points": event_source.get("watch_points", [])[:2],
            "positive_view": event_source.get("positive_view", ""),
            "neutral_view": event_source.get("neutral_view", ""),
            "negative_view": event_source.get("negative_view", ""),
            "related_links": event_source.get("related_links", [])[:2],
        },
    ]


def _build_glossary(report_payload: Dict[str, Any]) -> List[Dict[str, str]]:
    serialized = json.dumps(report_payload, ensure_ascii=False).lower()
    items: List[Dict[str, str]] = []
    for term, definition in _GLOSSARY.items():
        if term.lower() in serialized:
            items.append({"term": term, "definition": definition})
    return items


# Section D: public payload builder


def build_report_payload(
    *,
    user_name: str,
    market_summary_md: str,
    market_indices: Sequence[MarketIndex],
    market_news: Sequence[NewsArticle],
    datalab_trends: Sequence[SearchTrend],
    theme_sections: Sequence[Dict[str, str]],
    theme_news_map: Dict[str, Sequence[NewsArticle]],
    sentiment_score: int,
    sentiment_label: str,
    holding_insights: Sequence[Dict[str, str]],
    holding_news_map: Dict[str, Sequence[NewsArticle]],
    community_posts: Sequence[CommunityPost],
    recent_report_rows: Sequence[Dict[str, Any]],
    weekly_report_rows: Sequence[Dict[str, Any]],
    monthly_report_rows: Sequence[Dict[str, Any]],
    connector_success_rate_7d: Dict[str, float],
    connector_success_rate_30d: Dict[str, float],
    avg_feedback_score_30d: float,
    avg_accuracy_30d: float,
    connector_daily_rollups_7d: Optional[Sequence[Dict[str, Any]]] = None,
    recent_connector_failures_7d: Optional[Sequence[Dict[str, Any]]] = None,
    connector_metric_trends_7d: Optional[Sequence[Dict[str, Any]]] = None,
    reference_time: Optional[datetime] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """리포트 렌더링 payload와 저장용 스냅샷을 생성합니다."""
    market_points = extract_key_points(market_summary_md, max_items=4)
    previous_snapshots = _deserialize_snapshot_rows(recent_report_rows)
    weekly_snapshots = _deserialize_snapshot_rows(weekly_report_rows)
    monthly_snapshots = _deserialize_snapshot_rows(monthly_report_rows)

    theme_cards = _build_theme_cards(theme_sections, theme_news_map)
    focus_keywords = [card["keyword"] for card in theme_cards]
    holding_cards, holding_actions = _build_holding_cards(
        holding_insights=holding_insights,
        holding_news_map=holding_news_map,
    )

    market_regime = _build_market_regime(sentiment_score, sentiment_label, market_points)
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

    weekly_focus = _recurring_focus_keywords(weekly_snapshots)
    monthly_focus = _recurring_focus_keywords(monthly_snapshots)
    reliability_badge = _build_reliability_badge(
        connector_success_rate_7d=connector_success_rate_7d,
        connector_daily_rollups_7d=connector_daily_rollups_7d or [],
        connector_metric_trends_7d=connector_metric_trends_7d or [],
        reference_time=reference_time,
    )
    quick_take = _build_quick_take_card(
        market_points=market_points,
        market_indices=market_indices,
        market_news=market_news,
        focus_keywords=focus_keywords,
        sentiment_score=sentiment_score,
        market_regime=market_regime,
    )
    recent_window = _build_recent_window_card(
        market_news=market_news,
        datalab_trends=datalab_trends,
    )
    daily_window = _build_daily_window_card(
        market_indices=market_indices,
        market_news=market_news,
        market_points=market_points,
        sentiment_score=sentiment_score,
    )
    session_issue_section = _build_session_issue_card(
        reference_time=reference_time,
        market_news=market_news,
        community_posts=community_posts,
        datalab_trends=datalab_trends,
    )

    payload: Dict[str, Any] = {
        "title": "🌤️ 오늘의 주식 인사이트 리포트",
        "subtitle": "최신 동향과 앞으로의 판단을 쉽게 풀어쓴 5~10분 리포트",
        "reliability_badge": reliability_badge,
        "decision_tiles": _build_decision_tiles(
            market_regime=market_regime,
            focus_keywords=focus_keywords,
            holding_actions=holding_actions,
            quick_take=quick_take,
            reliability_badge=reliability_badge,
        ),
        "market_scoreboard": _build_market_scoreboard(
            market_indices=market_indices,
            market_regime=market_regime,
            sentiment_score=sentiment_score,
            focus_keywords=focus_keywords,
            datalab_trends=datalab_trends,
        ),
        "headline_changes": headline_changes,
        "quick_take": quick_take,
        "insight_lenses": _build_insight_lenses(
            market_regime=market_regime,
            market_points=market_points,
            quick_take=quick_take,
            daily_window=daily_window,
            recent_window=recent_window,
            session_issue_section=session_issue_section,
            theme_cards=theme_cards,
            holding_cards=holding_cards,
        ),
        "session_issue_section": session_issue_section,
        "time_windows": [
            {
                "label": "1H",
                "title": "최근 동향",
                **recent_window,
            },
            {
                "label": "1D",
                "title": "오늘 장 판단",
                **daily_window,
            },
            {
                "label": "1W",
                "title": "최근 1주 반복 신호",
                **_build_weekly_window_card(
                    weekly_snapshots=weekly_snapshots,
                    weekly_focus=weekly_focus,
                    connector_success_rate_7d=connector_success_rate_7d,
                ),
            },
            {
                "label": "1M",
                "title": "최근 1개월 장기 판단",
                **_build_monthly_window_card(
                    monthly_snapshots=monthly_snapshots,
                    monthly_focus=monthly_focus,
                    connector_success_rate_30d=connector_success_rate_30d,
                    avg_feedback_score_30d=avg_feedback_score_30d,
                    avg_accuracy_30d=avg_accuracy_30d,
                ),
            },
        ],
        "data_quality_section": _build_data_quality_card(
            connector_daily_rollups_7d=connector_daily_rollups_7d or [],
            recent_connector_failures_7d=recent_connector_failures_7d or [],
        ),
        "domain_signal_sections": _build_domain_signal_sections(
            connector_metric_trends_7d=connector_metric_trends_7d or [],
        ),
        "theme_sections": theme_cards,
        "holding_sections": holding_cards,
        "long_term_section": _build_long_term_card(
            monthly_focus=monthly_focus,
            avg_accuracy_30d=avg_accuracy_30d,
            avg_feedback_score_30d=avg_feedback_score_30d,
            connector_success_rate_30d=connector_success_rate_30d,
        ),
        "learning_card": _build_learning_card(
            market_points=market_points,
            focus_keywords=focus_keywords,
            holding_cards=holding_cards,
        ),
        "footer_note": "본 리포트는 자동화된 AI 및 스크래핑 시스템에 의해 수집/편집되었습니다.",
    }
    payload["glossary"] = _build_glossary(payload)
    return payload, current_snapshot
