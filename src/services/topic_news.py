"""
토픽별 뉴스 수집 서비스.

역할:
1. 키워드/보유종목별 뉴스를 병렬 수집합니다.
2. 캐시, 중복 제거, 리드 문단 추출을 공통화합니다.
3. 동일한 토픽이 여러 기능에서 재사용될 때 main.py의 중복 로직을 줄입니다.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Iterable, List

from src.crawlers.article_parser import enrich_news_with_leads
from src.crawlers.daum_news import search_daum_news_by_keyword
from src.crawlers.google_news import search_google_news_by_keyword
from src.crawlers.naver_news import search_news_by_keyword
from src.models import NewsArticle
from src.utils.cache import crawl_cache
from src.utils.deduplicator import deduplicate_news


async def collect_topic_news(
    topics: Iterable[str],
    cache_prefix: str,
    max_news: int = 7,
    max_lead_articles: int = 3,
) -> Dict[str, List[NewsArticle]]:
    """토픽별 뉴스를 병렬 수집하고 캐시합니다."""
    normalized_topics = [topic.strip() for topic in topics if topic and topic.strip()]
    if not normalized_topics:
        return {}

    topic_results: Dict[str, List[NewsArticle]] = {}
    uncached_topics: List[str] = []

    for topic in normalized_topics:
        cached = crawl_cache.get(f"{cache_prefix}:{topic}")
        if cached is not None:
            topic_results[topic] = cached
        else:
            uncached_topics.append(topic)

    if uncached_topics:
        # 캐시 miss 토픽만 3개 뉴스 소스로 fan-out 한 뒤 dedupe/enrich/cache 순으로 정리합니다.
        crawl_tasks = []
        for topic in uncached_topics:
            crawl_tasks.extend(
                [
                    search_news_by_keyword(topic, 3),
                    search_daum_news_by_keyword(topic, 3),
                    search_google_news_by_keyword(topic, 3),
                ]
            )

        all_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
        for index, topic in enumerate(uncached_topics):
            grouped_results = all_results[index * 3 : (index + 1) * 3]
            flat_news: List[NewsArticle] = []
            for result in grouped_results:
                if isinstance(result, list):
                    flat_news.extend(result)
            news_list = deduplicate_news(flat_news)[:max_news]
            news_list = await enrich_news_with_leads(
                news_list,
                max_articles=max_lead_articles,
            )
            topic_results[topic] = news_list
            crawl_cache.set(f"{cache_prefix}:{topic}", news_list)

    return {topic: topic_results.get(topic, []) for topic in normalized_topics}
