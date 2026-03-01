import pytest
from src.crawlers.daum_news import search_daum_news_by_keyword
from src.models import NewsArticle

@pytest.mark.asyncio
async def test_search_daum_news_by_keyword_returns_dto_list():
    """다음 뉴스 검색을 수행하여 DTO 리스트를 반환하는지 테스트"""
    news = await search_daum_news_by_keyword("테슬라", max_items=2)
    assert isinstance(news, list)
    assert len(news) <= 2
    
    if news:
        article = news[0]
        assert isinstance(article, NewsArticle)
        assert len(article.title) > 0
        assert "http" in article.link
