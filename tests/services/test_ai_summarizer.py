"""
AI 요약 서비스 배치 브리핑 단위 테스트 모듈.

[Task 6.23, REQ-P05]
"""

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
    generate_market_summary,
    _is_model_not_found_error,
    _parse_batch_theme_response,
    _pick_runtime_model,
    generate_theme_briefings_batch,
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


class TestGenerateMarketSummaryPrompt(unittest.IsolatedAsyncioTestCase):
    """시장 종합 요약 프롬프트 제약 테스트."""

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


if __name__ == "__main__":
    unittest.main()
