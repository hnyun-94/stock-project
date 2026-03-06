"""
Prompt manager unit tests.

Validates Notion prompt loading with flexible schema aliases, pagination, and
safe template formatting behavior.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["src.utils.logger"] = MagicMock()

import src.services.prompt_manager as prompt_manager


class FakeResponse:
    """Simple fake HTTP response for mocked httpx.post."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestPromptManager(unittest.TestCase):
    """Prompt manager behavior tests."""

    def setUp(self):
        prompt_manager._PROMPT_CACHE.clear()

    def test_load_prompt_with_korean_alias_schema(self):
        """Korean alias schema should be parsed and keyed by PromptKey."""
        payload = {
            "results": [
                {
                    "properties": {
                        "제목": {
                            "type": "title",
                            "title": [{"plain_text": "시장 요약"}],
                        },
                        "본문": {
                            "type": "rich_text",
                            "rich_text": [
                                {"plain_text": "{context_indices} | {context_news}"}
                            ],
                        },
                        "활성": {"type": "checkbox", "checkbox": True},
                        "모델": {
                            "type": "select",
                            "select": {"name": "gemini-2.0-flash"},
                        },
                        "온도": {"type": "number", "number": 0.2},
                        "PromptKey": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "market_summary"}],
                        },
                    }
                }
            ],
            "has_more": False,
        }

        with (
            patch.dict(
                os.environ,
                {
                    "NOTION_TOKEN": "token",
                    "NOTION_PROMPT_DB_ID": "db",
                    "GEMINI_MODEL": "gemini-2.5-flash",
                },
                clear=False,
            ),
            patch("httpx.post", return_value=FakeResponse(payload)),
        ):
            prompt_manager.fetch_prompts_from_notion()

        loaded = prompt_manager.get_cached_prompt(
            "market_summary",
            context_indices="KOSPI",
            context_news="반등",
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["model"], "gemini-2.0-flash")
        self.assertEqual(loaded["temperature"], 0.2)
        self.assertIn("KOSPI", loaded["content"])
        self.assertIn("반등", loaded["content"])

    def test_inactive_prompt_is_skipped(self):
        """Unchecked IsActive rows should not be loaded."""
        payload = {
            "results": [
                {
                    "properties": {
                        "Title": {
                            "type": "title",
                            "title": [{"plain_text": "theme_briefing"}],
                        },
                        "Content": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "x"}],
                        },
                        "IsActive": {"type": "checkbox", "checkbox": False},
                    }
                }
            ],
            "has_more": False,
        }

        with (
            patch.dict(
                os.environ,
                {"NOTION_TOKEN": "token", "NOTION_PROMPT_DB_ID": "db"},
                clear=False,
            ),
            patch("httpx.post", return_value=FakeResponse(payload)),
        ):
            prompt_manager.fetch_prompts_from_notion()

        self.assertIsNone(prompt_manager.get_cached_prompt("theme_briefing"))

    def test_missing_template_variable_is_replaced_with_empty_string(self):
        """Missing placeholders should not break runtime prompt formatting."""
        payload = {
            "results": [
                {
                    "properties": {
                        "Title": {
                            "type": "title",
                            "title": [{"plain_text": "theme_briefing"}],
                        },
                        "Content": {
                            "type": "rich_text",
                            "rich_text": [
                                {"plain_text": "테마={keyword} / 누락={missing_field}"}
                            ],
                        },
                        "IsActive": {"type": "checkbox", "checkbox": True},
                    }
                }
            ],
            "has_more": False,
        }

        with (
            patch.dict(
                os.environ,
                {"NOTION_TOKEN": "token", "NOTION_PROMPT_DB_ID": "db"},
                clear=False,
            ),
            patch("httpx.post", return_value=FakeResponse(payload)),
        ):
            prompt_manager.fetch_prompts_from_notion()

        loaded = prompt_manager.get_cached_prompt("theme_briefing", keyword="AI")
        self.assertIsNotNone(loaded)
        self.assertIn("테마=AI", loaded["content"])
        self.assertIn("누락=", loaded["content"])

    def test_pagination_loads_all_rows(self):
        """Cursor pagination should aggregate all prompt rows."""
        first_page = {
            "results": [
                {
                    "properties": {
                        "Title": {
                            "type": "title",
                            "title": [{"plain_text": "market_summary"}],
                        },
                        "Content": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "a"}],
                        },
                        "IsActive": {"type": "checkbox", "checkbox": True},
                    }
                }
            ],
            "has_more": True,
            "next_cursor": "cursor-1",
        }
        second_page = {
            "results": [
                {
                    "properties": {
                        "Title": {
                            "type": "title",
                            "title": [{"plain_text": "portfolio_analysis"}],
                        },
                        "Content": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "b"}],
                        },
                        "IsActive": {"type": "checkbox", "checkbox": True},
                    }
                }
            ],
            "has_more": False,
        }

        with (
            patch.dict(
                os.environ,
                {"NOTION_TOKEN": "token", "NOTION_PROMPT_DB_ID": "db"},
                clear=False,
            ),
            patch("httpx.post", side_effect=[FakeResponse(first_page), FakeResponse(second_page)]),
        ):
            prompt_manager.fetch_prompts_from_notion()

        self.assertIsNotNone(prompt_manager.get_cached_prompt("market_summary"))
        self.assertIsNotNone(prompt_manager.get_cached_prompt("portfolio_analysis"))


if __name__ == "__main__":
    unittest.main()
