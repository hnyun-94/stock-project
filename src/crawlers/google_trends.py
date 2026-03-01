"""
구글 트렌드 검색어 수집 모듈.

feedparser 기반으로 Google Trends RSS 피드를 가져와 
파이썬 라이브러리 버전 이슈(404 에러 등)에 구애받지 않고 안정적으로 데이터를 수집합니다.
"""

from typing import List, Dict
import aiohttp
import feedparser
import traceback

from src.models import SearchTrend
from src.utils.logger import global_logger
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_daily_trending_searches() -> List[SearchTrend]:
    """대한민국(KR)의 일별 구글 인기 검색어 트렌드를 RSS로 반환합니다.

    Returns:
        List[SearchTrend]: 검색어 트렌드 정보(키워드, 트래픽, 뉴스 정보)가 포함된 DTO 리스트.
    """
    trends = []
    try:
        url = "https://trends.google.co.kr/trending/rss?geo=KR"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                xml_data = await response.text()
                
        feed = feedparser.parse(xml_data)
        
        # 최상위 10개 트렌딩 토픽 수집
        for entry in feed.entries[:10]:
            title = entry.title
            
            # approximateTraffic 이 존재하면 사용, 없으면 빈 문자열
            traffic = getattr(entry, "ht_approximatetraffic", "N/A")
            
            # 연관 기사 중 첫 번째 링크가 있으면 포함
            news_link = ""
            if hasattr(entry, "ht_news_item") and len(entry.ht_news_item) > 0:
                # 내부 딕셔너리에 ht:news_item_url 등이 있음
                news_item = entry.ht_news_item[0]
                news_link = news_item.get('ht_news_item_url', "")
                
            trends.append(SearchTrend(
                keyword=title,
                traffic=traffic,
                news_link=news_link
            ))
            
    except Exception as e:
        global_logger.error(f"구글 트렌드 일별 검색어 수집 실패: {e}")
        traceback.print_exc()

    return trends

def get_realtime_trending_searches() -> List[SearchTrend]:
    """실시간 구글 트렌드 검색어 (RSS 피드는 일간 데이터에 최적화되어 있으므로 fallback 형태 제공)
    
    API 이슈(404) 회피를 위해 일별 트렌드와 동일한 피드로 임시 반환하도록 합니다.
    """
    return get_daily_trending_searches()
