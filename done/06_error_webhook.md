# 4.1 Error Webhook 시스템 도입 (텔레그램)

## 개요

- 자동화된 스케줄러 환경 (Github Actions, Cron 등)에서 메인 파이프라인(`main.py`)이 오류를 발생시키거나 Rate Limit, API Key 등 환경적 요인으로 중단되었을 경우, 관리자(개발자)에게 즉각 알림을 주는 시스템이 필요함.

## 구현 방안

1. **텔레그램 개발자용 알림 (Error Alert)**
   - 이미 도입된 `telegram` 모듈을 연장선으로 활용하여, 봇이 관리자(운영자) ID를 타겟으로 예외 역추적(Traceback)과 에러 이유를 즉시 발송하는 전용 함수(`send_error_alert`) 구현.
2. **Global Exception Handler**
   - `main.py`의 최상위 `try-except` 블록 내에서 포괄적 예외(Exception)를 캐치하면, 해당 Webhook(또는 Telegram Error Sender)을 호출하게 처리.
3. **환경 변수 구분**
   - 사용자용 텔레그램 `CHAT_ID`와 별도로 관리자용 웹훅 채널(예: `ADMIN_TELEGRAM_CHAT_ID`)을 구성하여 분리 관리 가능성 확보.

## 완료 조건

- 파이프라인에서 고의로 발생시킨 예외 혹은 기타 장애 발생 시, 성공적으로 개발자의 텔레그램으로 로그 전문이 날아오는지 테스트 확인.
