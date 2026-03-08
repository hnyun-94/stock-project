"""
토픽별 뉴스 수집 서비스.

역할:
1. 키워드/보유종목별 뉴스를 병렬 수집합니다.
2. 캐시, 중복 제거, 리드 문단 추출을 공통화합니다.
3. 동일한 토픽이 여러 기능에서 재사용될 때 main.py의 중복 로직을 줄입니다.
"""

from __future__ import annotations

import asyncio
import re
from typing import Dict, Iterable, List, Sequence

from src.crawlers.article_parser import enrich_news_with_leads
from src.crawlers.daum_news import search_daum_news_by_keyword
from src.crawlers.google_news import search_google_news_by_keyword
from src.crawlers.naver_news import search_news_by_keyword
from src.models import CommunityPost, NewsArticle
from src.utils.cache import crawl_cache
from src.utils.deduplicator import deduplicate_news

_CACHE_VERSION = "v2"
_SOURCE_FETCH_DEPTH = 4
_TOPIC_QUERY_ALIASES = {
    "ai": ["인공지능", "AI 반도체"],
    "인공지능": ["AI", "AI 반도체"],
    "2차전지": ["이차전지", "배터리"],
    "이차전지": ["2차전지", "배터리"],
    "배터리": ["이차전지", "2차전지"],
    "s&p500": ["미국 증시", "뉴욕증시"],
    "sp500": ["S&P500", "미국 증시"],
    "미국증시": ["S&P500", "뉴욕증시"],
    "뉴욕증시": ["S&P500", "미국 증시"],
}
_TOPIC_SIGNAL_TERMS = {
    "ai": ["AI", "인공지능", "GPU", "HBM", "데이터센터", "반도체", "엔비디아"],
    "인공지능": ["AI", "GPU", "HBM", "데이터센터", "반도체", "빅테크"],
    "2차전지": ["이차전지", "배터리", "전기차", "양극재", "리튬", "광물"],
    "이차전지": ["2차전지", "배터리", "전기차", "양극재", "리튬", "광물"],
    "배터리": ["이차전지", "2차전지", "전기차", "양극재", "리튬"],
    "s&p500": ["S&P500", "미국 증시", "뉴욕증시", "나스닥", "빅테크", "연준", "고용", "물가"],
    "sp500": ["S&P500", "미국 증시", "뉴욕증시", "나스닥", "빅테크", "연준", "고용", "물가"],
    "미국증시": ["S&P500", "뉴욕증시", "나스닥", "빅테크", "연준", "고용", "물가"],
    "뉴욕증시": ["S&P500", "미국 증시", "나스닥", "빅테크", "연준", "고용", "물가"],
}


def _normalize_topic_key(topic: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", topic.strip().lower())


def _dedupe_terms(items: Sequence[str]) -> List[str]:
    deduped: List[str] = []
    seen: set[str] = set()
    for item in items:
        term = item.strip()
        if not term:
            continue
        normalized = term.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(term)
    return deduped


def _topic_queries(topic: str) -> List[str]:
    normalized = _normalize_topic_key(topic)
    return _dedupe_terms([topic, *(_TOPIC_QUERY_ALIASES.get(normalized, [])[:1])])


def _topic_terms(topic: str) -> List[str]:
    normalized = _normalize_topic_key(topic)
    return _dedupe_terms([topic, *(_TOPIC_QUERY_ALIASES.get(normalized, [])), *(_TOPIC_SIGNAL_TERMS.get(normalized, []))])


def _score_topic_text(topic: str, text: str) -> int:
    lowered = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if not lowered:
        return -1

    normalized = _normalize_topic_key(topic)
    aliases = [topic, *(_TOPIC_QUERY_ALIASES.get(normalized, []))]
    score = sum(4 for alias in aliases if alias and alias.lower() in lowered)
    score += sum(1 for term in _TOPIC_SIGNAL_TERMS.get(normalized, []) if term.lower() in lowered)
    if any(fragment in lowered for fragment in ("keep에 바로가기", "주요기사", "구독하세요")):
        score -= 3
    return score


def filter_topic_news(
    topic: str,
    news_items: Sequence[NewsArticle],
    *,
    limit: int,
) -> List[NewsArticle]:
    """토픽과 직접 맞닿은 뉴스만 우선순위화해 반환합니다."""
    scored_items: List[tuple[int, int, NewsArticle]] = []
    for index, article in enumerate(deduplicate_news(news_items)):
        joined_text = f"{article.title} {article.summary or ''}"
        relevance_score = _score_topic_text(topic, joined_text)
        if article.summary:
            relevance_score += 1
        scored_items.append((relevance_score, -index, article))

    if not scored_items:
        return []

    scored_items.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if any(score > 0 for score, _, _ in scored_items):
        scored_items = [item for item in scored_items if item[0] > 0]

    return [article for _, _, article in scored_items[:limit]]


def select_topic_community_posts(
    topic: str,
    community_posts: Sequence[CommunityPost],
    *,
    limit: int = 3,
) -> List[CommunityPost]:
    """토픽과 관련된 커뮤니티 글만 선별해 테마 컨텍스트에 전달합니다."""
    scored_posts: List[tuple[int, int, CommunityPost]] = []
    for index, post in enumerate(community_posts):
        relevance_score = _score_topic_text(topic, post.title)
        if relevance_score <= 0:
            continue
        scored_posts.append((relevance_score, -index, post))

    scored_posts.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [post for _, _, post in scored_posts[:limit]]


async def collect_topic_news(
    topics: Iterable[str],
    cache_prefix: str,
    max_news: int = 10,
    max_lead_articles: int = 4,
) -> Dict[str, List[NewsArticle]]:
    """토픽별 뉴스를 병렬 수집하고 캐시합니다."""
    normalized_topics = [topic.strip() for topic in topics if topic and topic.strip()]
    if not normalized_topics:
        return {}

    topic_results: Dict[str, List[NewsArticle]] = {}
    uncached_topics: List[str] = []

    for topic in normalized_topics:
        cached = crawl_cache.get(f"{cache_prefix}:{_CACHE_VERSION}:{topic}")
        if cached is not None:
            topic_results[topic] = cached
        else:
            uncached_topics.append(topic)

    if uncached_topics:
        # 캐시 miss 토픽만 alias 1개까지 포함해 fan-out 한 뒤, 토픽 적합도 기준으로 다시 정렬합니다.
        crawl_tasks = []
        topic_queries = {topic: _topic_queries(topic) for topic in uncached_topics}
        for topic in uncached_topics:
            for query in topic_queries[topic]:
                crawl_tasks.extend(
                    [
                        search_news_by_keyword(query, _SOURCE_FETCH_DEPTH),
                        search_daum_news_by_keyword(query, _SOURCE_FETCH_DEPTH),
                        search_google_news_by_keyword(query, _SOURCE_FETCH_DEPTH),
                    ]
                )

        all_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
        cursor = 0
        for index, topic in enumerate(uncached_topics):
            query_count = len(topic_queries[topic]) * 3
            grouped_results = all_results[cursor : cursor + query_count]
            cursor += query_count
            flat_news: List[NewsArticle] = []
            for result in grouped_results:
                if isinstance(result, list):
                    flat_news.extend(result)
            news_list = filter_topic_news(topic, flat_news, limit=max_news)
            news_list = await enrich_news_with_leads(
                news_list,
                max_articles=max_lead_articles,
            )
            topic_results[topic] = news_list
            crawl_cache.set(f"{cache_prefix}:{_CACHE_VERSION}:{topic}", news_list)

    return {topic: topic_results.get(topic, []) for topic in normalized_topics}
