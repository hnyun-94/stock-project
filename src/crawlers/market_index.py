"""
국내 주식 시장 지수 및 동향 크롤러 모듈.

코스피(KOSPI), 코스닥(KOSDAQ)의 현재 지수와
투자자별 매매동향(개인/외국인/기관)을 수집하여 시장의 전반적인 분위기를 파악합니다.
"""

from typing import List, Dict, Any
import aiohttp
from src.crawlers.http_client import get_session
from bs4 import BeautifulSoup
import traceback

from src.models import MarketIndex
from src.utils.logger import global_logger
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_market_indices() -> List[MarketIndex]:
    """네이버 금융 홈에서 코스피, 코스닥 지수 및 투자자 매매동향을 수집합니다.

    역할:
        네이버 금융 웹사이트(finance.naver.com)에서 KOSPI 및 KOSDAQ의 현재 지수와
        투자자(개인, 외국인, 기관)별 매매동향 데이터를 비동기적으로 스크랩합니다.
        추가적으로, 네이버 금융 시장지표 페이지에서 주요 매크로 지표(미국 USD, WTI 유가, 국제 금)를 수집하여
        시장 전반의 흐름을 파악할 수 있는 정보를 제공합니다. 수집된 정보는 MarketIndex 객체 리스트 형태로 반환됩니다.

    입력:
        없음 (이 함수는 어떠한 인자도 받지 않습니다).

    반환값:
        List[MarketIndex]:
            현재 KOSPI 및 KOSDAQ 지수와 해당 시장의 투자자별 매매동향 요약 정보,
            그리고 주요 매크로 지표(환율, 유가, 금)를 담은 MarketIndex 객체들의 리스트입니다.
            각 MarketIndex 객체는 'name', 'value', 'change', 'investor_summary' 필드를 가집니다.
            'change' 필드는 현재 구현상 빈 문자열("")로 설정됩니다.

            예시:
            [
                MarketIndex(name='KOSPI', value='3,000.00', change='', investor_summary='개인: 1000억, 외국인: -500억, 기관: -500억'),
                MarketIndex(name='KOSDAQ', value='1,000.00', change='', investor_summary='개인: -500억, 외국인: 300억, 기관: 200억'),
                MarketIndex(name='미국 USD', value='1,350.50', change='', investor_summary='매크로 지표'),
                MarketIndex(name='WTI', value='80.25', change='', investor_summary='매크로 지표'),
                MarketIndex(name='국제 금', value='2,050.10', change='', investor_summary='매크로 지표')
            ]
    """
    market_list = []
    
    try:
        url = "https://finance.naver.com/"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        session = await get_session()
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status()
            html = await response.text(encoding='euc-kr')
                
        soup = BeautifulSoup(html, "html.parser")
        
        # KOSPI 수집
        kospi_area = soup.select_one(".kospi_area")
        if kospi_area:
            value = kospi_area.select_one(".num_quot .num").get_text(strip=True) if kospi_area.select_one(".num_quot .num") else "0"
            inv_dict = {}
            dl_tag = kospi_area.select_one("dl")
            if dl_tag:
                for dt, dd in zip(dl_tag.find_all("dt"), dl_tag.find_all("dd")):
                    inv_dict[dt.get_text(strip=True)] = dd.get_text(strip=True)
            inv_str = ", ".join([f"{k}: {v}" for k, v in inv_dict.items()])
            
            market_list.append(MarketIndex(name="KOSPI", value=value, change="", investor_summary=inv_str))
        
        # KOSDAQ 수집
        kosdaq_area = soup.select_one(".kosdaq_area")
        if kosdaq_area:
            value = kosdaq_area.select_one(".num_quot .num").get_text(strip=True) if kosdaq_area.select_one(".num_quot .num") else "0"
            inv_dict = {}
            dl_tag = kosdaq_area.select_one("dl")
            if dl_tag:
                for dt, dd in zip(dl_tag.find_all("dt"), dl_tag.find_all("dd")):
                    inv_dict[dt.get_text(strip=True)] = dd.get_text(strip=True)
            inv_str = ", ".join([f"{k}: {v}" for k, v in inv_dict.items()])
            
            market_list.append(MarketIndex(name="KOSDAQ", value=value, change="", investor_summary=inv_str))
            
        # 환율 (USD), 국제 금, WTI 유가 등 매크로 지표 추가
        try:
            market_url = "https://finance.naver.com/marketindex/"
            m_session = await get_session()
            async with m_session.get(market_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as m_res:
                m_res.raise_for_status()
                m_html = await m_res.text(encoding='euc-kr')
            m_soup = BeautifulSoup(m_html, "html.parser")
            
            # 시장 지표를 담은 박스들 (h_lst: 종목명, value: 값)
            for h3, v in zip(m_soup.select('.market1 h3.h_lst, .market2 h3.h_lst, .market3 h3.h_lst, .market4 h3.h_lst'), 
                             m_soup.select('.market1 span.value, .market2 span.value, .market3 span.value, .market4 span.value')):
                
                name = h3.get_text(strip=True)
                val = v.get_text(strip=True)
                
                # 주요 지표들만 선별해서 리포트에 포함
                if name in ["미국 USD", "WTI", "국제 금"]:
                    market_list.append(MarketIndex(name=name, value=val, change="", investor_summary="매크로 지표"))
                    
        except Exception as filter_err:
            global_logger.error(f"매크로 지표(환율/유가/금)를 가져오는 데 실패했습니다: {filter_err}")
            
    except Exception as e:
        global_logger.error(f"시장 지수 수집 실패: {e}")
        traceback.print_exc()

    return market_list
