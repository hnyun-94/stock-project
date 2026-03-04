"""
시장 감정 지표(Sentiment Score) 분석 모듈.

커뮤니티 게시글 제목과 뉴스 헤드라인에서 긍정/부정 키워드를 분석하여
시장 심리를 수치화합니다. 외부 NLP 라이브러리 없이 키워드 사전 기반으로
가벼운 감정 분석을 수행합니다.

결과물:
- 감정 점수: -100 ~ +100 (매우 부정 ~ 매우 긍정)
- 감정 라벨: 🔴 공포 / 🟠 부정 / 🟡 중립 / 🟢 긍정 / 🔵 탐욕
- 마크다운 포맷 리포트 섹션

사용법:
    from src.utils.sentiment import analyze_sentiment, format_sentiment_section

    score, label = analyze_sentiment(news_list, community_posts)
    section_md = format_sentiment_section(score, label)

[Task 6.19, REQ-F04]
"""

from typing import List, Tuple
from src.models import NewsArticle, CommunityPost
from src.utils.logger import global_logger


# 감정 키워드 사전 (한국어 주식 커뮤니티 기반)
# 점수: 긍정 +1, 부정 -1, 강한 감정 ±2
_POSITIVE_KEYWORDS = {
    # 강한 긍정 (+2)
    "급등": 2, "폭등": 2, "역대 최고": 2, "사상 최고": 2,
    "대박": 2, "로켓": 2, "불장": 2,
    # 일반 긍정 (+1)
    "상승": 1, "반등": 1, "상한가": 1, "매수": 1,
    "호재": 1, "회복": 1, "돌파": 1, "신고가": 1,
    "강세": 1, "순매수": 1, "실적 개선": 1, "성장": 1,
    "기대": 1, "좋다": 1, "올랐": 1, "최고치": 1,
}

_NEGATIVE_KEYWORDS = {
    # 강한 부정 (-2)
    "폭락": -2, "급락": -2, "공포": -2, "패닉": -2,
    "서킷브레이커": -2, "블랙먼데이": -2, "대폭락": -2,
    # 일반 부정 (-1)
    "하락": -1, "하한가": -1, "매도": -1, "손절": -1,
    "악재": -1, "하방": -1, "약세": -1, "순매도": -1,
    "실적 부진": -1, "우려": -1, "위기": -1, "떨어졌": -1,
    "빠졌": -1, "불안": -1, "침체": -1, "적자": -1,
}


def _score_text(text: str) -> int:
    """텍스트에서 감정 키워드를 탐지하고 점수를 합산합니다.

    Args:
        text: 분석 대상 텍스트 (뉴스 제목, 게시글 제목 등)

    Returns:
        감정 점수 합산값
    """
    score = 0
    for keyword, value in _POSITIVE_KEYWORDS.items():
        if keyword in text:
            score += value
    for keyword, value in _NEGATIVE_KEYWORDS.items():
        if keyword in text:
            score += value
    return score


def analyze_sentiment(
    news_list: List[NewsArticle],
    community_posts: List[CommunityPost]
) -> Tuple[int, str]:
    """뉴스와 커뮤니티 데이터에서 시장 감정 점수를 계산합니다.

    점수 범위를 -100 ~ +100으로 정규화합니다.
    분석 대상이 없으면 중립(0)을 반환합니다.

    Args:
        news_list: 뉴스 헤드라인 리스트
        community_posts: 커뮤니티 게시글 리스트

    Returns:
        (score, label) 튜플
        - score: -100 ~ +100 정규화된 감정 점수
        - label: 감정 라벨 문자열 (예: "🟢 긍정")
    """
    total_score = 0
    total_items = 0

    for news in news_list:
        total_score += _score_text(news.title)
        if news.summary:
            total_score += _score_text(news.summary)
        total_items += 1

    for post in community_posts:
        total_score += _score_text(post.title)
        total_items += 1

    if total_items == 0:
        return 0, "🟡 중립"

    # 정규화: 항목당 평균 점수를 -100 ~ +100 범위로 스케일
    # 항목당 최대 점수를 ±4로 가정 (키워드 2개 동시 매칭)
    avg_score = total_score / total_items
    normalized = max(-100, min(100, int(avg_score * 25)))

    # 라벨 결정
    if normalized <= -50:
        label = "🔴 극도의 공포"
    elif normalized <= -20:
        label = "🟠 부정적"
    elif normalized <= 20:
        label = "🟡 중립"
    elif normalized <= 50:
        label = "🟢 긍정적"
    else:
        label = "🔵 극도의 탐욕"

    global_logger.info(f"📊 [Sentiment] 감정 점수: {normalized} ({label}) - {total_items}건 분석")
    return normalized, label


def format_sentiment_section(score: int, label: str) -> str:
    """감정 지표를 마크다운 리포트 섹션으로 포맷합니다.

    Args:
        score: 감정 점수 (-100 ~ +100)
        label: 감정 라벨

    Returns:
        마크다운 형식의 시장 심리 온도계 섹션
    """
    # 게이지 바 시각화 (20칸)
    gauge_pos = max(0, min(20, (score + 100) // 10))
    gauge_bar = "▓" * gauge_pos + "░" * (20 - gauge_pos)

    return f"""### 🌡️ 시장 심리 온도계

**감정 점수**: {score}/100 {label}

```
공포 ← [{gauge_bar}] → 탐욕
-100                           +100
```

> 커뮤니티 여론과 뉴스 헤드라인 키워드를 분석한 시장 심리 지표입니다.
"""
