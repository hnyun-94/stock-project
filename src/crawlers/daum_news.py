"""
다음 뉴스 크롤러 모듈.

다음 경제/증권 섹션 뉴스 검색을 통해 네이버 뉴스 외의 시각을 확보합니다.
"""

from typing import List
import aiohttp
from bs4 import BeautifulSoup
from tenacity import retry, wait_exponential, stop_after_attempt

from src.models import NewsArticle
from src.utils.logger import global_logger
from src.utils.circuit_breaker import async_circuit_breaker

@async_circuit_breaker(failure_threshold=3, recovery_timeout=60, fallback_value=[])
@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def search_daum_news_by_keyword(keyword: str, max_items: int = 5) -> List[NewsArticle]:
    """
    역할:
        특정 키워드를 사용하여 다음(Daum) 뉴스 웹사이트를 비동기적으로 크롤링하고,
        검색 결과에서 뉴스 기사 목록을 추출합니다. 네트워크 오류 또는 응답 문제 발생 시
        자동 재시도 로직이 적용되어 안정적인 데이터 확보를 목표로 합니다.
        추출된 뉴스는 `NewsArticle` 객체 형태로 반환됩니다.

    입력:
        keyword (str): 검색할 관심 키워드
        max_items (int): 최대 뉴스 기사 수

    반환값:
        List[NewsArticle]: 수집된 뉴스 객체 리스트
    """
    url = f"https://search.daum.net/search?w=news&q={keyword}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    news_list = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                html = await response.text()
                
                soup = BeautifulSoup(html, "html.parser")
                
                # 다음 뉴스 검색 결과 리스트 아이템 선택 (CSS 셀렉터는 변경될 수 있음)
                articles = soup.select("ul.c-list-basic li")
                
                for item in articles[:max_items]:
                    title_elem = item.select_one("div.item-title a")
                    # 언론사 정보 파싱
                    pub_elem = item.select_one("div.item-info span.item-title")
                    
                    if title_elem:
                        # 공백 제거 및 정리
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get("href", "")
                        publisher = pub_elem.get_text(strip=True) if pub_elem else "다음 뉴스"
                        
                        # 데스크톱 URL로 변경 (mo.daum.net 등 방지)
                        if "v.media.daum.net" in link or "v.daum.net" in link:
                            news_list.append(NewsArticle(title=title, link=link, publisher=publisher))
                            
    except Exception as e:
        global_logger.error(f"[Daum뉴스] 크롤링 중 에러 발생 ({keyword}): {e}")
        raise e  # Tenacity Retry 동작 트리거, 이후 서킷 브레이커로 인계
        
    global_logger.info(f"[Daum뉴스] '{keyword}' 검색: {len(news_list)}건 수집 완료")
    return news_list
