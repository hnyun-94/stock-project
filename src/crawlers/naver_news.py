"""
네이버 금융 및 일반 검색 뉴스 크롤러 모듈.

이 모듈은 주식 리포트 생성을 위해 네이버 금융의 주요 시황(Track A) 및
사용자 지정 키워드 기반의 뉴스(Track B) 데이터를 수집하는 기능을 제공합니다.
"""

from typing import List, Dict
import aiohttp
from bs4 import BeautifulSoup

from src.models import NewsArticle
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_market_news() -> List[NewsArticle]:
    """네이버 금융 주요시황 뉴스의 헤드라인과 링크를 크롤링합니다.

    Returns:
        List[NewsArticle]: 뉴스 제목('title')과 원래 기사 링크('link')를 담은 DTO 리스트.
    """
    url = "https://finance.naver.com/news/mainnews.naver"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=10) as response:
            response.raise_for_status()
            html = await response.text(encoding='euc-kr')

    soup = BeautifulSoup(html, "html.parser")
    news_list = []
    
    # 'mode=mainnews' 파라미터가 있는 a 태그를 모두 찾음
    main_news_links = soup.find_all("a", href=lambda href: href and "mode=mainnews" in href)
    
    seen_links = set()
    for a in main_news_links:
        title = a.get_text(strip=True)
        # 텍스트가 존재하는 링크만 캡처 (이미지는 건너뜀)
        if title and len(title) > 3:
            link = "https://finance.naver.com" + a['href']
            if link not in seen_links:
                news_list.append(NewsArticle(title=title, link=link))
                seen_links.add(link)
                
        if len(news_list) >= 10:
            break
            
    return news_list


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def search_news_by_keyword(keyword: str, max_items: int = 5) -> List[NewsArticle]:
    """주어진 키워드로 네이버 뉴스를 검색하여 결과를 반환합니다.

    사용자 관심 테마(키워드)별로 최신/정확도 높은 기사를 수집할 때 사용합니다.

    Args:
        keyword (str): 검색할 관심 키워드 (예: '반도체', '엔비디아')
        max_items (int): 가져올 최대 뉴스 개수. (기본값 5)

    Returns:
        List[NewsArticle]: 뉴스 제목('title')과 링크('link')를 담은 DTO 리스트.
    """
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=10) as response:
            response.raise_for_status()
            html = await response.text()
            
    soup = BeautifulSoup(html, "html.parser")
    news_list = []
    
    # 최근 네이버 검색 결과는 title 속성보다 inner text에 기사 제목을 노출함
    anchors = soup.select(".news_area a.news_tit")
    if not anchors:
        # fallback
        anchors = soup.find_all("a", target="_blank")
        
    for a in anchors:
        title = a.get("title") or a.get_text(strip=True)
        link = a.get("href")
        
        # 네이버 자체 UI 링크가 아닌 실제 기사인 경우
        if title and len(title) > 5 and link and link.startswith("http") and "naver.com" not in title:
            # 중복 제목 방지
            if not any(n.title == title for n in news_list):
                news_list.append(NewsArticle(title=title, link=link))
                
        if len(news_list) >= max_items:
            break
            
    return news_list
