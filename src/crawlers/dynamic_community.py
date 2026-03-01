"""
동적 렌더링(CSR) 커뮤니티 파싱 전용 크롤러.

Playwright를 백그라운드(Headless)로 띄워
자바스크립트로 렌더링되거나 모바일 뷰 전용인 커뮤니티(토스, 블라인드 등)를 수집합니다.
"""

from typing import List
from playwright.async_api import async_playwright
from tenacity import retry, wait_exponential, stop_after_attempt

from src.models import CommunityPost
from src.utils.logger import global_logger
from src.crawlers.browser_pool import BrowserPool
from src.utils.circuit_breaker import async_circuit_breaker

@async_circuit_breaker(failure_threshold=2, recovery_timeout=60, fallback_value=[])
@retry(wait=wait_exponential(multiplier=2, min=5, max=15), stop=stop_after_attempt(3))
async def get_blind_stock_lounge(max_items: int = 3) -> List[CommunityPost]:
    """블라인드(Blind) 주식/투자 라운지의 인기글을 캡처합니다."""
    url = "https://www.teamblind.com/kr/topics/%EC%A3%BC%EC%8B%9D%C2%B7%ED%88%AC%EC%9E%90"
    posts = []
    
    try:
        browser = await BrowserPool.get_browser()
        # 매 연결마다 새로운 컨텍스트(캐시 비우기 및 격리)만 생성
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 페이지 로드 (자체 타임아웃 설정)
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # 동적 렌더링 대기
        await page.wait_for_selector(".article-list", timeout=10000)
        
        # 평가: 라운지의 게시글 목록 파싱
        article_elements = await page.query_selector_all(".article-list .article-list-item")
        
        for el in article_elements[:max_items]:
            title_elem = await el.query_selector("strong")
            link_elem = await el.query_selector("a")
            
            if title_elem and link_elem:
                title = await title_elem.inner_text()
                href = await link_elem.get_attribute("href")
                full_link = f"https://www.teamblind.com{href}" if href.startswith("/") else href
                posts.append(CommunityPost(title=f"[블라인드] {title}", link=full_link))
                
        # 리소스 반환 
        await context.close()
            
    except Exception as e:
        global_logger.error(f"블라인드(Playwright) 크롤링 중 예외 발생: {e}")
        raise e  # Tenacity Retry -> Circuit Breaker 로 넘김
        
    return posts
