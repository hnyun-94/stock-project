"""
AI 요약 서비스 배치 브리핑 단위 테스트 모듈.

[Task 6.23, REQ-P05]
"""

import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules['src.utils.logger'] = MagicMock()

class DummyClientError(Exception):
    """google.genai.errors.ClientError 테스트 대체용."""

    def __init__(self, code, response_json=None, response=None):
        self.code = code
        self.response_json = response_json or {}
        self.response = response
        error_data = self.response_json.get("error", {})
        self.status = error_data.get("status")
        self.message = error_data.get("message", "")
        super().__init__(f"{self.code} {self.status}. {self.response_json}")


mock_genai = types.ModuleType("google.genai")
mock_genai.Client = MagicMock()
mock_genai.types = types.SimpleNamespace(
    GenerateContentConfig=MagicMock(),
    SafetySetting=MagicMock(),
)
mock_errors_module = types.ModuleType("google.genai.errors")
mock_errors_module.ClientError = DummyClientError

mock_google_module = types.ModuleType("google")
mock_google_module.genai = mock_genai
sys.modules.setdefault("google", mock_google_module)
sys.modules.setdefault("google.genai", mock_genai)
sys.modules.setdefault("google.genai.errors", mock_errors_module)

from src.models import MarketIndex, NewsArticle
from src.services.ai_summarizer import (
    GeminiBudgetExceededError,
    GeminiQuotaExhaustedError,
    _is_model_not_found_error,
    _parse_batch_theme_response,
    _parse_holding_insights_response,
    _pick_runtime_model,
    _reset_gemini_runtime_state,
    generate_holding_insights,
    generate_market_summary,
    generate_theme_briefings_batch,
    prepare_ai_run,
    safe_gemini_call,
)


class TestModelSelectionHelpers(unittest.TestCase):
    """모델 선택/오류 판별 헬퍼 테스트."""

    def test_pick_runtime_model_prefers_available_candidate(self):
        selected = _pick_runtime_model(
            requested_model="gemini-2.5-flash-lite",
            available_models=["gemini-2.0-flash", "gemini-2.5-flash-lite"],
        )
        self.assertEqual(selected, "gemini-2.5-flash-lite")

    def test_pick_runtime_model_uses_available_flash_when_requested_missing(self):
        selected = _pick_runtime_model(
            requested_model="gemini-1.5-flash",
            available_models=["gemini-2.0-flash", "gemini-pro"],
        )
        self.assertEqual(selected, "gemini-2.0-flash")

    def test_model_not_found_error_detection(self):
        err = DummyClientError(
            404,
            {
                "error": {
                    "status": "NOT_FOUND",
                    "message": "models/gemini-1.5-flash is not found",
                }
            },
        )
        self.assertTrue(_is_model_not_found_error(err))


class TestBatchThemeResponseParser(unittest.TestCase):
    """배치 JSON 응답 파싱 테스트."""

    def test_parse_valid_results(self):
        """정상 JSON 응답을 순서대로 추출한다."""
        response_text = (
            '{"results":['
            '{"keyword":"반도체","briefing_md":"### 반도체 브리핑"},'
            '{"keyword":"2차전지","briefing_md":"### 2차전지 브리핑"}'
            ']}'
        )
        parsed = _parse_batch_theme_response(response_text, 2)
        self.assertEqual(parsed, ["### 반도체 브리핑", "### 2차전지 브리핑"])

    def test_parse_invalid_json_returns_empty_slots(self):
        """JSON 파싱 실패 시 fallback 슬롯(None)을 반환한다."""
        parsed = _parse_batch_theme_response("not-json", 2)
        self.assertEqual(parsed, [None, None])


class TestGenerateThemeBriefingsBatch(unittest.IsolatedAsyncioTestCase):
    """배치 브리핑 생성 테스트."""

    def setUp(self):
        _reset_gemini_runtime_state()

    async def test_batch_success_without_fallback(self):
        """배치 응답이 정상일 때 개별 fallback을 호출하지 않는다."""
        theme_items = [
            {
                "keyword": "반도체",
                "keyword_news": [NewsArticle(title="반도체 수요 증가", link="a.com")],
                "community_posts": [],
            },
            {
                "keyword": "2차전지",
                "keyword_news": [NewsArticle(title="배터리 수출 확대", link="b.com")],
                "community_posts": [],
            },
        ]
        batch_json = (
            '{"results":['
            '{"keyword":"반도체","briefing_md":"### 반도체"},'
            '{"keyword":"2차전지","briefing_md":"### 2차전지"}'
            ']}'
        )

        with (
            patch(
                "src.services.ai_summarizer.safe_gemini_call",
                new=AsyncMock(return_value=batch_json),
            ) as mock_batch_call,
            patch(
                "src.services.ai_summarizer.generate_theme_briefing",
                new=AsyncMock(return_value="fallback"),
            ) as mock_single_call,
        ):
            results = await generate_theme_briefings_batch(theme_items)

        self.assertEqual(results, ["### 반도체", "### 2차전지"])
        self.assertEqual(mock_batch_call.await_count, 1)
        self.assertEqual(
            mock_batch_call.await_args.kwargs.get("response_mime_type"),
            "application/json",
        )
        self.assertEqual(mock_single_call.await_count, 0)

    async def test_batch_parse_failure_falls_back_to_individual_calls(self):
        """배치 JSON 파싱 실패 시 개별 브리핑 호출로 전체 대체한다."""
        theme_items = [
            {
                "keyword": "반도체",
                "keyword_news": [NewsArticle(title="반도체 수요 증가", link="a.com")],
                "community_posts": [],
            },
            {
                "keyword": "2차전지",
                "keyword_news": [NewsArticle(title="배터리 수출 확대", link="b.com")],
                "community_posts": [],
            },
        ]

        with (
            patch(
                "src.services.ai_summarizer.safe_gemini_call",
                new=AsyncMock(return_value="not-json"),
            ),
            patch(
                "src.services.ai_summarizer.generate_theme_briefing",
                new=AsyncMock(side_effect=["fallback-1", "fallback-2"]),
            ) as mock_single_call,
        ):
            results = await generate_theme_briefings_batch(theme_items)

        self.assertEqual(results, ["fallback-1", "fallback-2"])
        self.assertEqual(mock_single_call.await_count, 2)

    async def test_batch_quota_error_uses_local_fallback_without_single_calls(self):
        """quota 고갈 시 개별 Gemini fallback을 건너뛰고 로컬 브리핑으로 채운다."""
        theme_items = [
            {
                "keyword": "AI",
                "keyword_news": [
                    NewsArticle(
                        title="AI 서버 투자 확대",
                        link="a.com",
                        summary="AI 서버 증설과 메모리 수요가 함께 확대되는 흐름입니다.",
                    )
                ],
                "community_posts": [],
            }
        ]

        with (
            patch(
                "src.services.ai_summarizer.safe_gemini_call",
                new=AsyncMock(side_effect=GeminiQuotaExhaustedError("quota")),
            ),
            patch(
                "src.services.ai_summarizer.generate_theme_briefing",
                new=AsyncMock(side_effect=AssertionError("single fallback should not run")),
            ) as mock_single_call,
        ):
            results = await generate_theme_briefings_batch(theme_items)

        self.assertEqual(mock_single_call.await_count, 0)
        self.assertIn("AI 서버 투자 확대", results[0])
        self.assertIn("투자 포인트", results[0])


class TestGenerateMarketSummaryPrompt(unittest.IsolatedAsyncioTestCase):
    """시장 종합 요약 프롬프트 제약 테스트."""

    def setUp(self):
        _reset_gemini_runtime_state()

    async def test_market_summary_prompt_includes_five_line_limit(self):
        market_indices = [
            MarketIndex(
                name="KOSPI",
                value="2500.12",
                change="+12.34",
                investor_summary="외국인 순매수",
            )
        ]
        market_news = [NewsArticle(title="반도체 업종 강세", link="https://example.com")]

        with (
            patch(
                "src.services.ai_summarizer.get_cached_prompt",
                return_value={
                    "content": "기본 시장 요약 프롬프트",
                    "model": "gemini-2.5-flash",
                    "temperature": 0.5,
                },
            ),
            patch(
                "src.services.ai_summarizer.get_tuning_adjustments",
                return_value={
                    "temperature_delta": 0.0,
                    "style_hint": "",
                    "feedback_summary": "",
                },
            ),
            patch(
                "src.services.ai_summarizer.apply_tuning_to_prompt",
                side_effect=lambda prompt, _: prompt,
            ),
            patch(
                "src.services.ai_summarizer.safe_gemini_call",
                new=AsyncMock(return_value="요약 결과"),
            ) as mock_call,
        ):
            await generate_market_summary(market_indices, market_news)

        sent_prompt = mock_call.await_args.args[0]
        self.assertIn("총 5줄 이내", sent_prompt)

    async def test_market_summary_returns_structured_fallback_on_quota_error(self):
        market_indices = [
            MarketIndex(
                name="KOSPI",
                value="2500.12",
                change="+12.34",
                investor_summary="외국인 순매수 우위",
            )
        ]
        market_news = [
            NewsArticle(
                title="반도체 업종 반등",
                link="https://example.com",
                summary="반도체 대형주가 반등하며 수급 개선 기대가 살아났습니다.",
            )
        ]

        with patch(
            "src.services.ai_summarizer.safe_gemini_call",
            new=AsyncMock(side_effect=GeminiQuotaExhaustedError("quota")),
        ):
            summary = await generate_market_summary(market_indices, market_news)

        self.assertIn("KOSPI 2500.12", summary)
        self.assertIn("반도체 업종 반등", summary)
        self.assertNotIn("시장 요약 생성 실패", summary)


class TestHoldingInsights(unittest.IsolatedAsyncioTestCase):
    """보유 종목별 인사이트 생성 테스트."""

    def setUp(self):
        _reset_gemini_runtime_state()

    def test_parse_holding_insights_response_fills_missing_holdings(self):
        response_text = (
            '{"insights":['
            '{"holding":"삼성전자","stance":"유지","summary":"메모리 수요 개선","action":"수요 추세 확인"}'
            ']}'
        )
        parsed = _parse_holding_insights_response(
            response_text,
            holdings=["삼성전자", "SK하이닉스"],
            holding_news_map={
                "삼성전자": [NewsArticle(title="삼성전자 실적 개선", link="a.com")],
                "SK하이닉스": [NewsArticle(title="SK하이닉스 HBM 확대", link="b.com")],
            },
        )

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["holding"], "삼성전자")
        self.assertEqual(parsed[1]["holding"], "SK하이닉스")

    async def test_generate_holding_insights_uses_json_mode(self):
        response_text = (
            '{"insights":['
            '{"holding":"삼성전자","stance":"유지","summary":"메모리 수요 개선","action":"수요 추세 확인"}'
            ']}'
        )
        with patch(
            "src.services.ai_summarizer.safe_gemini_call",
            new=AsyncMock(return_value=response_text),
        ) as mock_call:
            results = await generate_holding_insights(
                holdings=["삼성전자"],
                market_summary="시장 요약",
                theme_briefings=["### AI\n- 반도체 수요 증가"],
                holding_news_map={
                    "삼성전자": [NewsArticle(title="삼성전자 실적 개선", link="a.com")]
                },
            )

        self.assertEqual(results[0]["holding"], "삼성전자")
        self.assertEqual(
            mock_call.await_args.kwargs.get("response_mime_type"),
            "application/json",
        )

    async def test_generate_holding_insights_returns_concrete_fallback_on_quota_error(self):
        with patch(
            "src.services.ai_summarizer.safe_gemini_call",
            new=AsyncMock(side_effect=GeminiQuotaExhaustedError("quota")),
        ):
            results = await generate_holding_insights(
                holdings=["삼성전자"],
                market_summary="AI 수요 회복과 메모리 반등 기대가 부각됩니다.",
                theme_briefings=["### AI\n- HBM 공급 확대가 핵심 포인트입니다."],
                holding_news_map={
                    "삼성전자": [
                        NewsArticle(
                            title="삼성전자 HBM 공급 확대 기대",
                            link="a.com",
                            summary="HBM 공급 확대와 고객사 발주 기대가 동시에 반영됩니다.",
                        )
                    ]
                },
            )

        self.assertEqual(results[0]["holding"], "삼성전자")
        self.assertIn("HBM", results[0]["summary"])
        self.assertIn("발주", results[0]["action"])


class TestGeminiQuotaGuard(unittest.IsolatedAsyncioTestCase):
    """Gemini quota guard 테스트."""

    def setUp(self):
        _reset_gemini_runtime_state()

    async def test_safe_gemini_call_blocks_followup_calls_after_quota_error(self):
        quota_error = DummyClientError(
            429,
            {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded for metric",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                            "violations": [
                                {
                                    "quotaId": "GenerateRequestsPerDayPerModel-FreeTier",
                                }
                            ],
                        },
                        {
                            "@type": "type.googleapis.com/google.rpc.RetryInfo",
                            "retryDelay": "54s",
                        },
                    ],
                }
            },
        )

        with (
            patch(
                "src.services.ai_summarizer.get_db",
                return_value=types.SimpleNamespace(
                    get_runtime_state=lambda _key: None,
                    set_runtime_state=lambda _key, _value: None,
                    delete_runtime_state=lambda _key: None,
                ),
            ),
            patch("src.services.ai_summarizer._get_client", return_value=MagicMock()),
            patch(
                "src.services.ai_summarizer._get_available_models",
                new=AsyncMock(return_value=["gemini-2.5-flash"]),
            ),
            patch(
                "src.services.ai_summarizer._generate_content_with_model",
                new=AsyncMock(side_effect=quota_error),
            ) as mock_generate,
            patch("src.services.ai_summarizer.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            with self.assertRaises(GeminiQuotaExhaustedError):
                await safe_gemini_call("prompt")
            with self.assertRaises(GeminiQuotaExhaustedError):
                await safe_gemini_call("prompt-2")

        self.assertEqual(mock_generate.await_count, 2)
        self.assertTrue(any(call.args == (57,) for call in mock_sleep.await_args_list))

    async def test_safe_gemini_call_retries_after_short_quota_delay(self):
        quota_error = DummyClientError(
            429,
            {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded for metric",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                            "violations": [
                                {
                                    "quotaId": "GenerateRequestsPerMinutePerModel-FreeTier",
                                }
                            ],
                        },
                        {
                            "@type": "type.googleapis.com/google.rpc.RetryInfo",
                            "retryDelay": "6s",
                        },
                    ],
                }
            },
        )

        with (
            patch(
                "src.services.ai_summarizer.get_db",
                return_value=types.SimpleNamespace(
                    get_runtime_state=lambda _key: None,
                    set_runtime_state=lambda _key, _value: None,
                    delete_runtime_state=lambda _key: None,
                ),
            ),
            patch("src.services.ai_summarizer._get_client", return_value=MagicMock()),
            patch(
                "src.services.ai_summarizer._get_available_models",
                new=AsyncMock(return_value=["gemini-2.5-flash"]),
            ),
            patch(
                "src.services.ai_summarizer._generate_content_with_model",
                new=AsyncMock(side_effect=[quota_error, types.SimpleNamespace(text="ok")]),
            ) as mock_generate,
            patch("src.services.ai_summarizer.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            result = await safe_gemini_call("prompt")

        self.assertEqual(result, "ok")
        self.assertEqual(mock_generate.await_count, 2)
        self.assertTrue(any(call.args == (9,) for call in mock_sleep.await_args_list))

    async def test_safe_gemini_call_falls_back_when_quota_delay_exceeds_budget(self):
        quota_error = DummyClientError(
            429,
            {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded for metric",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                            "violations": [
                                {
                                    "quotaId": "GenerateRequestsPerMinutePerModel-FreeTier",
                                }
                            ],
                        },
                        {
                            "@type": "type.googleapis.com/google.rpc.RetryInfo",
                            "retryDelay": "61s",
                        },
                    ],
                }
            },
        )

        with (
            patch(
                "src.services.ai_summarizer.get_db",
                return_value=types.SimpleNamespace(
                    get_runtime_state=lambda _key: None,
                    set_runtime_state=lambda _key, _value: None,
                    delete_runtime_state=lambda _key: None,
                ),
            ),
            patch("src.services.ai_summarizer._get_client", return_value=MagicMock()),
            patch(
                "src.services.ai_summarizer._get_available_models",
                new=AsyncMock(return_value=["gemini-2.5-flash"]),
            ),
            patch(
                "src.services.ai_summarizer._generate_content_with_model",
                new=AsyncMock(side_effect=quota_error),
            ) as mock_generate,
            patch("src.services.ai_summarizer.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            with self.assertRaises(GeminiQuotaExhaustedError):
                await safe_gemini_call("prompt")

        self.assertEqual(mock_generate.await_count, 1)
        self.assertFalse(any(call.args == (61,) for call in mock_sleep.await_args_list))

    async def test_safe_gemini_call_respects_run_budget(self):
        with patch.dict(os.environ, {"GEMINI_MAX_REMOTE_CALLS_PER_RUN": "1"}, clear=False):
            _reset_gemini_runtime_state()
            with (
                patch(
                    "src.services.ai_summarizer.get_db",
                    return_value=types.SimpleNamespace(
                        get_runtime_state=lambda _key: None,
                        set_runtime_state=lambda _key, _value: None,
                        delete_runtime_state=lambda _key: None,
                    ),
                ),
            ):
                prepare_ai_run()
            with (
                patch("src.services.ai_summarizer._get_client", return_value=MagicMock()),
                patch(
                    "src.services.ai_summarizer._get_available_models",
                    new=AsyncMock(return_value=["gemini-2.5-flash"]),
                ),
                patch(
                    "src.services.ai_summarizer._generate_content_with_model",
                    new=AsyncMock(return_value=types.SimpleNamespace(text="ok")),
                ) as mock_generate,
            ):
                result = await safe_gemini_call("prompt")
                self.assertEqual(result, "ok")
                with self.assertRaises(GeminiBudgetExceededError):
                    await safe_gemini_call("prompt-2")

        self.assertEqual(mock_generate.await_count, 1)


if __name__ == "__main__":
    unittest.main()
