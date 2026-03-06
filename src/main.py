"""
주식 리포트 자동화 생성 및 이메일 발송 파이프라인 진입점.

1. 크롤링 데이터를 기반으로 AI 요약을 생성합니다.
2. Notion에서 수신 대상자별 관심 키워드를 조회합니다.
3. 리포트를 HTML로 포매팅하여 대상자들에게 이메일을 발송합니다.
"""

import os
import sys
import re
import traceback
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# 스크립트 실행을 위해 환경변수 및 모듈 경로 로드
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from src.crawlers.naver_news import get_market_news, search_news_by_keyword
from src.crawlers.daum_news import search_daum_news_by_keyword
from src.crawlers.google_news import search_google_news_by_keyword
from src.crawlers.market_index import get_market_indices
from src.crawlers.community import get_naver_board_posts, get_dc_stock_gallery, get_popular_stocks, get_reddit_wallstreetbets
from src.crawlers.google_trends import get_daily_trending_searches
from src.crawlers.naver_datalab import get_naver_datalab_trends
from src.crawlers.article_parser import enrich_news_with_leads
from src.crawlers.http_client import close_session
from src.crawlers.browser_pool import BrowserPool

from src.services.ai_summarizer import (
    generate_market_summary,
    generate_personalized_portfolio_analysis,
    generate_theme_briefing,
    generate_theme_briefings_batch,
)
from src.services.prompt_manager import fetch_prompts_from_notion
from src.services.market_source_governance import (
    evaluate_active_sources,
    get_default_source_policies,
    parse_active_source_ids,
)
from src.services.market_signal_summary import (
    PricePoint,
    build_market_snapshot,
    render_market_snapshot_markdown,
)
from src.utils.report_formatter import build_markdown_report
from src.services.user_manager import fetch_active_users
from src.services.ai_tracker import record_prediction_snapshot
from src.services.feedback_manager import generate_feedback_links_html
from src.services.backtesting_scorer import generate_backtesting_report
from src.utils.cache import crawl_cache
from src.utils.deduplicator import deduplicate_news
from src.utils.sentiment import analyze_sentiment, format_sentiment_section
from src.utils.database import close_db

from src.services.notifier.email import EmailSender
from src.services.notifier.telegram import TelegramSender
from src.services.notifier.queue_worker import global_message_queue, NotificationAction
from src.utils.logger import global_logger, log_critical_error


def _parse_int_env(env_key: str, default_value: int) -> int:
    """정수 환경변수를 안전하게 파싱합니다."""
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return default_value
    try:
        parsed = int(raw)
        return parsed if parsed > 0 else default_value
    except ValueError:
        global_logger.warning(
            f"{env_key} 값이 정수가 아닙니다('{raw}'). 기본값 {default_value}로 대체합니다."
        )
        return default_value


def _is_truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _run_source_governance_check() -> None:
    """활성화된 데이터 소스의 무료 한도/정책 리스크를 점검합니다."""
    default_sources = ["naver_datalab"]
    active_sources = parse_active_source_ids(
        os.getenv("ACTIVE_MARKET_SOURCES"),
        default_source_ids=default_sources,
    )
    if not active_sources:
        global_logger.warning(
            "ACTIVE_MARKET_SOURCES가 비어 있어 소스 정책 검증을 건너뜁니다."
        )
        return

    run_interval_hours = _parse_int_env("PIPELINE_RUN_INTERVAL_HOURS", 3)
    default_calls_per_run = _parse_int_env("SOURCE_DEFAULT_CALLS_PER_RUN", 1)
    strict_mode = _is_truthy(os.getenv("SOURCE_POLICY_STRICT", "false"))

    evaluations = evaluate_active_sources(
        active_sources,
        run_interval_hours=run_interval_hours,
        default_calls_per_run=default_calls_per_run,
    )
    policy_name_map = {
        policy.source_id: policy.name for policy in get_default_source_policies()
    }

    blocking_statuses = {"blocked", "exceed"}
    blocking_evaluations = []
    for result in evaluations:
        source_name = policy_name_map.get(result.source_id, result.source_id)
        limit_text = (
            str(result.free_daily_limit)
            if result.free_daily_limit is not None
            else "N/A"
        )
        message = (
            f"[SourcePolicy] {source_name} ({result.source_id}) "
            f"status={result.status}, daily={result.estimated_daily_calls}, "
            f"limit={limit_text}, reason={result.reason}"
        )
        if result.status in {"ok", "conditional"}:
            global_logger.info(message)
        else:
            global_logger.warning(message)
        if result.status in blocking_statuses:
            blocking_evaluations.append(result)

    if strict_mode and blocking_evaluations:
        blocked_sources = ", ".join(
            sorted({evaluation.source_id for evaluation in blocking_evaluations})
        )
        raise RuntimeError(
            "소스 정책 검증 실패(strict): "
            f"{blocked_sources}. SOURCE_POLICY_STRICT=false 또는 호출 정책을 조정하세요."
        )


def _parse_numeric_value(raw_text: str) -> float | None:
    """문자열에서 첫 번째 숫자 값을 파싱합니다."""
    match = re.search(r"-?\d+(?:\.\d+)?", raw_text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _build_market_snapshot_markdown(
    market_indices,
    market_news,
    community_posts,
    datalab_trends,
) -> str:
    """현재 수집 데이터 기반 정량 스냅샷 마크다운을 생성합니다."""
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    index_series: dict[str, list[PricePoint]] = {}
    for item in market_indices:
        close = _parse_numeric_value(item.value)
        if close is None:
            continue
        index_series[item.name] = [PricePoint(date=snapshot_date, close=close)]

    ratio_values = []
    for trend in datalab_trends or []:
        ratio = _parse_numeric_value(getattr(trend, "traffic", ""))
        if ratio is not None:
            ratio_values.append(ratio)
    avg_trend_ratio = sum(ratio_values) / len(ratio_values) if ratio_values else None

    snapshot = build_market_snapshot(
        index_series=index_series,
        event_counts={
            "market_news": len(market_news or []),
            "community_posts": len(community_posts or []),
        },
        keyword_trend_change_pct=avg_trend_ratio,
    )
    return render_market_snapshot_markdown(snapshot)


async def run_pipeline() -> None:
    """
    역할 (Role):
        주식 리포트 자동화 파이프라인의 핵심 제어 함수(진입점)입니다.
        크롤러를 통해 실시간 시장 데이터(뉴스, 지수, 커뮤니티, 트렌드)를 병렬 수집하고,
        Notion API에서 구독자 목록과 개인 관심/보유 종목을 가져옵니다.
        수집된 데이터는 Gemini(AI)를 거쳐 브리핑/요약 문자열로 가공된 뒤
        각 사용자가 설정한 채널(Email, Telegram 등)로 맞춤형 발송됩니다.

    입력 (Input):
        없음 (None) - 외부 설정(.env), 데이터베이스(Notion) 및 크롤링 결과 데이터를 기반으로 동작합니다.

    반환값 (Output / Returns):
        없음 (None) - 실행 성공 여부는 콘솔 및 log 파일(`logging/` 폴더)에 자동으로 기록됩니다.
    """
    global_logger.info("=== 🚀 주식 리포트 생성 파이프라인 시작 ===")

    # 실행 시작 전 데이터 소스 정책/무료 한도 점검
    _run_source_governance_check()

    # 0. Notion에서 동적 프롬프트 설정 (미리 캐싱) [Task 6.21, REQ-Q07]
    # 동기 함수를 asyncio.to_thread()로 래핑하여 이벤트 루프 블로킹 방지
    await asyncio.to_thread(fetch_prompts_from_notion)
    
    global_message_queue.start_workers() # 워커 스레드 시작
    try:
        # 1. 공통 시황 데이터 수집 (병렬 처리)
        global_logger.info("[1/5] 시장 지수 및 공통 뉴스 수집 중... (비동기 병렬)")
        market_indices, market_news, dc_posts, reddit_posts, datalab_trends = await asyncio.gather(
            get_market_indices(),
            get_market_news(),
            get_dc_stock_gallery(3),
            get_reddit_wallstreetbets(3),
            get_naver_datalab_trends()
        )
        
        # 2. 공통 시황 브리핑 생성
        global_logger.info("[2/5] AI 시장 시황 요약 중...")
        market_summary_md = await generate_market_summary(market_indices, market_news, datalab_trends)
        
        # 3. 사용자 정보 조회 [Task 6.21, REQ-Q07]
        global_logger.info("[3/5] Notion에서 수신 대상자 조회 중...")
        users = await asyncio.to_thread(fetch_active_users)
        
        if not users:
            global_logger.warning("발송할 대상(Active User)이 없어 파이프라인을 종료합니다. (혹은 Notion API Key 설정 누락)")
            return
            
        global_logger.info(f"총 {len(users)}명의 대상자를 확인했습니다.")
        
        # 관심 키워드가 없을 경우를 대비해 기본값으로 커뮤니티 트렌드나 구글 파워검색어 등을 활용할 수 있음
        # 여기서는 디시 식갤 장세 민심 + 글로벌 레딧(WallStreetBets) 밈 요약을 합친 전체 시장 민심 브리핑 추가
        combined_community_posts = dc_posts + reddit_posts
        common_theme_md = await generate_theme_briefing("글로벌 및 국내 시장 민심(식갤+WSB)", market_news[:2], combined_community_posts)

        # 시장 감정 지표 분석 [Task 6.19, REQ-F04]
        sentiment_score, sentiment_label = analyze_sentiment(market_news, combined_community_posts)
        sentiment_md = format_sentiment_section(sentiment_score, sentiment_label)

        # 시장 정량 통계 스냅샷 [P1]
        market_snapshot_md = _build_market_snapshot_markdown(
            market_indices=market_indices,
            market_news=market_news,
            community_posts=combined_community_posts,
            datalab_trends=datalab_trends,
        )

        # 과거 스냅샷 적중률 분석 (PM Task)
        global_logger.info("[+] 과거 AI 예측 백테스팅(Scoring) 분석 중...")
        backtest_report_md = await generate_backtesting_report()

        # 4. 개별 대상자 맞춤형 리포트 발송
        for idx, user in enumerate(users, 1):
            name = user.name
            
            global_logger.info(f"\n[4/5] ({idx}/{len(users)}) '{name}'님 맞춤형 데이터 생성 중...")
            theme_briefings = []
            if backtest_report_md:
                theme_briefings.append(backtest_report_md)
            if market_snapshot_md:
                theme_briefings.append(market_snapshot_md)
            theme_briefings.append(sentiment_md)  # 시장 심리 온도계 [REQ-F04]
            theme_briefings.append(common_theme_md)
            
            # 사용자 키워드 뉴스 완전 병렬 크롤링 + 캐시 [Task 6.2/6.8, REQ-P02/F03]
            # 동일 키워드가 여러 사용자에게 등록된 경우 캐시에서 즉시 반환합니다.
            keywords_to_search = user.keywords[:2]
            global_logger.info(f"      - {keywords_to_search} 키워드 뉴스 수집 중 (캐시 적용)...")
            
            # 캐시 미스/히트 분리 - 캐시에 있는 키워드는 바로 사용, 없는 키워드만 크롤링
            kw_news_results = []
            uncached_keywords = []
            uncached_indices = []
            
            for i, kw in enumerate(keywords_to_search):
                cached = crawl_cache.get(f"keyword_news:{kw}")
                if cached is not None:
                    kw_news_results.append(cached)
                    global_logger.info(f"        🎯 '{kw}' 캐시 적중 - 크롤링 생략")
                else:
                    kw_news_results.append(None)  # placeholder
                    uncached_keywords.append(kw)
                    uncached_indices.append(i)
            
            # 캐시 미스된 키워드만 병렬 크롤링
            if uncached_keywords:
                all_crawl_tasks = []
                for kw in uncached_keywords:
                    all_crawl_tasks.extend([
                        search_news_by_keyword(kw, 3),
                        search_daum_news_by_keyword(kw, 3),
                        search_google_news_by_keyword(kw, 3),
                    ])
                
                all_results = await asyncio.gather(*all_crawl_tasks, return_exceptions=True)
                
                # 결과를 키워드별로 3개씩 그룹핑 + 캐시 저장
                for j, idx in enumerate(uncached_indices):
                    chunk = all_results[j*3:(j+1)*3]
                    flat_news = []
                    for res in chunk:
                        if isinstance(res, list):
                            flat_news.extend(res)
                    news_list = deduplicate_news(flat_news)[:7]  # 중복 제거 후 토큰 초과 방지
                    # 리드 문단 추출로 AI 컨텍스트 품질 향상 [Task 6.10, REQ-F01]
                    news_list = await enrich_news_with_leads(news_list, max_articles=3)
                    kw_news_results[idx] = news_list
                    # 캐시에 저장 (10분 TTL) - 리드 포함
                    crawl_cache.set(f"keyword_news:{uncached_keywords[j]}", news_list)
            
            # 수집된 데이터를 바탕으로 AI 테마 브리핑 요약 (Gemini Batch 1회 호출)
            theme_items = []
            for keyword, kw_news in zip(keywords_to_search, kw_news_results):
                global_logger.info(f"      - '{keyword}' 테마 배치 요약 입력 구성 중...")
                theme_items.append({
                    "keyword": keyword,
                    "keyword_news": kw_news or [],
                    "community_posts": [],
                })
            kw_md_results = await generate_theme_briefings_batch(theme_items)
            theme_briefings.extend(kw_md_results)

            # 5. 초개인화 포트폴리오 분석 추가 (보유 종목이 있는 경우)
            if user.holdings:
                global_logger.info(f"      - '{name}'님 보유 종목({user.holdings}) 기반 초개인화 AI 맞춤 분석 중...")
                portfolio_analysis_md = await generate_personalized_portfolio_analysis(
                    user.holdings, 
                    market_summary_md, 
                    theme_briefings
                )
                # 테마 브리핑 목록 맨 앞에 포트폴리오 분석 결과 삽입 및 스냅샷 DB 보관
                if portfolio_analysis_md:
                    theme_briefings.insert(0, portfolio_analysis_md)
                    record_prediction_snapshot(name, ", ".join(user.holdings), portfolio_analysis_md)

            # 6. 리포트 포매팅 및 메일/메신저 발송
            global_logger.info(f"[5/5] '{name}'님 채널별 알림 전송 중... (등록된 채널: {', '.join(user.channels)})")
            
            # 발송할 알림은 HTML 대신 통합된 순수 Markdown으로 넘기고 채널별(이메일, 텔레그램)로 자체 렌더링하도록 변경
            report_md_content = build_markdown_report(market_summary_md, theme_briefings)
            
            # 사용자 맞춤 피드백 양식 꼬리말 동적 삽입 (별점 1~5 개별 HMAC 서명 링크)
            feedback_links = generate_feedback_links_html(name)
            feedback_footer = f"\n\n---\n💬 오늘 리포트 어떠셨나요?\n\n{feedback_links}\n"
            report_md_content += feedback_footer
            
            subject = f"오늘 하루의 시황 요약 및 맞춤 테마 리포트 - {name}님"
            
            # 팩토리 패턴 대신 전략 적용 (Dictionary Mapping)
            notifiers = {
                "email": EmailSender()
                # "telegram": TelegramSender()  # 텔레그램 발송 기능 제외
            }
            
            for channel in user.channels:
                sender = notifiers.get(channel)
                if sender:
                    action = NotificationAction(sender, user, subject, report_md_content)
                    await global_message_queue.enqueue(action)
                else:
                    global_logger.warning(f"지원하지 않거나 등록되지 않은(비활성화된) 채널입니다: {channel}")
            
        global_logger.info("큐에 대기중인 발송 작업이 모두 끝날 때까지 대기합니다...")
        await global_message_queue.join()
        global_message_queue.stop_workers()
        global_logger.info("\n=== ✨ 모든 파이프라인 실행 완료 ===")
        
    except Exception as e:
        log_critical_error(e, "주식 리포트 파이프라인 메인 실행")
    finally:
        # 파이프라인 종료 시 글로벌 HTTP 세션 및 브라우저 풀 자원 정리 [Task 6.1, 6.4]
        await close_session()
        await BrowserPool.cleanup()
        close_db()

async def main_with_timeout():
    try:
        # 전체 파이프라인(백그라운드 크롤링, AI 요약, 발송 등)이 무한정 대기하는 것을 방지하고자 5분(300초) 타임아웃 설정
        await asyncio.wait_for(run_pipeline(), timeout=300.0)
    except asyncio.TimeoutError:
        global_logger.error("🚨 전역 타임아웃 발생: 파이프라인 실행이 5분을 초과하여 강제 종료되었습니다. (원인: 크롤링 타임아웃 또는 외부 API 응답 지연)")

if __name__ == "__main__":
    asyncio.run(main_with_timeout())
