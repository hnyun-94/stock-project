"""
네이버 데이터랩(DataLab) API 연동 크롤러.

구글 트렌드와 별개로, 지정된 핵심 키워드(코스피, 코스닥 등)의 
네이버 검색 추이(트렌드)를 가져와 국내 투자자 관심도를 파악합니다.
"""

import os
from typing import List, Dict
import aiohttp
from datetime import datetime, timedelta
from tenacity import retry, wait_exponential, stop_after_attempt

from src.models import SearchTrend
from src.utils.logger import global_logger

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def get_naver_datalab_trends(keywords: List[str] = None) -> List[SearchTrend]:
    """네이버 데이터랩 통합 검색어 트렌드 API를 호출하여 결과를 반환합니다.

    Args:
        keywords (List[str], optional): 트렌드를 조회할 키워드 목록.

    Returns:
        List[SearchTrend]: 최근 통합 검색 비율 정보 DTO 리스트
    """
    if keywords is None:
        keywords = ["코스피", "코스닥", "증시", "환율", "금리"]
        
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        global_logger.warning("네이버 개발자 API 설정(NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)이 누락되었습니다. 빈 데이터랩 트렌드를 반환합니다.")
        return []
        
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json"
    }
    
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    # 네이버 API 스펙에 맞는 Body 구성
    keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords]
    body = {
        "startDate": yesterday.strftime("%Y-%m-%d"),
        "endDate": today.strftime("%Y-%m-%d"),
        "timeUnit": "date",
        "keywordGroups": keyword_groups
    }
    
    trends = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=10) as response:
                if response.status != 200:
                    error_text = await response.text()
                    global_logger.error(f"데이터랩 API 호출 실패: HTTP {response.status} - {error_text}")
                    return []
                    
                data = await response.json()
                
        results = data.get("results", [])
        for res in results:
            group_name = res.get("title")
            data_points = res.get("data", [])
            # 가장 최근(마지막) 날짜의 검색 비율(ratio) 추출
            if data_points:
                latest_ratio = data_points[-1].get("ratio", 0)
                trends.append(SearchTrend(
                    keyword=f"{group_name} (네이버)",
                    traffic=f"지표: {latest_ratio}",
                    news_link=""
                ))
                
    except Exception as e:
        global_logger.error(f"네이버 데이터랩 수집 중 예외 발생: {e}")
        raise e
        
    return trends
