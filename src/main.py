"""
주식 리포트 자동화 생성 및 이메일 발송 파이프라인 진입점.

1. 크롤링 데이터를 기반으로 AI 요약을 생성합니다.
2. Notion에서 수신 대상자별 관심 키워드를 조회합니다.
3. 리포트를 HTML로 포매팅하여 대상자들에게 이메일을 발송합니다.
"""

import os
import sys
import json
import traceback
import asyncio
from dotenv import load_dotenv

# 스크립트 실행을 위해 환경변수 및 모듈 경로 로드
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from src.crawlers.naver_news import get_market_news
from src.crawlers.market_index import get_market_indices
from src.crawlers.community import get_dc_stock_gallery, get_reddit_wallstreetbets
from src.crawlers.naver_datalab import get_naver_datalab_trends
from src.crawlers.http_client import close_session
from src.crawlers.browser_pool import BrowserPool

from src.services.ai_summarizer import (
    generate_market_summary,
    generate_theme_briefing,
    generate_theme_briefings_batch,
    generate_holding_insights,
)
from src.services.prompt_manager import fetch_prompts_from_notion
from src.services.community_safety import (
    filter_community_posts_by_source,
    flatten_safe_community_posts,
)
from src.services.market_source_governance import (
    evaluate_active_sources,
    get_default_source_policies,
    parse_active_source_ids,
)
from src.services.market_external_connectors import (
    collect_external_source_snapshot,
)
from src.services.report_builder import build_report_payload
from src.services.topic_news import collect_topic_news
from src.utils.report_formatter import build_structured_markdown_report
from src.services.user_manager import fetch_active_users
from src.services.ai_tracker import record_prediction_snapshot
from src.services.feedback_manager import generate_feedback_links_html
from src.utils.sentiment import analyze_sentiment
from src.utils.database import close_db, get_db

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

        # 커뮤니티 안전 필터 적용
        community_filter_results = filter_community_posts_by_source(
            {
                "dc_stock_gallery": dc_posts,
                "reddit_wallstreetbets": reddit_posts,
            },
            max_items_per_source=3,
        )
        for source_id, result in community_filter_results.items():
            global_logger.info(
                "[CommunitySafety] %s input=%s kept=%s filtered=%s skipped=%s reason=%s",
                source_id,
                result.input_count,
                len(result.kept_posts),
                result.filtered_count,
                result.skipped,
                result.reason or "ok",
            )
        safe_community_posts = flatten_safe_community_posts(
            community_filter_results,
            max_items=4,
        )

        # 3. 사용자 정보 조회 [Task 6.21, REQ-Q07]
        global_logger.info("[3/5] Notion에서 수신 대상자 조회 중...")
        users = await asyncio.to_thread(fetch_active_users)
        
        if not users:
            global_logger.warning("발송할 대상(Active User)이 없어 파이프라인을 종료합니다. (혹은 Notion API Key 설정 누락)")
            return
            
        global_logger.info(f"총 {len(users)}명의 대상자를 확인했습니다.")
        
        common_theme_md = ""
        if safe_community_posts:
            common_theme_md = await generate_theme_briefing(
                "글로벌 및 국내 시장 민심",
                market_news[:2],
                safe_community_posts,
            )

        # 시장 감정 지표 분석 [Task 6.19, REQ-F04]
        sentiment_score, sentiment_label = analyze_sentiment(
            market_news,
            safe_community_posts,
        )

        # 외부 무료 소스 커넥터 지표 수집 + 텔레메트리 (옵션)
        _, _ = (
            await collect_external_source_snapshot()
        )

        db = get_db()
        connector_success_rate_7d = db.get_connector_success_rate(days=7)
        connector_success_rate_30d = db.get_connector_success_rate(days=30)
        avg_feedback_score_30d = db.get_average_score(days=30)
        avg_accuracy_30d = db.get_average_accuracy(days=30)

        # 4. 개별 대상자 맞춤형 리포트 발송
        for idx, user in enumerate(users, 1):
            name = user.name
            
            global_logger.info(f"\n[4/5] ({idx}/{len(users)}) '{name}'님 맞춤형 데이터 생성 중...")
            keywords_to_search = user.keywords[:2]
            holdings_to_analyze = user.holdings[:4]
            search_topics = list(dict.fromkeys(keywords_to_search + holdings_to_analyze))
            global_logger.info(
                f"      - 토픽 뉴스 수집 중 (키워드 {keywords_to_search}, 보유종목 {holdings_to_analyze})..."
            )
            topic_news_map = await collect_topic_news(
                search_topics,
                cache_prefix="topic_news",
            )

            # 수집된 데이터를 바탕으로 AI 테마 브리핑 요약 (Gemini Batch 1회 호출)
            theme_items = []
            for keyword in keywords_to_search:
                global_logger.info(f"      - '{keyword}' 테마 배치 요약 입력 구성 중...")
                theme_items.append(
                    {
                        "keyword": keyword,
                        "keyword_news": topic_news_map.get(keyword, []),
                        "community_posts": [],
                    }
                )
            kw_md_results = await generate_theme_briefings_batch(theme_items)
            theme_sections = []
            if common_theme_md:
                theme_sections.append(
                    {"keyword": "시장 민심", "briefing_md": common_theme_md}
                )
            for keyword, md_text in zip(keywords_to_search, kw_md_results):
                theme_sections.append({"keyword": keyword, "briefing_md": md_text})

            holding_news_map = {
                holding: topic_news_map.get(holding, [])
                for holding in holdings_to_analyze
            }
            holding_insights = []
            if holdings_to_analyze:
                global_logger.info(
                    f"      - '{name}'님 보유 종목({holdings_to_analyze}) 기반 개별 인사이트 생성 중..."
                )
                holding_insights = await generate_holding_insights(
                    holdings_to_analyze,
                    market_summary_md,
                    [section["briefing_md"] for section in theme_sections],
                    holding_news_map,
                )

            recent_report_rows = db.get_recent_report_snapshots(name, limit=2)
            weekly_report_rows = db.get_report_snapshots_since(name, days=7)
            monthly_report_rows = db.get_report_snapshots_since(name, days=30)

            report_payload, report_snapshot = build_report_payload(
                user_name=name,
                market_summary_md=market_summary_md,
                market_indices=market_indices,
                market_news=market_news,
                datalab_trends=datalab_trends or [],
                theme_sections=theme_sections,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                holding_insights=holding_insights,
                recent_report_rows=recent_report_rows,
                weekly_report_rows=weekly_report_rows,
                monthly_report_rows=monthly_report_rows,
                connector_success_rate_7d=connector_success_rate_7d,
                connector_success_rate_30d=connector_success_rate_30d,
                avg_feedback_score_30d=avg_feedback_score_30d,
                avg_accuracy_30d=avg_accuracy_30d,
            )

            # 6. 리포트 포매팅 및 메일/메신저 발송
            global_logger.info(f"[5/5] '{name}'님 채널별 알림 전송 중... (등록된 채널: {', '.join(user.channels)})")
            
            report_md_content = build_structured_markdown_report(report_payload)
            db.insert_report_snapshot(
                user_name=name,
                headline=(report_payload.get("headline_changes") or [""])[0],
                snapshot_json=json.dumps(report_snapshot, ensure_ascii=False),
                report_text=report_md_content,
            )

            if holding_insights:
                snapshot_text = "\n".join(
                    f"{item['holding']}: {item['stance']} | {item['summary']} | {item['action']}"
                    for item in holding_insights
                )
                record_prediction_snapshot(
                    name,
                    ", ".join(holdings_to_analyze),
                    snapshot_text,
                )
            
            # 사용자 맞춤 피드백 양식 꼬리말 동적 삽입 (별점 1~5 개별 HMAC 서명 링크)
            feedback_links = generate_feedback_links_html(name)
            feedback_footer = f"\n\n---\n💬 오늘 리포트 어떠셨나요?\n\n{feedback_links}\n"
            report_md_content += feedback_footer
            
            subject = f"최근 동향 중심 시황 요약 리포트 - {name}님"
            
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
