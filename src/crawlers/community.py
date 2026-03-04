"""
주식 커뮤니티 반응 수집 모듈.

네이버 증권 인기 검색 종목의 종목토론방(종토방) 및
디시인사이드 주식갤러리(식갤)의 개념글(인기글)을 수집하여 시장의 민심과 화제성을 파악합니다.
"""

from typing import List, Dict
import os
import aiohttp
from src.crawlers.http_client import get_session
from bs4 import BeautifulSoup

from src.models import CommunityPost
from src.utils.logger import global_logger
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_popular_stocks() -> List[Dict[str, str]]:
    """네이버 증권 인기 검색 종목 Top 5를 가져옵니다.

    역할:
        네이버 증권에서 현재 가장 많이 검색되는 인기 종목 상위 5개를 비동기적으로 스크랩합니다.
        이를 통해 시장의 관심 종목과 화제성을 파악할 수 있습니다.

    입력:
        없음 (인자 없음)

    반환값:
        List[Dict[str, str]]: 종목명('name')과 종목코드('code') 딕셔너리 리스트
            각 딕셔너리는 'name' (종목명)과 'code' (종목코드) 키를 가집니다.
            예시: `[{'name': '삼성전자', 'code': '005930'}, {'name': 'SK하이닉스', 'code': '000660'}]`
    """
    url = "https://finance.naver.com/sise/lastsearch2.naver"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    session = await get_session()
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as res:
        res.raise_for_status()
        html = await res.read()
            
    soup = BeautifulSoup(html, "html.parser", from_encoding="euc-kr")
    stocks = []
    
    # type_5 테이블 내에 인기 검색 종목들이 노출됨
    rows = soup.select("table.type_5 tr")
    for row in rows:
        a_tag = row.select_one("a.tltle")
        if a_tag:
            name = a_tag.get_text(strip=True)
            href = a_tag["href"]  # 예: /item/main.naver?code=005930
            code = href.split("code=")[-1]
            stocks.append({"name": name, "code": code})
            if len(stocks) >= 5:
                break
                
    return stocks


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_naver_board_posts(code: str, name: str, max_items: int = 3) -> List[CommunityPost]:
    """특정 종목의 네이버 종토방 최신/인기 게시글 제목을 수집합니다.

    역할:
        주어진 종목 코드에 해당하는 네이버 증권 종목토론방(종토방)의 최신 게시글 제목과 링크를
        비동기적으로 수집합니다. 이를 통해 개별 종목에 대한 투자자들의 실시간 의견을 파악할 수 있습니다.

    입력:
        code (str): 종목 코드.
            예시: `'005930'` (삼성전자)
        name (str): 종목명.
            수집된 게시글 제목 앞에 "[종목명]" 형태로 붙여 사용됩니다.
            예시: `'삼성전자'`
        max_items (int, 선택): 수집할 최대 게시글 수. 기본값은 3.
            예시: `3`

    반환값:
        List[CommunityPost]: `CommunityPost` 객체 리스트.
            각 객체는 게시글의 `title` (제목)과 `link` (링크)를 포함합니다.
            예시: `[CommunityPost(title='[삼성전자] 주가는 왜 이러냐...', link='https://finance.naver.com/item/board_read.naver?code=005930&article_id=...'), ...]`
    """
    url = f"https://finance.naver.com/item/board.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    session = await get_session()
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as res:
        res.raise_for_status()
        html = await res.read()
            
    soup = BeautifulSoup(html, "html.parser", from_encoding="euc-kr")
    posts = []
    
    titles = soup.select(".title a")
    for t in titles[:max_items]:
        title_text = t.get("title") or t.get_text(strip=True)
        link = "https://finance.naver.com" + t["href"]
        posts.append(CommunityPost(title=f"[{name}] {title_text}", link=link))
        
    return posts


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_dc_stock_gallery(max_items: int = 5) -> List[CommunityPost]:
    """디시인사이드 주식 갤러리 개념글(추천글) 목록을 수집합니다.

    역할:
        디시인사이드 주식 갤러리(식갤)의 '개념글'(추천글) 목록을 비동기적으로 스크랩합니다.
        이를 통해 주식 투자자들 사이에서 유머와 이슈가 되는 인기 게시글을 파악합니다.

    입력:
        max_items (int, 선택): 수집할 최대 게시글 수. 기본값은 5.
            예시: `5`

    반환값:
        List[CommunityPost]: `CommunityPost` 객체 리스트.
            각 객체는 게시글의 `title` (제목)과 `link` (링크)를 포함합니다.
            예시: `[CommunityPost(title='[식갤] 주식으로 돈 버는 법 정리.txt', link='https://gall.dcinside.com/board/view/?id=neostock&no=...'), ...]`
    """
    url = "https://gall.dcinside.com/board/lists/?id=neostock&exception_mode=recommend"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    session = await get_session()
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as res:
        res.raise_for_status()
        html = await res.text()
            
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    
    rows = soup.select("tr.ub-content.us-post")
    for row in rows:
        title_tag = row.select_one(".gall_tit a:not(.reply_numbox)")
        if title_tag:
            title = title_tag.get_text(strip=True)
            link = "https://gall.dcinside.com" + title_tag["href"]
            posts.append(CommunityPost(title=f"[식갤] {title}", link=link))
            if len(posts) >= max_items:
                break
                
    return posts

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_reddit_wallstreetbets(max_items: int = 5) -> List[CommunityPost]:
    """글로벌 주식 트렌드 및 밈(Meme) 반응 파악을 위해 
    미국 최대 주식 커뮤니티인 Reddit의 WallStreetBets 핫(인기) 게시글을 파싱합니다.

    역할:
        글로벌 주식 시장의 트렌드와 밈(Meme) 반응을 파악하기 위해,
        미국 최대 주식 커뮤니티인 Reddit의 WallStreetBets (WSB) 서브레딧에서
        가장 인기 있는('Hot') 게시글을 비동기적으로 수집합니다.

    입력:
        max_items (int, 선택): 수집할 최대 게시글 수. 기본값은 5.

    반환값:
        List[CommunityPost]: 게시글 리스트. 실패 시 빈 리스트.

    환경변수:
        REDDIT_ENABLED: 'false'로 설정 시 크롤링을 건너뜁니다 (CI/CD용).
    """
    # CI/CD 환경에서 Reddit API가 403을 반환하므로 비활성화 가능 [Fix: production-errors]
    if os.environ.get("REDDIT_ENABLED", "true").lower() == "false":
        global_logger.info("[Reddit] REDDIT_ENABLED=false → 크롤링 건너뜀")
        return []

    url = f"https://www.reddit.com/r/wallstreetbets/hot.json?limit={max_items}"
    headers = {
        "User-Agent": f"stock-report-bot/1.0 (by /u/stock_report_bot)",
        "Accept": "application/json",
    }
    
    posts = []
    try:
        session = await get_session()
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as res:
            if res.status == 200:
                data = await res.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    post = child.get("data", {})
                    title = post.get("title")
                    permalink = post.get("permalink")
                    upvotes = post.get("ups", 0)
                    
                    full_link = f"https://www.reddit.com{permalink}"
                    
                    if title and permalink:
                        posts.append(CommunityPost(title=f"[WSB|추천:{upvotes}] {title}", link=full_link))
            elif res.status == 403:
                global_logger.warning(f"[Reddit] 403 Forbidden - 봇 차단됨 (CI/CD 환경에서는 REDDIT_ENABLED=false 권장)")
            else:
                global_logger.warning(f"[Reddit] HTTP {res.status} - 수집 실패")
    except Exception as e:
        global_logger.warning(f"[Reddit] 크롤링 예외: {e}")
        
    return posts
