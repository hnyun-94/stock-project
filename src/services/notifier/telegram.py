"""
이 모듈은 Telegram Bot API를 활용하여 사용자에게 텔레그램 알림을 전송하는 기능을 제공합니다.
`NotificationSender` 인터페이스를 구현하며, 텔레그램 봇 토큰 및 사용자 ID를 사용하여
텍스트 기반의 알림 메시지를 푸시하는 역할을 담당합니다.
주로 알림 시스템의 텔레그램 채널 통합을 위해 사용됩니다.
"""

import os
from typing import List

import requests

from src.models import User
from src.services.notifier.base import NotificationSender
from src.utils.logger import global_logger


def _parse_positive_int_env(env_key: str, default_value: int) -> int:
    """Parses a positive integer env var and falls back on invalid input."""
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return default_value
    try:
        parsed = int(raw)
    except ValueError:
        global_logger.warning(
            "[TelegramSender] %s 값이 정수가 아닙니다: %s. 기본값 %s를 사용합니다.",
            env_key,
            raw,
            default_value,
        )
        return default_value
    return parsed if parsed > 0 else default_value


def _split_message(text: str, max_length: int) -> List[str]:
    """Splits a long Telegram message into safe chunks."""
    compact = (text or "").strip()
    if not compact:
        return [""]

    chunks: List[str] = []
    remaining = compact
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, max_length)
        if split_at < max_length // 2:
            split_at = remaining.rfind(" ", 0, max_length)
        if split_at < max_length // 2:
            split_at = max_length

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks


class TelegramSender(NotificationSender):
    """
    Telegram Bot API를 활용하여
    사용자의 개인 텔레그램 ID로 채널 단위의 무료 마크다운/텍스트 메세지를 푸시합니다.
    """

    def send(self, user: User, subject: str, content: str) -> bool:
        """User 객체의 telegram_id로 메시지를 전송합니다."""
        if not user.telegram_id:
            global_logger.info(f"[TelegramSender] {user.name}님의 텔레그램 ID가 설정되어 있지 않습니다.")
            return False

        return self.send_to_chat_id(user.telegram_id, subject, content)

    def send_to_chat_id(self, chat_id: str, subject: str, content: str) -> bool:
        """운영 알림처럼 raw chat_id만 있을 때 텔레그램 메시지를 전송합니다."""
        if not chat_id:
            global_logger.info("[TelegramSender] chat_id가 비어 있어 텔레그램 발송을 건너뜁니다.")
            return False

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            global_logger.info("[TelegramSender] 텔레그램 봇 토큰(TELEGRAM_BOT_TOKEN)이 설정되어 있지 않습니다.")
            return False

        message = f"📢 {subject}\n\n{content}"
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        timeout_seconds = _parse_positive_int_env(
            "TELEGRAM_REQUEST_TIMEOUT_SECONDS",
            10,
        )
        max_length = _parse_positive_int_env(
            "TELEGRAM_MESSAGE_MAX_LENGTH",
            3500,
        )
        chunks = _split_message(message, max_length)

        try:
            for index, chunk in enumerate(chunks, start=1):
                payload = {
                    "chat_id": chat_id,
                    "text": (
                        f"[{index}/{len(chunks)}] {chunk}"
                        if len(chunks) > 1
                        else chunk
                    ),
                }
                response = requests.post(
                    url,
                    json=payload,
                    timeout=timeout_seconds,
                )
                response.raise_for_status()

            global_logger.info(
                "[TelegramSender] 텔레그램 발송 완료: %s (chunks=%s)",
                chat_id,
                len(chunks),
            )
            return True
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", "n/a")
            body = getattr(response, "text", "")
            global_logger.warning(
                "[TelegramSender] 요청 실패 (%s): HTTP %s - %s",
                chat_id,
                status,
                body or exc,
            )
            return False
        except Exception as exc:  # pragma: no cover - defensive branch
            global_logger.warning(
                "[TelegramSender] 요청 중 예외 발생 (%s): %s",
                chat_id,
                exc,
            )
            return False
