"""
뉴스 본문 리드(Lead) 문단 추출 모듈.

수집된 뉴스 기사의 URL을 방문하여 본문 첫 2~3문장(리드 문단)을 추출합니다.
리드 문단은 기사의 핵심 내용을 요약한 부분으로, AI 프롬프트에 제목만 전달하는 것보다
훨씬 풍부한 컨텍스트를 제공하여 요약 품질을 크게 향상시킵니다.

- 비동기 HTTP 요청으로 성능 영향 최소화
- 실패 시 기존 summary를 유지하여 안전하게 동작
- 과도한 요청 방지를 위한 Semaphore 제한

사용법:
    from src.crawlers.article_parser import enrich_news_with_leads

    # 뉴스 리스트에 리드 문단 추가
    enriched_news = await enrich_news_with_leads(news_list)

[Task 6.10, REQ-F01]
"""

import re
import asyncio
from typing import List
from bs4 import BeautifulSoup

from src.models import NewsArticle
from src.crawlers.http_client import get_session
from src.utils.logger import global_logger

# 동시 본문 요청 수 제한 (서버 부하 방지)
_PARSE_SEMA = asyncio.Semaphore(3)

# 본문 추출 시 최소/최대 글자 수
_MIN_LEAD_LENGTH = 30
_MAX_LEAD_LENGTH = 300


async def _fetch_lead_paragraph(url: str) -> str:
    """뉴스 URL에서 본문 리드 문단(첫 2~3문장)을 추출합니다.

    Args:
        url: 뉴스 기사 URL

    Returns:
        리드 문단 텍스트. 실패 시 빈 문자열 반환.
    """
    try:
        async with _PARSE_SEMA:
            session = await get_session()
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return ""
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")

        # 주요 뉴스 사이트별 본문 셀렉터 (우선순위순)
        selectors = [
            "article",                          # 표준 HTML5 시맨틱
            "#articleBodyContents",             # 네이버 뉴스
            "#harmonyContainer .article_body",  # 네이버 뉴스 (신규)
            ".news_end",                        # 다음 뉴스
            "#article-view-content-div",        # 기타 언론사
            ".article-body",                    # 범용
            ".article_txt",                     # 범용
        ]

        body_text = ""
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # 스크립트/스타일 태그 제거
                for tag in element.find_all(["script", "style", "iframe"]):
                    tag.decompose()
                body_text = element.get_text(separator=" ", strip=True)
                if len(body_text) >= _MIN_LEAD_LENGTH:
                    break

        if len(body_text) < _MIN_LEAD_LENGTH:
            return ""

        # 문장 단위로 분리하여 첫 2~3문장 추출
        sentences = re.split(r'(?<=[.!?다])\s+', body_text)
        lead = ""
        for sent in sentences[:3]:
            if len(lead) + len(sent) > _MAX_LEAD_LENGTH:
                break
            lead += sent + " "

        return lead.strip()

    except Exception:
        return ""


async def enrich_news_with_leads(
    news_list: List[NewsArticle],
    max_articles: int = 5
) -> List[NewsArticle]:
    """뉴스 리스트의 각 기사에 본문 리드 문단을 추가합니다.

    기존 summary가 비어있는 기사에만 리드 문단을 추출하여 채웁니다.
    성능을 위해 최대 max_articles개까지만 처리합니다.

    Args:
        news_list: 대상 뉴스 리스트
        max_articles: 리드 추출할 최대 기사 수 (기본 5개)

    Returns:
        리드 문단이 추가된 뉴스 리스트 (원본 수정)
    """
    if not news_list:
        return news_list

    # summary가 비어있는 기사만 대상
    targets = [n for n in news_list[:max_articles] if not n.summary]

    if not targets:
        return news_list

    # 비동기 병렬로 본문 추출
    tasks = [_fetch_lead_paragraph(n.link) for n in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched_count = 0
    for news, result in zip(targets, results):
        if isinstance(result, str) and result:
            news.summary = result
            enriched_count += 1

    if enriched_count > 0:
        global_logger.info(f"📰 [Lead] {len(targets)}건 중 {enriched_count}건 리드 문단 추출 완료")

    return news_list
