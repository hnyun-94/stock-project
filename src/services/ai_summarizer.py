"""
AI 요약 서비스 모듈.

Google Gemini API를 활용하여 수집된 뉴스, 커뮤니티, 트렌드, 시장 지수 데이터를
사용자가 읽기 편한 형태의 인사이트 리포트로 요약 및 브리핑합니다.
"""

import os
import asyncio
from typing import Dict, Any, List
from google import genai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from src.models import MarketIndex, NewsArticle, CommunityPost, SearchTrend
from src.utils.logger import global_logger
from src.utils.circuit_breaker import async_circuit_breaker
from src.services.prompt_manager import get_cached_prompt

# 제미나이 API 호출 병목/Rate Limit 15RPM 방지를 위한 Semaphore 및 딜레이
_gemini_sema = asyncio.Semaphore(2)

# Gemini 클라이언트 싱글톤 인스턴스 [Task 6.3, REQ-P03]
# 매번 새 Client 객체를 생성하면 내부 초기화 오버헤드가 발생하므로
# 모듈 레벨에서 한 번만 생성하여 재사용합니다.
_client = None

def _get_client():
    """Gemini 클라이언트 싱글톤 인스턴스를 반환합니다.
    
    최초 호출 시 Client 객체를 생성하고, 이후에는 동일 인스턴스를 재사용합니다.
    GEMINI_API_KEY 환경변수가 설정되어 있어야 합니다.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되어 있지 않습니다.")
        _client = genai.Client(api_key=api_key)
    return _client

@async_circuit_breaker(failure_threshold=2, recovery_timeout=120, fallback_value=lambda: "⚠️ [Circuit Open] 현재 AI 분석 서버 구간에 장애가 감지되어 요약 텍스트 생성을 건너뛰었습니다.")
@retry(wait=wait_exponential(multiplier=5, min=10, max=60), stop=stop_after_attempt(5))
async def safe_gemini_call(prompt: str, model: str = 'gemini-1.5-flash', temperature: float = 0.5) -> str:
    """Gemini API 호출 시 429 에러 등을 대비한 안전한 래퍼 함수입니다."""
    client = _get_client()
    async with _gemini_sema:
        # Gemini API 호출이 무한정 멈추는 것을 방지하기 위해 90초 타임아웃을 설정합니다.
        # 실제 Gemini 응답은 10~30초이므로 90초면 충분한 여유를 제공합니다. [REQ-Q02]
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=temperature,
                    safety_settings=[
                        genai.types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                        genai.types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                        genai.types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                        genai.types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    ]
                )
            ),
            timeout=90.0
        )
        await asyncio.sleep(2)  # 분당 요청수 추가 방어
    return response.text

def _load_prompt_template(filename: str) -> str:
    """prompts 폴더에서 프롬프트 템플릿 마크다운 파일을 읽어옵니다."""
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

async def generate_market_summary(market_indices: List[MarketIndex], market_news: List[NewsArticle], datalab_trends: List[SearchTrend] = None) -> str:
    """오늘의 주요 시황 데이터와 뉴스를 입력받아 시장 종합 요약을 생성합니다.

    Args:
        market_indices (List[MarketIndex]): KOSPI, KOSDAQ 수치 및 매매동향 DTO 리스트
        market_news (List[NewsArticle]): 언론사별 주요 시황 뉴스 헤드라인 DTO 리스트
        datalab_trends (List[SearchTrend]): 네이버 데이터랩 검색 트렌드 DTO 리스트 (선택사항)

    Returns:
        str: 마크다운 형식의 시장 요약 리포트 텍스트
    """
    try:
        # 프롬프트 구성
        context_indices = "[국내 시장 지표]\n"
        for m_idx in market_indices:
            context_indices += f"- {m_idx.name}: {m_idx.value} ({m_idx.investor_summary})\n"
            
        context_news = "[주요 시장 뉴스]\n"
        for i, news in enumerate(market_news[:10], 1):
            context_news += f"{i}. {news.title}\n"
            if news.summary:
                context_news += f"   → {news.summary[:150]}\n"
            
        context_trends = ""
        if datalab_trends:
            context_trends = "[주요 검색 트렌드 지표]\n"
            for tr in datalab_trends:
                context_trends += f"- {tr.keyword}: {tr.traffic}\n"
                
        # 먼저 Notion에서 동적으로 관리되는 프롬프트를 시도
        prompt_data = get_cached_prompt("market_summary", context_indices=context_indices, context_news=context_news, context_trends=context_trends)
        
        if prompt_data:
            prompt = prompt_data["content"]
            model = prompt_data.get("model", "gemini-1.5-flash")
            temperature = prompt_data.get("temperature", 0.5)
        else:
            # 실패하거나 아예 등록이 안 되어 있으면 로컬 Fallback 텍스트 마크다운 사용
            template = _load_prompt_template("market_summary.md")
            prompt = template.format(
                context_indices=context_indices,
                context_news=context_news,
                context_trends=context_trends
            )
            model = "gemini-1.5-flash"
            temperature = 0.5
        
        response_text = await safe_gemini_call(prompt, model=model, temperature=temperature)
        return response_text
        
    except Exception as e:
        global_logger.error(f"시장 요약 생성 중 오류 발생: {e}")
        return f"시장 요약 생성 실패: {str(e)}"

async def generate_theme_briefing(keyword: str, keyword_news: List[NewsArticle], community_posts: List[CommunityPost]) -> str:
    """사용자의 관심 테마(키워드)에 대한 뉴스와 커뮤니티 여론을 종합하여 브리핑합니다.

    Args:
        keyword (str): 관심 테마 키워드
        keyword_news (List[NewsArticle]): 테마 관련 주요 뉴스 DTO 리스트
        community_posts (List[CommunityPost]): 종토방 및 디시 식갤 인기글 등 커뮤니티 데이터 DTO 리스트

    Returns:
        str: 마크다운 형식의 테마 브리핑 리포트 텍스트
    """
    try:
        context_news = "[관련 언론 뉴스]\n"
        for i, news in enumerate(keyword_news[:5], 1):
            context_news += f"{i}. {news.title}\n"
            if news.summary:
                context_news += f"   → {news.summary[:150]}\n"

        context_community = "[관련 커뮤니티 여론 (인기글)]\n"
        for i, post in enumerate(community_posts[:5], 1):
            context_community += f"{i}. {post.title}\n"
            
        prompt_data = get_cached_prompt("theme_briefing", keyword=keyword, context_news=context_news, context_community=context_community)
        
        if prompt_data:
            prompt = prompt_data["content"]
            model = prompt_data.get("model", "gemini-1.5-flash")
            temperature = prompt_data.get("temperature", 0.5)
        else:
            template = _load_prompt_template("theme_briefing.md")
            prompt = template.format(
                keyword=keyword,
                context_news=context_news,
                context_community=context_community
            )
            model = "gemini-1.5-flash"
            temperature = 0.5

        response_text = await safe_gemini_call(prompt, model=model, temperature=temperature)
        return response_text
        
    except Exception as e:
        global_logger.error(f"테마 브리핑 생성 중 오류 발생: {e}")
        return f"테마 브리핑 생성 실패 ({keyword}): {str(e)}"

async def generate_personalized_portfolio_analysis(holdings: List[str], market_summary: str, theme_briefings: List[str]) -> str:
    """사용자의 보유 종목을 바탕으로 오늘 시장이 미칠 영향을 개인화하여 분석합니다.

    Args:
        holdings (List[str]): 사용자의 보유 종목 리스트
        market_summary (str): 기존에 생성된 전체 시장 시황 요약
        theme_briefings (List[str]): 기존에 생성된 테마별 브리핑 내용

    Returns:
        str: 초개인화 포트폴리오 분석 결과 브리핑 (Markdown)
    """
    if not holdings:
        return ""
        
    try:
        joined_holdings = ", ".join(holdings)
        joined_theme_briefings = chr(10).join(theme_briefings)
        
        prompt_data = get_cached_prompt("portfolio_analysis", holdings=joined_holdings, market_summary=market_summary, theme_briefings=joined_theme_briefings)
        
        if prompt_data:
            prompt = prompt_data["content"]
            model = prompt_data.get("model", "gemini-1.5-flash")
            temperature = prompt_data.get("temperature", 0.5)
        else:
            template = _load_prompt_template("portfolio_analysis.md")
            prompt = template.format(
                holdings=joined_holdings,
                market_summary=market_summary,
                theme_briefings=joined_theme_briefings
            )
            model = "gemini-1.5-flash"
            temperature = 0.5

        response_text = await safe_gemini_call(prompt, model=model, temperature=temperature)
        return response_text
        
    except Exception as e:
        global_logger.error(f"초개인화 포트폴리오 분석 생성 중 오류 발생: {e}")
        return f"포트폴리오 맞춤 분석 생성 실패: {str(e)}"
