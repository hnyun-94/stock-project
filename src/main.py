"""
주식 리포트 자동화 파이프라인 진입점.

Codex reading guide:
1. `run_pipeline()`이 현재 운영 경로의 단일 오케스트레이터입니다.
2. 실행 순서는 공통 데이터 수집 -> 안전 필터/지표 계산 -> 사용자별 개인화 -> 리포트 저장/발송입니다.
3. 주요 외부 의존성은 Notion, Gemini, SQLite, 이메일 큐입니다.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# 스크립트 실행을 위해 환경변수 및 모듈 경로 로드
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from src.crawlers.browser_pool import BrowserPool
from src.crawlers.community import (
    get_dc_stock_gallery,
    get_reddit_wallstreetbets,
    get_stockplus_insight_signals,
)
from src.crawlers.dynamic_community import get_blind_stock_lounge
from src.crawlers.http_client import close_session
from src.crawlers.market_index import get_market_indices
from src.crawlers.naver_datalab import get_naver_datalab_trends
from src.crawlers.naver_news import get_market_news
from src.services.ai_summarizer import (
    generate_holding_insights,
    generate_market_summary,
    generate_theme_briefings_batch,
    prepare_ai_run,
)
from src.services.ai_tracker import record_prediction_snapshot
from src.services.community_safety import (
    filter_community_posts_by_source,
    flatten_safe_community_posts,
    get_enabled_community_sources,
)
from src.services.connector_alerts import dispatch_connector_health_alerts
from src.services.feedback_manager import generate_feedback_links_html
from src.services.market_external_connectors import (
    collect_external_source_snapshot,
)
from src.services.market_source_governance import (
    evaluate_active_sources,
    get_default_source_policies,
    parse_active_source_ids,
)
from src.services.notifier.email import EmailSender
from src.services.notifier.queue_worker import NotificationAction, global_message_queue
from src.services.prompt_manager import fetch_prompts_from_notion
from src.services.report_builder import build_report_payload
from src.services.topic_news import collect_topic_news, select_topic_community_posts
from src.services.user_manager import fetch_active_users
from src.utils.database import close_db, get_db
from src.utils.logger import global_logger, log_critical_error
from src.utils.report_formatter import build_structured_markdown_report
from src.utils.sentiment import analyze_sentiment


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
    """불리언 성격의 환경변수 문자열을 판별합니다."""
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
    """리포트 생성, 이력 저장, 발송까지 포함한 전체 배치를 실행합니다."""
    global_logger.info("=== 🚀 주식 리포트 생성 파이프라인 시작 ===")
    report_reference_time = datetime.now(ZoneInfo("Asia/Seoul"))
    prepare_ai_run()

    # 실행 시작 전 데이터 소스 정책/무료 한도 점검
    _run_source_governance_check()

    # Phase 0: 런타임 캐시와 발송 워커를 준비합니다.
    await asyncio.to_thread(fetch_prompts_from_notion)
    
    global_message_queue.start_workers()
    try:
        # Phase 1: 모든 사용자에게 공통인 시장 컨텍스트를 한 번만 수집합니다.
        global_logger.info("[1/5] 시장 지수 및 공통 뉴스 수집 중... (비동기 병렬)")
        enabled_community_sources = get_enabled_community_sources()
        community_task_factories = {
            "stockplus_insight": lambda: get_stockplus_insight_signals(2),
            "blind_stock_lounge": lambda: get_blind_stock_lounge(2),
            "dc_stock_gallery": lambda: get_dc_stock_gallery(3),
            "reddit_wallstreetbets": lambda: get_reddit_wallstreetbets(3),
        }
        enabled_community_tasks = {
            source_id: task_factory()
            for source_id, task_factory in community_task_factories.items()
            if source_id in enabled_community_sources
        }
        market_indices, market_news, datalab_trends = await asyncio.gather(
            get_market_indices(),
            get_market_news(),
            get_naver_datalab_trends(),
        )
        community_source_posts = {}
        if enabled_community_tasks:
            community_results = await asyncio.gather(
                *enabled_community_tasks.values(),
                return_exceptions=True,
            )
            for source_id, result in zip(enabled_community_tasks.keys(), community_results):
                if isinstance(result, Exception):
                    global_logger.warning("[Community] %s 수집 실패: %s", source_id, result)
                    community_source_posts[source_id] = []
                else:
                    community_source_posts[source_id] = result

        # Phase 2: 공통 컨텍스트를 안전화하고, 공용 요약과 지표를 계산합니다.
        global_logger.info("[2/5] AI 시장 시황 요약 중...")
        market_summary_md = await generate_market_summary(market_indices, market_news, datalab_trends)

        # 커뮤니티 안전 필터 적용
        community_filter_results = filter_community_posts_by_source(
            community_source_posts,
            max_items_per_source=3,
            enabled_sources=enabled_community_sources,
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

        # Phase 3: 수신 대상자를 로드합니다. Notion I/O는 to_thread로 감쌉니다.
        global_logger.info("[3/5] Notion에서 수신 대상자 조회 중...")
        users = await asyncio.to_thread(fetch_active_users)
        
        if not users:
            global_logger.warning("발송할 대상(Active User)이 없어 파이프라인을 종료합니다. (혹은 Notion API Key 설정 누락)")
            return
            
        global_logger.info(f"총 {len(users)}명의 대상자를 확인했습니다.")
        
        # 시장 감정 지표 분석 [Task 6.19, REQ-F04]
        sentiment_score, sentiment_label = analyze_sentiment(
            market_news,
            safe_community_posts,
        )

        # 외부 무료 소스 커넥터 지표 수집 + 텔레메트리 (옵션)
        db = get_db()
        _, connector_telemetry = await collect_external_source_snapshot()
        if connector_telemetry:
            try:
                alert_decisions = await asyncio.to_thread(
                    dispatch_connector_health_alerts,
                    db,
                )
                if alert_decisions:
                    sent_count = sum(1 for item in alert_decisions if item.sent_chat_ids)
                    cooldown_count = sum(1 for item in alert_decisions if item.skipped_by_cooldown)
                    global_logger.info(
                        "[ConnectorAlerts] evaluated=%s sent=%s cooldown=%s",
                        len(alert_decisions),
                        sent_count,
                        cooldown_count,
                    )
            except Exception as exc:
                global_logger.warning(f"[ConnectorAlerts] 운영 알림 평가 실패: {exc}")

        connector_success_rate_7d = db.get_connector_success_rate(days=7)
        connector_success_rate_30d = db.get_connector_success_rate(days=30)
        connector_daily_rollups_7d = db.get_connector_daily_rollups(days=7)
        recent_connector_failures_7d = db.get_recent_connector_failures(days=7, limit=3)
        connector_metric_trends_7d = db.get_connector_metric_trends(days=8)
        avg_feedback_score_30d = db.get_average_score(days=30)
        avg_accuracy_30d = db.get_average_accuracy(days=30)
        topic_news_runtime_cache = {}
        theme_runtime_cache = {}
        holding_runtime_cache = {}

        # Phase 4: 사용자별 추가 수집, AI 개인화, 스냅샷 비교, 발송을 처리합니다.
        for idx, user in enumerate(users, 1):
            name = user.name
            
            global_logger.info(f"\n[4/5] ({idx}/{len(users)}) '{name}'님 맞춤형 데이터 생성 중...")
            keywords_to_search = user.keywords[:2]
            holdings_to_analyze = user.holdings[:4]
            search_topics = list(dict.fromkeys(keywords_to_search + holdings_to_analyze))
            topic_cache_key = tuple(search_topics)
            if topic_cache_key in topic_news_runtime_cache:
                global_logger.info(
                    f"      - 토픽 뉴스 재사용 중 (키워드 {keywords_to_search}, 보유종목 {holdings_to_analyze})..."
                )
                topic_news_map = topic_news_runtime_cache[topic_cache_key]
            else:
                global_logger.info(
                    f"      - 토픽 뉴스 수집 중 (키워드 {keywords_to_search}, 보유종목 {holdings_to_analyze})..."
                )
                topic_news_map = await collect_topic_news(
                    search_topics,
                    cache_prefix="topic_news",
                )
                topic_news_runtime_cache[topic_cache_key] = topic_news_map

            # 테마 브리핑은 batch 1회 호출을 우선 사용하고, 누락 건만 개별 fallback 합니다.
            theme_cache_key = tuple(keywords_to_search)
            if theme_cache_key in theme_runtime_cache:
                global_logger.info("      - 테마 브리핑 결과 재사용 중...")
                theme_sections = theme_runtime_cache[theme_cache_key]
            else:
                theme_items = []
                for keyword in keywords_to_search:
                    global_logger.info(f"      - '{keyword}' 테마 배치 요약 입력 구성 중...")
                    theme_items.append(
                        {
                            "keyword": keyword,
                            "keyword_news": topic_news_map.get(keyword, []),
                            "community_posts": select_topic_community_posts(
                                keyword,
                                safe_community_posts,
                                limit=3,
                            ),
                        }
                    )
                kw_md_results = await generate_theme_briefings_batch(theme_items)
                theme_sections = []
                for keyword, md_text in zip(keywords_to_search, kw_md_results):
                    theme_sections.append({"keyword": keyword, "briefing_md": md_text})
                theme_runtime_cache[theme_cache_key] = theme_sections

            theme_news_map = {
                keyword: topic_news_map.get(keyword, [])
                for keyword in keywords_to_search
            }
            holding_news_map = {
                holding: topic_news_map.get(holding, [])
                for holding in holdings_to_analyze
            }
            holding_insights = []
            if holdings_to_analyze:
                holding_cache_key = (
                    tuple(holdings_to_analyze),
                    market_summary_md,
                    tuple(section["briefing_md"] for section in theme_sections),
                )
                if holding_cache_key in holding_runtime_cache:
                    global_logger.info(
                        f"      - '{name}'님 보유 종목 인사이트 결과 재사용 중..."
                    )
                    holding_insights = holding_runtime_cache[holding_cache_key]
                else:
                    global_logger.info(
                        f"      - '{name}'님 보유 종목({holdings_to_analyze}) 기반 개별 인사이트 생성 중..."
                    )
                    holding_insights = await generate_holding_insights(
                        holdings_to_analyze,
                        market_summary_md,
                        [section["briefing_md"] for section in theme_sections],
                        holding_news_map,
                    )
                    holding_runtime_cache[holding_cache_key] = holding_insights

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
                theme_news_map=theme_news_map,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                holding_insights=holding_insights,
                holding_news_map=holding_news_map,
                community_posts=safe_community_posts,
                recent_report_rows=recent_report_rows,
                weekly_report_rows=weekly_report_rows,
                monthly_report_rows=monthly_report_rows,
                connector_success_rate_7d=connector_success_rate_7d,
                connector_success_rate_30d=connector_success_rate_30d,
                avg_feedback_score_30d=avg_feedback_score_30d,
                avg_accuracy_30d=avg_accuracy_30d,
                connector_daily_rollups_7d=connector_daily_rollups_7d,
                recent_connector_failures_7d=recent_connector_failures_7d,
                connector_metric_trends_7d=connector_metric_trends_7d,
                reference_time=report_reference_time,
            )

            # 최종 리포트는 "최근 -> 장기" 순서를 유지한 payload를 렌더링합니다.
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
            
            # 피드백 링크는 수신자별 HMAC 서명이 포함된 상태로 후처리합니다.
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
    """전역 타임아웃을 걸어 외부 의존성 hang이 배치를 무기한 점유하지 않게 합니다."""
    try:
        await asyncio.wait_for(run_pipeline(), timeout=300.0)
    except asyncio.TimeoutError:
        global_logger.error("🚨 전역 타임아웃 발생: 파이프라인 실행이 5분을 초과하여 강제 종료되었습니다. (원인: 크롤링 타임아웃 또는 외부 API 응답 지연)")

if __name__ == "__main__":
    asyncio.run(main_with_timeout())
