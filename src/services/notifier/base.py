from abc import ABC, abstractmethod
from src.models import User

class NotificationSender(ABC):
    """
    모든 알림 전송 채널(이메일, 카카오톡, 텔레그램 등)이 공통으로
    구현해야 하는 인터페이스 설계 규약입니다. (Strategy Pattern)
    """

    @abstractmethod
    def send(self, user: User, subject: str, content: str) -> bool:
        """
        알림을 사용자에게 전송합니다.

        역할 (Role):
            주어진 사용자 객체에 설정된 정보를 바탕으로 특정 채널(이메일, 텔레그램 등)을 통해 
            주식 요약 리포트나 알림 메시지를 전송하는 공통 추상 메서드입니다.

        입력 (Input):
            user (User): 알림의 대상이 되는 사용자 객체. 사용자 이름, 이메일, 텔레그램 ID 등을 포함합니다.
            subject (str): 알림 메시지의 제목 문자열. 예: "오늘의 주식 브리핑"
            content (str): 알림 메시지의 본문 내용. 채널에 따라 HTML 또는 Markdown 포맷 등이 될 수 있습니다.

        반환값 (Output / Returns):
            bool: 발송 성공 시 True, 실패 시 False를 반환합니다.
        """
        pass
