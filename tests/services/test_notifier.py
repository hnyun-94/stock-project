"""Notifier service regression tests."""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.models import User
from src.services.notifier.email import EmailSender
from src.services.notifier.telegram import TelegramSender


@pytest.fixture
def mock_user():
    """Builds a sample user fixture."""
    return User(
        name="테스터",
        email="test@example.com",
        keywords=["반도체"],
        telegram_id="123456789",
        channels=["email", "telegram"],
    )


@patch("smtplib.SMTP_SSL")
@patch("os.getenv")
def test_email_sender_success(mock_getenv, mock_smtp, mock_user):
    """이메일 발송 성공 테스트."""
    mock_getenv.return_value = "dummy"

    sender = EmailSender()
    result = sender.send(mock_user, "테스트 제목", "테스트 내용")

    assert result is True
    mock_smtp.assert_called_once()


@patch("os.getenv")
def test_email_sender_no_env(mock_getenv, mock_user):
    """이메일 환경변수 누락 시 실패 처리 테스트."""
    mock_getenv.return_value = None

    sender = EmailSender()
    result = sender.send(mock_user, "제목", "내용")

    assert result is False


@patch("requests.post")
def test_telegram_sender_success(mock_post, mock_user):
    """텔레그램 발송 성공 테스트."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    with patch.dict(
        os.environ,
        {
            "TELEGRAM_BOT_TOKEN": "dummy_token",
            "TELEGRAM_REQUEST_TIMEOUT_SECONDS": "7",
        },
        clear=False,
    ):
        sender = TelegramSender()
        result = sender.send(mock_user, "텔레그램 테스트", "본문입니다.")

    assert result is True
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["timeout"] == 7


def test_telegram_sender_no_id():
    """텔레그램 ID가 없는 유저의 경우 실패 처리 테스트."""
    user_no_tg = User(
        name="노텔레그램",
        email="test@example.com",
        keywords=[],
        telegram_id=None,
        channels=["telegram"],
    )
    sender = TelegramSender()
    result = sender.send(user_no_tg, "제목", "내용")

    assert result is False


@patch("requests.post")
def test_telegram_sender_send_to_chat_id(mock_post):
    """운영 알림용 raw chat_id 전송 테스트."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "dummy_token"}, clear=False):
        sender = TelegramSender()
        result = sender.send_to_chat_id("999", "운영 알림", "본문")

    assert result is True
    assert mock_post.call_args.kwargs["json"]["chat_id"] == "999"
    assert mock_post.call_args.kwargs["timeout"] == 10


@patch("requests.post")
def test_telegram_sender_splits_long_message(mock_post):
    """긴 텔레그램 메시지는 여러 chunk로 분할해 전송합니다."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    with patch.dict(
        os.environ,
        {
            "TELEGRAM_BOT_TOKEN": "dummy_token",
            "TELEGRAM_MESSAGE_MAX_LENGTH": "40",
            "TELEGRAM_REQUEST_TIMEOUT_SECONDS": "5",
        },
        clear=False,
    ):
        sender = TelegramSender()
        result = sender.send_to_chat_id("999", "운영 알림", "가" * 120)

    assert result is True
    assert mock_post.call_count >= 2
    sent_texts = [call.kwargs["json"]["text"] for call in mock_post.call_args_list]
    assert sent_texts[0].startswith("[1/")
    assert all(call.kwargs["timeout"] == 5 for call in mock_post.call_args_list)


@patch("requests.post")
def test_telegram_sender_returns_false_on_timeout(mock_post):
    """텔레그램 요청 timeout은 False로 처리합니다."""
    mock_post.side_effect = requests.Timeout("timeout")

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "dummy_token"}, clear=False):
        sender = TelegramSender()
        result = sender.send_to_chat_id("999", "운영 알림", "본문")

    assert result is False
