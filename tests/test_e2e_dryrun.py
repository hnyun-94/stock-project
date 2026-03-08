"""
E2E 파이프라인 드라이런(Dry-run) 테스트 모듈.

실제 외부 API 호출 없이, 핵심 데이터 흐름 단위를 검증합니다.

드라이런 테스트의 목적:
1. 모델 간 데이터 전달이 정상인지 확인
2. report_formatter의 빈 데이터/정상 데이터 처리 확인
3. cache → deduplicator → formatter 흐름 통합 검증
4. 리팩토링 후 회귀 버그 발견

[Task 6.18, REQ-Q08]
"""

import sys
import unittest
from unittest.mock import MagicMock

# logger mock
sys.modules['src.utils.logger'] = MagicMock()

from src.models import MarketIndex, NewsArticle, User
from src.utils.cache import TTLCache
from src.utils.deduplicator import deduplicate_news
from src.utils.report_formatter import (
    build_structured_markdown_report,
    markdown_to_html,
)


class TestDataFlowIntegration(unittest.TestCase):
    """데이터 모델 간 흐름 통합 테스트."""

    def test_news_article_to_dedup_to_cache(self):
        """NewsArticle → deduplicate → cache 흐름 검증.

        실제 파이프라인에서는:
        1. 크롤러가 NewsArticle 리스트를 반환
        2. deduplicate_news()가 중복 제거
        3. crawl_cache에 저장
        4. 이후 캐시에서 꺼내어 AI에 전달
        """
        # 1. 크롤러가 반환하는 뉴스 (중복 포함)
        raw_news = [
            NewsArticle(title="삼성전자 4분기 실적 발표 예정", link="a.com"),
            NewsArticle(title="삼성전자 4분기 실적 공식 발표", link="b.com"),
            NewsArticle(title="코스피 2500선 돌파", link="c.com"),
        ]

        # 2. 중복 제거
        deduped = deduplicate_news(raw_news, threshold=0.7)
        self.assertLessEqual(len(deduped), len(raw_news))
        self.assertGreater(len(deduped), 0)

        # 3. 캐시에 저장 및 조회
        cache = TTLCache(default_ttl=600, max_size=100)
        cache.set("keyword_news:삼성전자", deduped)

        cached = cache.get("keyword_news:삼성전자")
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), len(deduped))

        # 4. 캐시된 뉴스의 모든 항목이 NewsArticle인지 확인
        for news in cached:
            self.assertIsInstance(news, NewsArticle)
            self.assertTrue(len(news.title) > 0)
            self.assertTrue(len(news.link) > 0)

    def test_user_model_properties(self):
        """User 모델 기본값 및 필드 접근 검증.

        파이프라인에서 User 모델은 Notion에서 조회된 사용자 정보를 담으며,
        keywords, channels, holdings 등의 기본값이 올바르게 설정되어야 합니다.
        """
        user = User(
            name="테스트",
            email="test@example.com",
            keywords=["삼성전자", "SK하이닉스"]
        )
        # 기본값 확인
        self.assertEqual(user.channels, ["email"])
        self.assertEqual(user.holdings, [])
        self.assertIsNone(user.telegram_id)

        # keywords 슬라이싱 (main.py에서 [:2] 사용)
        self.assertEqual(user.keywords[:2], ["삼성전자", "SK하이닉스"])

    def test_market_index_format(self):
        """MarketIndex 모델 데이터 형식 검증."""
        idx = MarketIndex(
            name="KOSPI",
            value="2,500.12",
            change="+15.34",
            investor_summary="외국인 순매수"
        )
        # AI 프롬프트에서 사용되는 형식
        formatted = f"- {idx.name}: {idx.value} ({idx.investor_summary})"
        self.assertIn("KOSPI", formatted)
        self.assertIn("2,500.12", formatted)
        self.assertIn("외국인 순매수", formatted)

    def test_news_with_summary_format(self):
        """리드 문단이 포함된 뉴스의 AI 프롬프트 포맷 검증.

        ai_summarizer.py에서 summary가 있을 때:
        '1. 제목\\n   → 본문 요약 (150자)'
        """
        news = NewsArticle(
            title="삼성전자 실적",
            link="a.com",
            summary="삼성전자가 4분기 역대 최고 실적을 발표했다."
        )
        # ai_summarizer.py의 포맷
        context = f"1. {news.title}\n"
        if news.summary:
            context += f"   → {news.summary[:150]}\n"

        self.assertIn("삼성전자 실적", context)
        self.assertIn("→", context)
        self.assertIn("역대 최고 실적", context)


class TestCacheAndDedupIntegration(unittest.TestCase):
    """캐시와 중복제거 통합 테스트."""

    def test_cache_preserves_deduped_results(self):
        """캐시에 저장된 중복제거 결과가 변질되지 않는지 검증."""
        news = [
            NewsArticle(title="뉴스1", link="a.com", summary="요약1"),
            NewsArticle(title="뉴스2", link="b.com"),
        ]
        deduped = deduplicate_news(news)

        cache = TTLCache(default_ttl=600)
        cache.set("test_key", deduped)

        # 원본과 캐시 결과 비교
        cached = cache.get("test_key")
        self.assertEqual(len(cached), len(deduped))
        self.assertEqual(cached[0].title, deduped[0].title)
        self.assertEqual(cached[0].summary, deduped[0].summary)

    def test_empty_news_handled(self):
        """빈 뉴스 리스트 처리 검증."""
        deduped = deduplicate_news([])
        self.assertEqual(len(deduped), 0)

        cache = TTLCache(default_ttl=600)
        cache.set("empty_key", deduped)
        self.assertEqual(cache.get("empty_key"), [])

    def test_cache_miss_returns_none(self):
        """캐시 미스 시 None 반환 후 크롤링 트리거가 가능한지 검증."""
        cache = TTLCache(default_ttl=600)
        result = cache.get("nonexistent_key")
        self.assertIsNone(result)

        # None이면 크롤링 실행 (파이프라인 로직 시뮬레이션)
        if result is None:
            crawled = [NewsArticle(title="새 뉴스", link="new.com")]
            cache.set("nonexistent_key", crawled)

        self.assertIsNotNone(cache.get("nonexistent_key"))

    def test_structured_report_formatter_renders_core_sections(self):
        """구조화 리포트 payload가 주요 섹션을 모두 렌더링한다."""
        markdown_text = build_structured_markdown_report(
            {
                "title": "🌤️ 리포트",
                "subtitle": "요약",
                "headline_changes": ["헤드라인 1"],
                "reliability_badge": {
                    "label": "높음",
                    "score": 88,
                    "gauge": "█████████░",
                    "reason": "최근 7일 평균 성공률 97%, 최신 데이터 0일 전, 주의 source 0개",
                },
                "decision_tiles": [
                    {"label": "시장 톤", "value": "중립", "detail": "급한 방향 추격보다 확인이 먼저입니다."},
                    {"label": "먼저 볼 테마", "value": "AI", "detail": "반복 등장 테마입니다."},
                ],
                "market_scoreboard": {
                    "headers": ["항목", "현재 값", "읽는 법"],
                    "rows": [["KOSPI", "2650.10", "외국인 수급 확인"], ["시장 심리", "+8 / 중립 ████░░░░", "과열 여부 확인"]],
                },
                "quick_take": {
                    "summary": "핵심 요약",
                    "details": ["근거 1"],
                    "why_it_matters": "왜 중요한가",
                    "watch_points": ["수급", "환율"],
                    "related_links": [{"label": "시장 기사", "url": "https://news.example.com/market"}],
                    "positive_view": "긍정",
                    "neutral_view": "중립",
                    "negative_view": "부정",
                    "outlook": "전망",
                },
                "insight_lenses": [
                    {
                        "title": "경제 온도",
                        "summary": "요약 1",
                        "details": ["근거 1"],
                        "why_it_matters": "왜 중요한가",
                        "watch_points": ["수급"],
                        "related_links": [{"label": "경제 기사", "url": "https://news.example.com/economy"}],
                        "positive_view": "긍정",
                        "neutral_view": "중립",
                        "negative_view": "부정",
                    }
                ],
                "time_windows": [
                    {
                        "label": "1D",
                        "title": "오늘",
                        "summary": "요약 1",
                        "details": ["근거 1"],
                        "why_it_matters": "왜 중요한가",
                        "watch_points": ["외국인 수급"],
                        "related_links": [{"label": "장중 기사", "url": "https://news.example.com/day"}],
                        "positive_view": "긍정",
                        "neutral_view": "중립",
                        "negative_view": "부정",
                        "outlook": "전망",
                    }
                ],
                "data_quality_section": {
                    "summary": "최근 7일 데이터 품질은 혼조입니다.",
                    "details": ["근거 1", "근거 2"],
                    "positive_view": "긍정",
                    "neutral_view": "중립",
                    "negative_view": "부정",
                    "outlook": "전망",
                    "table_headers": ["날짜", "소스", "성공률", "평균 지연", "판단"],
                    "table_rows": [["2026-03-07", "opendart", "100% ████████", "120ms · 빠름", "안정"]],
                },
                "domain_signal_sections": [
                    {
                        "title": "OpenDART 공시 흐름",
                        "summary": "실적 공시 비중이 늘었습니다.",
                        "details": ["실적 공시 6건"],
                        "why_it_matters": "왜 중요한가",
                        "watch_points": ["실적 공시", "자금조달 공시"],
                        "positive_view": "긍정",
                        "neutral_view": "중립",
                        "negative_view": "부정",
                        "outlook": "전망",
                        "table_headers": ["지표", "최근값", "1D 변화", "7D 변화"],
                        "table_rows": [["실적/영업", "6건 ▁▅█", "▲ +2건", "▲ +4건"]],
                    }
                ],
                "theme_sections": [
                    {
                        "keyword": "AI",
                        "summary": "테마 요약",
                        "details": ["테마 근거"],
                        "why_it_matters": "왜 중요한가",
                        "watch_points": ["HBM", "고객사 CAPEX"],
                        "related_links": [{"label": "AI 기사", "url": "https://news.example.com/ai"}],
                        "positive_view": "긍정",
                        "neutral_view": "중립",
                        "negative_view": "부정",
                        "outlook": "전망",
                    }
                ],
                "holding_sections": [
                    {
                        "holding": "삼성전자",
                        "stance": "유지",
                        "summary": "근거",
                        "details": ["뉴스 근거"],
                        "why_it_matters": "왜 중요한가",
                        "watch_points": ["HBM 납품 확대"],
                        "related_links": [{"label": "삼성 기사", "url": "https://news.example.com/samsung"}],
                        "positive_view": "긍정",
                        "neutral_view": "중립",
                        "negative_view": "부정",
                        "outlook": "전망",
                        "action": "액션",
                    }
                ],
                "long_term_section": {
                    "summary": "장기 1",
                    "details": ["장기 근거"],
                    "why_it_matters": "왜 중요한가",
                    "watch_points": ["장기 테마 유지"],
                    "positive_view": "긍정",
                    "neutral_view": "중립",
                    "negative_view": "부정",
                    "outlook": "전망",
                },
                "learning_card": {
                    "term": "환율",
                    "summary": "환율은 원화와 달러의 교환 비율입니다.",
                    "why_today": "오늘은 환율이 시장 해석의 핵심 변수였습니다.",
                    "how_to_read": "보통 환율이 오르면 시장 불안 해석이 커집니다.",
                },
                "glossary": [{"term": "HBM", "definition": "고성능 메모리"}],
            }
        )

        self.assertIn("## 📍 지금 결론", markdown_text)
        self.assertIn("### 빠르게 보는 판단표", markdown_text)
        self.assertIn("### 오늘 바로 볼 숫자", markdown_text)
        self.assertIn("## 🌍 경제 상황과 트렌드", markdown_text)
        self.assertIn("## 🕒 시간대 압축판", markdown_text)
        self.assertTrue(markdown_text.startswith("# 🌤️ 리포트"))
        self.assertIn("**리포트 신뢰도**: 높음", markdown_text)
        self.assertIn("█████████░", markdown_text)
        self.assertIn("| 체크 대상 | 현재 판단 | 읽는 이유 |", markdown_text)
        self.assertIn("| 체크 대상 | 오늘 숫자 | 읽는 포인트 |", markdown_text)
        self.assertIn("+8 / **중립** ████░░░░", markdown_text)
        self.assertIn("100% ████████", markdown_text)
        self.assertIn("6건 ▁▅█", markdown_text)
        self.assertIn("▲ +2건", markdown_text)
        self.assertIn("| 기간 | 핵심 요약 | 바로 볼 점 |", markdown_text)
        self.assertIn("## 🛰 데이터 신뢰도", markdown_text)
        self.assertIn("## 🧪 보조 지표 해석", markdown_text)
        self.assertIn("## 💼 보유 종목별 인사이트", markdown_text)
        self.assertIn("## 📘 오늘의 경제 상식", markdown_text)
        self.assertIn("## 🧩 용어 풀이", markdown_text)
        self.assertIn("### 삼성전자", markdown_text)
        self.assertIn("| 기준일 | 데이터 출처 | 정상 수집 비율 | 응답 속도 | 읽는 포인트 |", markdown_text)
        self.assertIn("| 체크 지표 | 지금 수치 | 하루 변화 | 일주일 변화 |", markdown_text)
        self.assertIn("[시장 기사](https://news.example.com/market)", markdown_text)
        self.assertIn("[삼성 기사](https://news.example.com/samsung)", markdown_text)
        self.assertIn("[경제 기사](https://news.example.com/economy)", markdown_text)
        self.assertIn("**중립**", markdown_text)
        self.assertNotIn("**인공지능(**AI**)**", markdown_text)

    def test_markdown_to_html_inlines_email_styles(self):
        html_text = markdown_to_html("# 제목\n\n> 요약\n\n| 항목 | 값 |\n| --- | --- |\n| KOSPI | 2600 |")

        self.assertIn("<h1 style=", html_text)
        self.assertIn("<table role=\"presentation\"", html_text)
        self.assertIn("<body style=", html_text)
        self.assertIn("#AEBDCA", html_text)
        self.assertIn("#E8DFCA", html_text)
        self.assertIn("href=\"https://example.com\"", markdown_to_html("[기사](https://example.com)"))


if __name__ == "__main__":
    unittest.main()
