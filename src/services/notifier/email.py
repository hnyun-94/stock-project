"""
이 모듈은 이메일 발송 기능을 정의하고 구현합니다.
`NotificationSender` 추상 클래스를 상속받아 SMTP 프로토콜(주로 Gmail)을 통해
사용자에게 HTML 형식의 이메일 알림을 전송하는 `EmailSender` 클래스를 제공합니다.
환경 변수를 통해 발신자 계정 정보(SENDER_EMAIL, SENDER_APP_PASSWORD)를 설정하며,
주어진 콘텐츠를 HTML로 변환하여 발송하는 기능을 포함합니다.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.models import User
from src.services.notifier.base import NotificationSender
from src.utils.logger import global_logger
from src.utils.report_formatter import markdown_to_html

class EmailSender(NotificationSender):
    """
    SMTP 프로토콜(Gmail 기준)을 사용하여
    사용자에게 HTML 이메일을 발송하는 `NotificationSender` 구현체입니다.
    """
    
    def send(self, user: User, subject: str, content: str) -> bool:
        """
        역할 (Role):
            사용자의 이메일 주소를 확인하고, 설정된 발송자 계정으로 SMTP(Gmail) 서버를 통해
            사용자에게 리포트 내용을 메일로 전송합니다.
            콘텐츠가 마크다운 형식일 경우 자동으로 HTML로 변환하여 발송합니다.

        입력 (Input):
            user (User): 수신 대상 파라미터. `user.email` 속성이 필수로 요구됩니다.
                         이메일 주소가 없으면 발송하지 않습니다.
                         예: User(name="김철수", email="chulsoo@example.com")
            subject (str): 전송할 이메일의 제목입니다.
                           예: "[알림] 최신 주식 동향 요약 보고서"
            content (str): 이메일 본문 내용입니다. 마크다운 또는 HTML 문자열 형태로 제공될 수 있습니다.
                           HTML 형태가 아니면 내부적으로 `markdown_to_html` 함수를 사용하여 HTML로 포맷을 변환하여 발송합니다.
                           예: "# 주식 보고서\n\n오늘의 주요 뉴스...", "<html><body><h1>환영합니다</h1></body></html>"

        반환값 (Output / Returns):
            bool: 이메일 전송에 성공하면 True를 반환합니다.
                  다음과 같은 경우 실패(False)를 반환합니다:
                  - 수신자 `user` 객체에 유효한 이메일 주소가 없는 경우
                  - 발신자 계정 환경변수(SENDER_EMAIL, SENDER_APP_PASSWORD)가 누락된 경우
                  - SMTP 서버 연결 또는 메일 발송 중 예외(에러)가 발생한 경우
        """
        if not user.email:
            global_logger.info(f"[EmailSender] {user.name}님의 이메일 주소가 없습니다. 무시합니다.")
            return False

        sender_email = os.getenv("SENDER_EMAIL")
        app_password = os.getenv("SENDER_APP_PASSWORD")
        
        if not sender_email or not app_password:
            global_logger.info("[EmailSender] 발신자 계정 환경변수(SENDER_EMAIL, SENDER_APP_PASSWORD)가 누락되었습니다.")
            return False

        # 이메일 메시지 객체 생성
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = user.email
        
        # 본문(markdown) -> HTML 포매팅 적용
        html_content = markdown_to_html(content) if '<html' not in content else content
        part = MIMEText(html_content, "html", "utf-8")
        msg.attach(part)
        
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, app_password)
                server.send_message(msg)
            global_logger.info(f"[EmailSender] 이메일 발송 완료: {user.email}")
            return True
        except Exception as e:
            global_logger.info(f"[EmailSender] 이메일 발송 실패 ({user.email}): {e}")
            return False
