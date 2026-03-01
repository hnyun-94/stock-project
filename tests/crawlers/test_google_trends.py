"""
이 모듈은 Google Trends 크롤러인 `get_daily_trending_searches` 함수의 동작을 테스트합니다.
주요 목적은 해당 함수가 예상되는 `SearchTrend` DTO 객체 리스트를 올바른 형식으로 반환하는지 검증하는 것입니다.
"""
import pytest
from src.models import SearchTrend
from src.crawlers.google_trends import get_daily_trending_searches

@pytest.mark.asyncio
async def test_get_daily_trending_searches_returns_dto():
    """
    `get_daily_trending_searches` 함수가 `SearchTrend` DTO 리스트를 올바르게 반환하는지 검증합니다.

    역할:
        Google Trends에서 일일 인기 검색어를 가져오는 크롤러 함수인
        `get_daily_trending_searches`가 호출될 때, 그 반환값이
        `SearchTrend` 객체의 리스트이며 각 `SearchTrend` 객체가
        `keyword`, `traffic`, `news_link`와 같은 필수 속성을
        포함하고 있는지 확인합니다.

    입력:
        없음. 이 함수는 테스트 함수로, 직접적인 입력을 받지 않습니다.

    반환값:
        없음. 테스트 성공 시 아무것도 반환하지 않으며,
        어설션(assertion) 실패 시 예외를 발생시킵니다.
        (예: `AssertionError`)
    """
    trends = await get_daily_trending_searches()
    assert isinstance(trends, list)
    
    if trends:
        trend = trends[0]
        assert isinstance(trend, SearchTrend)
        assert hasattr(trend, 'keyword')
        assert hasattr(trend, 'traffic')
        assert hasattr(trend, 'news_link')
        assert len(trend.keyword) > 0
