"""
사용자 조회 서비스 단위 테스트 모듈.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules['src.utils.logger'] = MagicMock()

from src.services.user_manager import fetch_active_users


def _build_user_result(
    name: str,
    *,
    email: str = "user@example.com",
    active: str = "O",
    keywords: str = "AI, 반도체",
) -> dict:
    return {
        "properties": {
            "이름": {"title": [{"text": {"content": name}}]},
            "이메일": {"email": email},
            "관심키워드": {
                "type": "rich_text",
                "rich_text": [{"text": {"content": keywords}}],
            },
            "수신여부": {"select": {"name": active}},
        }
    }


class TestUserManager(unittest.TestCase):
    """Notion 사용자 조회 로직을 검증합니다."""

    def test_fetch_active_users_handles_pagination(self):
        first_page = MagicMock()
        first_page.raise_for_status.return_value = None
        first_page.json.return_value = {
            "results": [_build_user_result("첫번째")],
            "has_more": True,
            "next_cursor": "cursor-1",
        }

        second_page = MagicMock()
        second_page.raise_for_status.return_value = None
        second_page.json.return_value = {
            "results": [_build_user_result("두번째")],
            "has_more": False,
            "next_cursor": None,
        }

        with (
            patch.dict(
                "os.environ",
                {
                    "NOTION_TOKEN": "token",
                    "NOTION_DATABASE_ID": "db-id",
                },
                clear=False,
            ),
            patch("httpx.post", side_effect=[first_page, second_page]) as mock_post,
        ):
            users = fetch_active_users()

        self.assertEqual([user.name for user in users], ["첫번째", "두번째"])
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"], {"start_cursor": "cursor-1"})

    def test_fetch_active_users_filters_inactive_rows(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "results": [
                _build_user_result("활성", active="O"),
                _build_user_result("비활성", active="X"),
            ],
            "has_more": False,
            "next_cursor": None,
        }

        with (
            patch.dict(
                "os.environ",
                {
                    "NOTION_TOKEN": "token",
                    "NOTION_DATABASE_ID": "db-id",
                },
                clear=False,
            ),
            patch("httpx.post", return_value=response),
        ):
            users = fetch_active_users()

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, "활성")


if __name__ == "__main__":
    unittest.main()
