"""
이 모듈은 네이버 뉴스 크롤러 (`src.crawlers.naver_news`)의 핵심 기능을 테스트합니다.
주요 시황 뉴스 수집 및 키워드 기반 뉴스 검색 기능이 예상하는 `NewsArticle` DTO 리스트 형태로
데이터를 올바르게 반환하는지 검증하는 비동기 테스트 함수들을 포함하고 있습니다.
"""
import pytest
from src.models import NewsArticle
from src.crawlers.naver_news import get_market_news, search_news_by_keyword

@pytest.mark.asyncio
async def test_get_market_news_returns_dto_list():
    """
    `get_market_news` 함수가 주요 시황 뉴스 기사를 `NewsArticle` DTO 리스트 형태로
    올바르게 수집하고 반환하는지 검증합니다.

    역할:
        - `get_market_news` 함수를 호출하여 뉴스 목록을 가져옵니다.
        - 반환된 객체가 리스트 타입인지 확인합니다.
        - 리스트가 비어있지 않다면, 첫 번째 항목이 `NewsArticle` DTO 인스턴스인지 확인합니다.
        - `NewsArticle` DTO의 `title`과 `link` 필드가 유효한 값을 포함하는지 검증합니다.

    입력:
        없음

    반환값:
        없음. (Pytest의 assertion을 통해 테스트 성공/실패를 판단합니다.)
    """
    news_list = await get_market_news()
    
    assert isinstance(news_list, list)
    # 최소 1개 이상은 크롤링 되어야 함
    if news_list:
        article = news_list[0]
        assert isinstance(article, NewsArticle)
        assert len(article.title) > 0
        assert "http" in article.link

@pytest.mark.asyncio
async def test_search_news_by_keyword_returns_dto_list():
    """
    `search_news_by_keyword` 함수가 특정 키워드로 검색된 뉴스 기사 목록을
    `NewsArticle` DTO 리스트 형태로 올바르게 반환하는지 검증합니다.

    역할:
        - 특정 키워드(예: "반도체")와 `max_items` 제한으로 `search_news_by_keyword` 함수를 호출합니다.
        - 반환된 객체가 리스트 타입인지, 그리고 `max_items` 이하의 항목 수를 가지는지 확인합니다.
        - 리스트 내의 각 항목이 `NewsArticle` DTO 인스턴스인지 확인합니다.
        - 각 `NewsArticle` DTO의 `title`과 `link` 필드가 유효한 값을 포함하는지 검증합니다.

    입력:
        없음. (테스트 내부에서 `keyword`와 `max_items`를 정의하여 사용합니다.)

    반환값:
        없음. (Pytest의 assertion을 통해 테스트 성공/실패를 판단합니다.)
    """
    keyword = "반도체"
    news_list = await search_news_by_keyword(keyword, max_items=2)
    
    assert isinstance(news_list, list)
    assert len(news_list) > 0
    assert len(news_list) <= 2
    
    for article in news_list:
        assert isinstance(article, NewsArticle)
        assert hasattr(article, 'title')
        assert hasattr(article, 'link')
        assert len(article.title) > 0
        assert article.link.startswith("http")
