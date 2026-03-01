"""
구글 뉴스 검색 크롤러 모듈.

다양한 정보 소스를 확보하기 위해 구글 뉴스의 RSS 피드를 연동합니다.
이 모듈은 주어진 키워드를 사용하여 구글 뉴스 RSS 피드에서 최신 뉴스 기사를 검색하고,
파싱하여 구조화된 형태로 반환하는 기능을 제공합니다.
"""

from typing import List
import aiohttp
import feedparser

from src.models import NewsArticle
from src.utils.logger import global_logger
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def search_google_news_by_keyword(keyword: str, max_items: int = 5) -> List[NewsArticle]:
    """
    주어진 키워드로 구글 뉴스(Google News) RSS 피드를 검색하고, 파싱하여 뉴스 기사 목록을 반환합니다.
    네트워크 오류나 파싱 실패 시 재시도 메커니즘이 적용됩니다.

    역할:
        특정 키워드에 대한 구글 뉴스 기사들을 비동기적으로 검색하고,
        각 기사의 제목과 원본 링크를 추출하여 `NewsArticle` 객체 리스트로 제공합니다.
        검색 중 발생할 수 있는 일시적인 네트워크 문제에 대비하여 재시도 로직을 포함합니다.

    입력:
        keyword (str): 검색할 관심 키워드입니다. 이 키워드를 사용하여 구글 뉴스 RSS 피드를 조회합니다.
                       예시: "인공지능", "기후 변화", "반도체 동향"
        max_items (int, optional): 가져올 최대 뉴스 기사 개수입니다. RSS 피드에서 이 개수만큼의 기사를 파싱합니다.
                                   기본값은 5입니다.
                                   예시: 5, 10, 20

    반환값:
        List[NewsArticle]: 검색된 뉴스 기사 객체들의 리스트입니다.
                           각 `NewsArticle` 객체는 `title` (기사 제목)과 `link` (원본 기사 링크)를 포함합니다.
                           네트워크 문제나 RSS 파싱 오류가 발생하면 `Exception`을 발생시킵니다.
                           예시: [
                               NewsArticle(title='삼성전자, 새로운 AI 칩 공개', link='https://news.google.com/articles/1234'),
                               NewsArticle(title='기후 변화 대응을 위한 국제 협력 강화', link='https://news.google.com/articles/5678')
                           ]
    """
    url = f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"
    news_list = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                xml_data = await response.text()
                
        feed = feedparser.parse(xml_data)
        
        for entry in feed.entries[:max_items]:
            title = entry.title
            link = entry.link
            
            # Google News RSS 제목 포맷: '기사 제목 - 언론사'
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
                
            news_list.append(NewsArticle(title=title, link=link))
            
    except Exception as e:
        global_logger.error(f"구글 뉴스 검색 실패 ({keyword}): {e}")
        raise e  # tenacity 재시도를 위해 예외를 다시 발생시킴

    return news_list
