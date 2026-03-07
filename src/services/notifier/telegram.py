"""
이 모듈은 Telegram Bot API를 활용하여 사용자에게 텔레그램 알림을 전송하는 기능을 제공합니다.
`NotificationSender` 인터페이스를 구현하며, 텔레그램 봇 토큰 및 사용자 ID를 사용하여
텍스트 기반의 알림 메시지를 푸시하는 역할을 담당합니다.
주로 알림 시스템의 텔레그램 채널 통합을 위해 사용됩니다.
"""

import os
import requests

from src.models import User
from src.services.notifier.base import NotificationSender
from src.utils.logger import global_logger

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

        # 파도(물결) 등 마크다운 충돌 문자를 우회하려면 단순 HTML 송신 모드도 좋습니다. 
        # 여기서는 주식 리포트가 markdown 문법이 섞여올 확률이 높으므로 MarkdownV2를 쓰거나 
        # 안전한 HTML 파싱을 지원하는 방식으로 전송합니다. 본 프로젝트는 이메일 위주로 설계되었으므로,
        # 텔레그램 발송 시엔 텍스트 길이나 마크다운 문제 최소화를 위해 기본 Markdown 속성을 사용합니다.
        
        # 텔레그램 메시지는 제목+본문을 하나의 텍스트로 결합
        message = f"📢 {subject}\n\n{content}"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"  # AI_Summarizer의 출력을 HTML로 포맷팅해서 보내도 됩니다. 
                                  # 하지만 여기선 간단히 전송 시 에러를 막기위해 None 혹은 명확한 텍스트로 보냅니다.
                                  # 일단 에러 회피를 위해 옵션을 제외하거나, 내용의 특수문자를 감안해야 합니다.
        }
        # 안전을 위해 parse_mode 없이 단순 String으로 던집니다. (이후 고도화 시 개선 가능)
        del payload["parse_mode"]
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                global_logger.info(f"[TelegramSender] 텔레그램 발송 완료: {chat_id}")
                return True
            else:
                global_logger.info(f"[TelegramSender] 텔레그램 발송 실패 ({chat_id}): HTTP {response.status_code} - {response.text}")
                return False
        except Exception as e:
            global_logger.info(f"[TelegramSender] 요청 중 예외 발생 ({chat_id}): {e}")
            return False
