"""
뉴스 제목 기반 중복 제거(Deduplication) 모듈.

네이버, 다음, 구글 3개 소스에서 동일 뉴스가 중복 수집되는 문제를 해결합니다.
제목의 유사도를 비교하여 85% 이상 겹치는 뉴스를 필터링합니다.

외부 라이브러리 없이 Python 표준 라이브러리(difflib)만 사용하여
SequenceMatcher 기반의 가벼운 유사도 비교를 수행합니다.

사용법:
    from src.utils.deduplicator import deduplicate_news

    # 여러 소스에서 수집된 뉴스 리스트를 중복 제거
    unique_news = deduplicate_news(all_news_list, threshold=0.85)

[Task 6.9, REQ-F02]
"""

from difflib import SequenceMatcher
from typing import List
from src.models import NewsArticle
from src.utils.logger import global_logger


def _normalize_title(title: str) -> str:
    """제목에서 비교에 불필요한 문자를 제거합니다.

    Args:
        title: 원본 뉴스 제목

    Returns:
        정규화된 제목 문자열
    """
    # 대괄호 태그 제거: [속보], [단독], [종합] 등
    import re
    title = re.sub(r'\[.*?\]', '', title)
    # 앞뒤 공백 및 말줄임표 제거
    title = title.strip().rstrip('...')
    return title


def _similarity(a: str, b: str) -> float:
    """두 문자열의 유사도를 0.0~1.0 사이 값으로 반환합니다.

    SequenceMatcher는 두 시퀀스의 유사도를 계산하는 표준 라이브러리입니다.
    Levenshtein 거리보다 가볍고, 제목 비교에 충분한 정확도를 제공합니다.

    Args:
        a: 첫 번째 문자열
        b: 두 번째 문자열

    Returns:
        유사도 (0.0 = 완전히 다름, 1.0 = 동일)
    """
    return SequenceMatcher(None, a, b).ratio()


def deduplicate_news(
    news_list: List[NewsArticle],
    threshold: float = 0.85
) -> List[NewsArticle]:
    """뉴스 리스트에서 제목 유사도 기반으로 중복을 제거합니다.

    먼저 등장한 뉴스를 우선 유지하고, 이후 유사한 제목의 뉴스는 필터링합니다.
    O(n²) 비교이지만 뉴스 수가 적어(~20개 이하) 성능 문제가 없습니다.

    Args:
        news_list: 중복이 포함된 뉴스 리스트
        threshold: 유사도 임계값 (기본 0.85 = 85% 이상 유사하면 중복으로 판정)

    Returns:
        중복이 제거된 뉴스 리스트
    """
    if not news_list:
        return []

    unique: List[NewsArticle] = []
    seen_titles: List[str] = []

    for news in news_list:
        normalized = _normalize_title(news.title)

        is_duplicate = False
        for seen in seen_titles:
            if _similarity(normalized, seen) >= threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique.append(news)
            seen_titles.append(normalized)

    removed_count = len(news_list) - len(unique)
    if removed_count > 0:
        global_logger.info(f"🔄 [Dedup] {len(news_list)}건 → {len(unique)}건 (중복 {removed_count}건 제거)")

    return unique
