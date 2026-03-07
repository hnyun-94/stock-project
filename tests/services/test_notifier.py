import pytest
from unittest.mock import patch, MagicMock
from src.models import User
from src.services.notifier.email import EmailSender
from src.services.notifier.telegram import TelegramSender

@pytest.fixture
def mock_user():
    return User(
        name="테스터",
        email="test@example.com",
        keywords=["반도체"],
        telegram_id="123456789",
        channels=["email", "telegram"]
    )

@patch("smtplib.SMTP_SSL")
@patch("os.getenv")
def test_email_sender_success(mock_getenv, mock_smtp, mock_user):
    """이메일 발송 성공 테스트"""
    # 환경변수 모킹 (SENDER_EMAIL, SENDER_APP_PASSWORD)
    mock_getenv.return_value = "dummy"
    
    sender = EmailSender()
    result = sender.send(mock_user, "테스트 제목", "테스트 내용")
    
    assert result is True
    mock_smtp.assert_called_once()


@patch("os.getenv")
def test_email_sender_no_env(mock_getenv, mock_user):
    """이메일 환경변수 누락 시 실패 처리 테스트"""
    mock_getenv.return_value = None
    
    sender = EmailSender()
    result = sender.send(mock_user, "제목", "내용")
    
    assert result is False


@patch("requests.post")
@patch("os.getenv")
def test_telegram_sender_success(mock_getenv, mock_post, mock_user):
    """텔레그램 발송 성공 테스트"""
    mock_getenv.return_value = "dummy_token"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    sender = TelegramSender()
    result = sender.send(mock_user, "텔레그램 테스트", "본문입니다.")
    
    assert result is True
    mock_post.assert_called_once()
    

def test_telegram_sender_no_id():
    """텔레그램 ID가 없는 유저의 경우 실패 처리 테스트"""
    # telegram_id가 없는 유저 생성
    user_no_tg = User(
        name="노텔레그램",
        email="test@example.com",
        keywords=[],
        telegram_id=None,
        channels=["telegram"]
    )
    sender = TelegramSender()
    result = sender.send(user_no_tg, "제목", "내용")
    
    assert result is False


@patch("requests.post")
@patch("os.getenv")
def test_telegram_sender_send_to_chat_id(mock_getenv, mock_post):
    """운영 알림용 raw chat_id 전송 테스트"""
    mock_getenv.return_value = "dummy_token"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    sender = TelegramSender()
    result = sender.send_to_chat_id("999", "운영 알림", "본문")

    assert result is True
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["chat_id"] == "999"
