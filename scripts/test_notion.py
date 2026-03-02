"""
이 모듈은 Notion 데이터베이스에서 활성 사용자 정보를 가져오는 기능을 테스트하고 시연합니다.
환경 변수 로드, 사용자 서비스 호출, 로깅을 포함하며, 가져온 사용자 정보를 콘솔에 상세히 출력하여
데이터 연동 및 객체 매핑이 올바르게 이루어지는지 확인합니다.
"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from src.services.user_manager import fetch_active_users
from src.utils.logger import global_logger

def test_notion():
    """
    Notion 데이터베이스에서 활성 사용자 정보를 가져와 콘솔에 출력합니다.

    이 함수는 `fetch_active_users` 서비스를 호출하여 Notion 데이터베이스에 저장된
    모든 활성 사용자 객체 리스트를 가져옵니다. 각 사용자 객체에서 이름, 채널, 이메일,
    텔레그램 ID, 관심 키워드, 보유 종목, 알림 임계치 등의 상세 정보를 추출하여
    콘솔에 보기 좋게 출력합니다. 테스트 시작과 종료 시 로거를 통해 알림을 기록합니다.

    역할:
        Notion DB 연동을 통한 활성 사용자 정보 조회 기능을 테스트하고,
        조회된 사용자 데이터를 콘솔에 시각적으로 표시합니다.

    입력:
        없음

    반환값:
        없음. (함수가 직접 값을 반환하지 않고, 모든 결과는 콘솔에 출력됩니다.)

    예시:
        >>> test_notion()
        # 콘솔에 다음과 유사한 정보가 출력됩니다.
        # 테스트 시작: Notion DB 사용자 정보 가져오기
        # 사용자 이름: 홍길동
        # 채널: ['뉴스', '주식']
        # 이메일: hong.gildong@example.com
        # 텔레그램 ID: 123456789
        # 관심 키워드: ['삼성전자', 'AI']
        # 보유 종목: ['005930']
        # 알림 임계치: 5.0
        # ------------------------------
        # 사용자 이름: 이순신
        # 채널: ['공지']
        # 이메일: lee.soonshin@example.com
        # 텔레그램 ID: 987654321
        # 관심 키워드: ['반도체']
        # 보유 종목: []
        # 알림 임계치: 3.0
        # ------------------------------
        # 테스트 종료: 총 2명 사용자 가져옴
    """
    global_logger.info("테스트 시작: Notion DB 사용자 정보 가져오기")
    users = fetch_active_users()
    for user in users:
        print(f"사용자 이름: {user.name}")
        print(f"채널: {user.channels}")
        print(f"이메일: {user.email}")
        print(f"텔레그램 ID: {user.telegram_id}")
        print(f"관심 키워드: {user.keywords}")
        print(f"보유 종목: {user.holdings}")
        print(f"알림 임계치: {user.alert_threshold}")
        print("-" * 30)
    global_logger.info(f"테스트 종료: 총 {len(users)}명 사용자 가져옴")

if __name__ == "__main__":
    test_notion()
