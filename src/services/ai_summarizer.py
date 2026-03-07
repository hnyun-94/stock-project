"""
AI 요약 서비스 모듈.

Google Gemini API를 활용하여 수집된 뉴스, 커뮤니티, 트렌드, 시장 지수 데이터를
사용자가 읽기 편한 형태의 인사이트 리포트로 요약 및 브리핑합니다.
"""

import os
import json
import asyncio
import time
from typing import Dict, Any, List, Optional, Set
from google import genai
from google.genai.errors import ClientError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception

from src.models import MarketIndex, NewsArticle, CommunityPost, SearchTrend
from src.utils.logger import global_logger
from src.utils.circuit_breaker import async_circuit_breaker
from src.services.prompt_manager import get_cached_prompt
from src.services.prompt_tuner import get_tuning_adjustments, apply_tuning_to_prompt

# 제미나이 API 호출 병목/Rate Limit 15RPM 방지를 위한 Semaphore 및 딜레이
_gemini_sema = asyncio.Semaphore(2)

# Gemini 클라이언트 싱글톤 인스턴스 [Task 6.3, REQ-P03]
# 매번 새 Client 객체를 생성하면 내부 초기화 오버헤드가 발생하므로
# 모듈 레벨에서 한 번만 생성하여 재사용합니다.
_client = None
_model_cache: List[str] = []
_model_cache_at: float = 0.0
_model_cache_ttl = int(os.getenv("GEMINI_MODEL_CACHE_TTL", "600"))
_model_cache_lock = asyncio.Lock()

# Gemini 1.5 계열은 2025-09-24 종료되어 기본 후보에서 제거
# (공식 공지: https://ai.google.dev/gemini-api/docs/models/gemini)
_default_model_candidates = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


class PermanentGeminiError(Exception):
    """재시도로 해결되지 않는 영구 설정/모델 오류."""


def _normalize_model_name(name: str) -> str:
    """모델명을 표준화합니다. (예: models/gemini-2.5-flash -> gemini-2.5-flash)"""
    if not name:
        return ""
    return name.replace("models/", "").strip()


def _dedupe_model_list(models: List[str]) -> List[str]:
    """모델 리스트를 순서 유지하며 중복 제거합니다."""
    deduped: List[str] = []
    seen = set()
    for model in models:
        normalized = _normalize_model_name(model)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _get_model_candidates(requested_model: Optional[str]) -> List[str]:
    """요청/환경/기본 후보를 합쳐 모델 후보 우선순위를 구성합니다."""
    env_model = os.getenv("GEMINI_MODEL", "").strip()
    env_candidates_raw = os.getenv("GEMINI_MODEL_CANDIDATES", "").strip()
    env_candidates = []
    if env_candidates_raw:
        env_candidates = [item.strip() for item in env_candidates_raw.split(",")]

    candidates = []
    if env_model:
        candidates.append(env_model)
    if requested_model:
        candidates.append(requested_model)
    candidates.extend(env_candidates)
    candidates.extend(_default_model_candidates)

    return _dedupe_model_list(candidates)


def _supports_generate_content(model_obj: Any) -> bool:
    """모델이 generateContent 액션을 지원하는지 확인합니다."""
    actions = getattr(model_obj, "supported_actions", None) or []
    lowered = [str(action).lower() for action in actions]
    return "generatecontent" in lowered or "generate_content" in lowered


def _fetch_available_models_sync(client: Any) -> List[str]:
    """Gemini ListModels를 동기 호출해 generateContent 가능 모델 목록을 반환합니다."""
    models: List[str] = []
    pager = client.models.list()
    for model_obj in pager:
        if not _supports_generate_content(model_obj):
            continue
        model_name = _normalize_model_name(getattr(model_obj, "name", ""))
        if model_name:
            models.append(model_name)
    return _dedupe_model_list(models)


async def _get_available_models(force_refresh: bool = False) -> List[str]:
    """사용 가능한 모델 목록을 캐시 기반으로 조회합니다."""
    global _model_cache, _model_cache_at
    now = time.time()

    if (
        not force_refresh
        and _model_cache
        and (now - _model_cache_at) < _model_cache_ttl
    ):
        return _model_cache.copy()

    async with _model_cache_lock:
        now = time.time()
        if (
            not force_refresh
            and _model_cache
            and (now - _model_cache_at) < _model_cache_ttl
        ):
            return _model_cache.copy()

        try:
            client = _get_client()
            available = await asyncio.to_thread(_fetch_available_models_sync, client)
            if available:
                _model_cache = available
                _model_cache_at = time.time()
                return available
            return _model_cache.copy()
        except Exception as e:
            global_logger.warning(
                f"[Gemini] 모델 목록 조회 실패, 후보 기반으로 동작합니다: {e}"
            )
            return _model_cache.copy()


def _pick_runtime_model(
    requested_model: Optional[str],
    available_models: List[str],
    excluded_models: Optional[Set[str]] = None,
) -> str:
    """후보/가용 모델 목록을 바탕으로 실제 호출 모델을 선택합니다."""
    excluded = {_normalize_model_name(name) for name in (excluded_models or set())}
    candidates = _get_model_candidates(requested_model)

    if available_models:
        available_set = {_normalize_model_name(model) for model in available_models}
        for candidate in candidates:
            normalized = _normalize_model_name(candidate)
            if normalized in available_set and normalized not in excluded:
                return normalized

        for available in available_models:
            normalized = _normalize_model_name(available)
            if "flash" in normalized and normalized not in excluded:
                return normalized

        for available in available_models:
            normalized = _normalize_model_name(available)
            if normalized and normalized not in excluded:
                return normalized

    for candidate in candidates:
        normalized = _normalize_model_name(candidate)
        if normalized and normalized not in excluded:
            return normalized

    return _default_model_candidates[0]


def _is_model_not_found_error(error: Exception) -> bool:
    """예외가 모델 미지원/미존재(404)인지 판별합니다."""
    if isinstance(error, ClientError):
        return getattr(error, "code", None) == 404

    message = str(error).lower()
    return "404" in message and "not_found" in message and "model" in message


def _default_requested_model() -> str:
    """환경변수 기반 기본 모델명을 반환합니다."""
    return os.getenv("GEMINI_MODEL", _default_model_candidates[0]).strip()


async def _generate_content_with_model(
    client: Any,
    model: str,
    prompt: str,
    config_kwargs: Dict[str, Any],
) -> Any:
    """단일 모델로 generate_content를 실행합니다."""
    return await asyncio.wait_for(
        client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(**config_kwargs),
        ),
        timeout=90.0,
    )

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

@async_circuit_breaker(failure_threshold=5, recovery_timeout=300, fallback_value=lambda: "⚠️ [Circuit Open] 현재 AI 분석 서버 구간에 장애가 감지되어 요약 텍스트 생성을 건너뛰었습니다.")
@retry(wait=wait_exponential(multiplier=3, min=5, max=30), stop=stop_after_attempt(3),
       retry=retry_if_exception(lambda e: not isinstance(e, PermanentGeminiError)),
       before_sleep=lambda retry_state: global_logger.warning(
           f"🔄 [Gemini] 재시도 {retry_state.attempt_number}/3 - "
           f"{retry_state.outcome.exception().__class__.__name__}: {retry_state.outcome.exception()}"
       ))
async def safe_gemini_call(
    prompt: str,
    model: str = "",
    temperature: float = 0.5,
    response_mime_type: Optional[str] = None
) -> str:
    """Gemini API 호출 시 429 에러 등을 대비한 안전한 래퍼 함수입니다."""
    client = _get_client()
    selected_model = _normalize_model_name(model) or _default_requested_model()
    async with _gemini_sema:
        # Gemini API 호출이 무한정 멈추는 것을 방지하기 위해 90초 타임아웃을 설정합니다.
        # 실제 Gemini 응답은 10~30초이므로 90초면 충분한 여유를 제공합니다. [REQ-Q02]
        try:
            config_kwargs: Dict[str, Any] = {
                "temperature": temperature,
                "safety_settings": [
                    genai.types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    genai.types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    genai.types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    genai.types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                ],
            }
            if response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type

            available_models = await _get_available_models(force_refresh=False)
            selected_model = _pick_runtime_model(model, available_models)

            response = await _generate_content_with_model(
                client,
                selected_model,
                prompt,
                config_kwargs,
            )
        except asyncio.TimeoutError:
            global_logger.error("⏰ [Gemini] API 호출 90초 타임아웃")
            raise
        except Exception as e:
            if _is_model_not_found_error(e):
                global_logger.warning(
                    f"[Gemini] 모델 '{selected_model}' 미지원(404) 감지. "
                    "모델 목록을 새로 조회해 자동 대체를 시도합니다."
                )
                refreshed_models = await _get_available_models(force_refresh=True)
                fallback_model = _pick_runtime_model(
                    model,
                    refreshed_models,
                    excluded_models={selected_model},
                )

                if fallback_model and fallback_model != selected_model:
                    global_logger.warning(
                        f"[Gemini] 모델 대체 적용: {selected_model} -> {fallback_model}"
                    )
                    try:
                        response = await _generate_content_with_model(
                            client,
                            fallback_model,
                            prompt,
                            config_kwargs,
                        )
                    except Exception as fallback_error:
                        global_logger.error(
                            f"❌ [Gemini] 대체 모델 호출 실패: "
                            f"{fallback_error.__class__.__name__}: {fallback_error}"
                        )
                        raise
                else:
                    raise PermanentGeminiError(
                        "사용 가능한 Gemini 모델을 찾지 못했습니다. "
                        "GEMINI_MODEL/GEMINI_MODEL_CANDIDATES 설정을 확인하세요."
                    ) from e
            else:
                global_logger.error(
                    f"❌ [Gemini] API 호출 실패: {e.__class__.__name__}: {e}"
                )
                raise

        await asyncio.sleep(2)  # 분당 요청수 추가 방어
    return response.text or ""

def _load_prompt_template(filename: str) -> str:
    """prompts 폴더에서 프롬프트 템플릿 마크다운 파일을 읽어옵니다."""
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def _build_theme_context(
    keyword_news: List[NewsArticle],
    community_posts: List[CommunityPost]
) -> tuple[str, str]:
    """테마 브리핑 프롬프트용 뉴스/커뮤니티 컨텍스트 문자열을 생성합니다."""
    context_news = "[관련 언론 뉴스]\n"
    for i, news in enumerate(keyword_news[:5], 1):
        context_news += f"{i}. {news.title}\n"
        if news.summary:
            context_news += f"   → {news.summary[:150]}\n"

    context_community = "[관련 커뮤니티 여론 (인기글)]\n"
    for i, post in enumerate(community_posts[:5], 1):
        context_community += f"{i}. {post.title}\n"

    return context_news, context_community


def _append_market_summary_line_limit(prompt: str) -> str:
    """시장 종합 요약 프롬프트에 5줄 출력 제약을 강제합니다."""
    line_limit_instruction = (
        "\n\n[출력 제약]\n"
        "오늘 시장 종합 요약은 반드시 Markdown 기준 총 5줄 이내로 작성하세요.\n"
        "- 제목 1줄 + 본문 최대 4줄만 허용합니다.\n"
        "- 빈 줄, 불필요한 서론/면책 문구를 추가하지 마세요.\n"
    )
    return f"{prompt.rstrip()}{line_limit_instruction}"


def _append_theme_briefing_limit(prompt: str) -> str:
    """테마 브리핑 프롬프트에 짧은 bullet 제약을 강제합니다."""
    line_limit_instruction = (
        "\n\n[출력 제약]\n"
        "반드시 제목 1줄 + bullet 최대 3개로 작성하세요.\n"
        "- bullet은 각각 한 문장만 사용하세요.\n"
        "- 뉴스 핵심, 수급/심리, 투자 시사점 순으로 짧게 정리하세요.\n"
        "- 비속어/민감 표현을 직접 인용하지 말고 '고위험 커뮤니티 표현은 제외됨'처럼 중립적으로 요약하세요.\n"
        "- 장문 문단, 서론, 결론, 면책 문구를 추가하지 마세요.\n"
    )
    return f"{prompt.rstrip()}{line_limit_instruction}"


def _build_batch_theme_prompt(theme_items: List[Dict[str, Any]]) -> str:
    """여러 키워드를 한 번에 분석하기 위한 배치 프롬프트를 생성합니다."""
    prompt_sections = [
        (
            "당신은 트렌드 분석에 능한 주식 애널리스트입니다. "
            "아래 여러 테마를 각각 독립적으로 분석해 주세요."
        ),
        "반드시 JSON만 출력하세요.",
        "출력 스키마:",
        '{"results":[{"keyword":"키워드","briefing_md":"마크다운 브리핑"}]}',
        "각 briefing_md에는 제목(### 🎯 관심 테마 브리핑: <키워드>)을 포함하세요.",
        "각 briefing_md는 제목 1줄 + bullet 최대 3개만 허용합니다.",
        "bullet은 각각 한 문장만 사용하고, 장문 문단과 민감 표현 직접 인용은 금지합니다.",
    ]

    for index, item in enumerate(theme_items, 1):
        keyword = item.get("keyword", "")
        keyword_news = item.get("keyword_news", [])
        community_posts = item.get("community_posts", [])
        context_news, context_community = _build_theme_context(keyword_news, community_posts)
        prompt_sections.extend([
            f"\n[테마 {index}]",
            f"키워드: {keyword}",
            context_news,
            context_community,
        ])

    return "\n".join(prompt_sections)


def _parse_batch_theme_response(response_text: str, expected_count: int) -> List[Optional[str]]:
    """Gemini JSON 응답에서 키워드별 브리핑을 순서대로 추출합니다."""
    briefings: List[Optional[str]] = [None] * expected_count
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        global_logger.warning("배치 테마 브리핑 JSON 파싱 실패: fallback 모드로 전환합니다.")
        return briefings

    if isinstance(payload, dict):
        raw_results = payload.get("results", [])
    elif isinstance(payload, list):
        raw_results = payload
    else:
        raw_results = []

    if not isinstance(raw_results, list):
        return briefings

    for idx, item in enumerate(raw_results[:expected_count]):
        if isinstance(item, dict):
            md_text = item.get("briefing_md")
        elif isinstance(item, str):
            md_text = item
        else:
            md_text = None

        if isinstance(md_text, str) and md_text.strip():
            briefings[idx] = md_text.strip()

    return briefings


def _build_holding_news_context(
    holdings: List[str],
    holding_news_map: Dict[str, List[NewsArticle]],
) -> str:
    """보유 종목별 뉴스 컨텍스트 문자열을 생성합니다."""
    sections: List[str] = []
    for holding in holdings:
        sections.append(f"[보유 종목: {holding}]")
        news_list = holding_news_map.get(holding, [])
        if not news_list:
            sections.append("- 관련 뉴스 부족")
            continue
        for index, news in enumerate(news_list[:3], 1):
            sections.append(f"{index}. {news.title}")
            if news.summary:
                sections.append(f"   → {news.summary[:120]}")
    return "\n".join(sections)


def _fallback_holding_insights(
    holdings: List[str],
    holding_news_map: Dict[str, List[NewsArticle]],
) -> List[Dict[str, str]]:
    """JSON 파싱 실패 시 종목별 보수적 기본 인사이트를 생성합니다."""
    positive_keywords = ("상승", "반등", "실적", "수주", "강세", "기대", "확대")
    negative_keywords = ("하락", "급락", "우려", "소송", "악재", "부진", "감소")
    insights: List[Dict[str, str]] = []

    for holding in holdings:
        news_titles = [news.title for news in holding_news_map.get(holding, [])[:2]]
        score = 0
        for title in news_titles:
            score += sum(1 for keyword in positive_keywords if keyword in title)
            score -= sum(1 for keyword in negative_keywords if keyword in title)

        stance = "관찰"
        if score >= 2:
            stance = "유지"
        elif score <= -1:
            stance = "경계"

        summary = news_titles[0] if news_titles else "직접 연계 뉴스가 적어 추가 확인이 필요합니다."
        action = "실적/수급 일정 확인"
        if stance == "유지":
            action = "강한 모멘텀 유지 여부 점검"
        elif stance == "경계":
            action = "단기 변동성 확대 여부 점검"

        insights.append(
            {
                "holding": holding,
                "stance": stance,
                "summary": summary,
                "action": action,
            }
        )
    return insights


def _parse_holding_insights_response(
    response_text: str,
    holdings: List[str],
    holding_news_map: Dict[str, List[NewsArticle]],
) -> List[Dict[str, str]]:
    """Gemini JSON 응답에서 보유 종목별 인사이트를 추출합니다."""
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return _fallback_holding_insights(holdings, holding_news_map)

    raw_items = []
    if isinstance(payload, dict):
        raw_items = payload.get("insights", [])
    elif isinstance(payload, list):
        raw_items = payload

    parsed_items: List[Dict[str, str]] = []
    seen_holdings: Set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        holding = str(item.get("holding") or item.get("symbol") or "").strip()
        if not holding or holding in seen_holdings or holding not in holdings:
            continue
        parsed_items.append(
            {
                "holding": holding,
                "stance": str(item.get("stance") or "관찰").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "action": str(item.get("action") or "추가 확인").strip(),
            }
        )
        seen_holdings.add(holding)

    if len(parsed_items) != len(holdings):
        fallback_map = {
            item["holding"]: item
            for item in _fallback_holding_insights(holdings, holding_news_map)
        }
        merged_items = []
        parsed_map = {item["holding"]: item for item in parsed_items}
        for holding in holdings:
            merged_items.append(parsed_map.get(holding) or fallback_map[holding])
        return merged_items

    return parsed_items

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
            model = prompt_data.get("model", _default_requested_model())
            temperature = prompt_data.get("temperature", 0.5)
        else:
            # 실패하거나 아예 등록이 안 되어 있으면 로컬 Fallback 텍스트 마크다운 사용
            template = _load_prompt_template("market_summary.md")
            prompt = template.format(
                context_indices=context_indices,
                context_news=context_news,
                context_trends=context_trends
            )
            model = _default_requested_model()
            temperature = 0.5

        # 피드백 기반 자동 프롬프트 튜닝 [REQ-F06]
        adjustments = get_tuning_adjustments()
        prompt = apply_tuning_to_prompt(prompt, adjustments)
        prompt = _append_market_summary_line_limit(prompt)
        temperature = max(0.1, min(1.0, temperature + adjustments["temperature_delta"]))

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
        context_news, context_community = _build_theme_context(keyword_news, community_posts)
            
        prompt_data = get_cached_prompt("theme_briefing", keyword=keyword, context_news=context_news, context_community=context_community)
        
        if prompt_data:
            prompt = prompt_data["content"]
            model = prompt_data.get("model", _default_requested_model())
            temperature = prompt_data.get("temperature", 0.5)
        else:
            template = _load_prompt_template("theme_briefing.md")
            prompt = template.format(
                keyword=keyword,
                context_news=context_news,
                context_community=context_community
            )
            model = _default_requested_model()
            temperature = 0.5

        prompt = _append_theme_briefing_limit(prompt)
        response_text = await safe_gemini_call(prompt, model=model, temperature=temperature)
        return response_text
        
    except Exception as e:
        global_logger.error(f"테마 브리핑 생성 중 오류 발생: {e}")
        return f"테마 브리핑 생성 실패 ({keyword}): {str(e)}"


async def generate_theme_briefings_batch(theme_items: List[Dict[str, Any]]) -> List[str]:
    """여러 키워드 테마 브리핑을 한 번의 Gemini 호출로 생성합니다.

    Args:
        theme_items (List[Dict[str, Any]]): 키워드별 컨텍스트 목록.
            각 항목은 `keyword`, `keyword_news`, `community_posts`를 포함합니다.

    Returns:
        List[str]: 입력 순서와 동일한 마크다운 브리핑 리스트.
    """
    if not theme_items:
        return []

    keywords = [item.get("keyword", "") for item in theme_items]
    results = [""] * len(theme_items)
    missing_indices: List[int] = []

    try:
        batch_prompt = _build_batch_theme_prompt(theme_items)
        response_text = await safe_gemini_call(
            batch_prompt,
            model=_default_requested_model(),
            temperature=0.5,
            response_mime_type="application/json"
        )
        parsed_briefings = _parse_batch_theme_response(response_text, len(theme_items))

        for idx, briefing in enumerate(parsed_briefings):
            if briefing:
                results[idx] = briefing
            else:
                missing_indices.append(idx)

    except Exception as e:
        global_logger.error(f"배치 테마 브리핑 생성 중 오류 발생: {e}")
        missing_indices = list(range(len(theme_items)))

    if not missing_indices:
        return results

    global_logger.warning(
        f"배치 브리핑 응답 누락 {len(missing_indices)}건 감지, 개별 호출 fallback 수행"
    )
    fallback_tasks = []
    for idx in missing_indices:
        fallback_tasks.append(
            generate_theme_briefing(
                keywords[idx],
                theme_items[idx].get("keyword_news", []),
                theme_items[idx].get("community_posts", []),
            )
        )

    fallback_results = await asyncio.gather(*fallback_tasks)
    for idx, fallback in zip(missing_indices, fallback_results):
        results[idx] = fallback

    return results

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
            model = prompt_data.get("model", _default_requested_model())
            temperature = prompt_data.get("temperature", 0.5)
        else:
            template = _load_prompt_template("portfolio_analysis.md")
            prompt = template.format(
                holdings=joined_holdings,
                market_summary=market_summary,
                theme_briefings=joined_theme_briefings
            )
            model = _default_requested_model()
            temperature = 0.5

        response_text = await safe_gemini_call(prompt, model=model, temperature=temperature)
        return response_text
        
    except Exception as e:
        global_logger.error(f"초개인화 포트폴리오 분석 생성 중 오류 발생: {e}")
        return f"포트폴리오 맞춤 분석 생성 실패: {str(e)}"


async def generate_holding_insights(
    holdings: List[str],
    market_summary: str,
    theme_briefings: List[str],
    holding_news_map: Dict[str, List[NewsArticle]],
) -> List[Dict[str, str]]:
    """보유 종목별 개별 인사이트를 JSON 구조로 생성합니다."""
    if not holdings:
        return []

    compact_theme_briefings = "\n".join(theme_briefings[:3])
    news_context = _build_holding_news_context(holdings, holding_news_map)
    prompt = f"""
당신은 리스크 관리에 강한 프라이빗 뱅커입니다.
아래 시장 요약, 테마 요약, 보유 종목별 뉴스를 읽고 종목별 인사이트를 작성하세요.

반드시 JSON만 출력하세요.
출력 스키마:
{{
  "insights": [
    {{
      "holding": "종목명",
      "stance": "유지|확대검토|관찰|경계",
      "summary": "90자 이내 근거 요약",
      "action": "한 줄 대응 전략"
    }}
  ]
}}

규칙:
- holdings 순서를 유지하세요.
- 각 종목당 객체는 정확히 1개만 생성하세요.
- 장문 문단, 과장된 확신, 면책 문구는 금지합니다.
- summary와 action은 각각 한 문장으로 짧게 작성하세요.

[오늘 시장 요약]
{market_summary}

[주요 테마 요약]
{compact_theme_briefings}

[보유 종목별 뉴스]
{news_context}
""".strip()

    try:
        response_text = await safe_gemini_call(
            prompt,
            model=_default_requested_model(),
            temperature=0.3,
            response_mime_type="application/json",
        )
        return _parse_holding_insights_response(response_text, holdings, holding_news_map)
    except Exception as e:
        global_logger.error(f"보유 종목별 인사이트 생성 중 오류 발생: {e}")
        return _fallback_holding_insights(holdings, holding_news_map)
