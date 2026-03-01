"""
시스템 전반의 로깅과 에러 트래킹 이벤트를 관리하는 모듈입니다.
파일 및 콘솔 로그 출력 설정, 그리고 텔레그램을 통한 치명적 에러 알림 웹훅 발송을 담당합니다.
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
import traceback
import datetime
import requests

def setup_logger(name: str = "main"):
    """
    역할 (Role):
        프로젝트 전반에서 사용할 중앙 로깅 시스템 초기화.
        콘솔 출력과 동시에 logging/YYYY-MM-DD.log 형태로 로테이팅 저장.

    입력 (Input):
        name (str): 로거의 이름. 기본값은 "main"

    반환값 (Output / Returns):
        logging.Logger: 설정이 완료된 로거 객체
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 핸들러 중복 추가 방지
    if not logger.handlers:
        # 1. 콘솔 핸들러
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # 2. 파일 핸들러 (매일 자정에 새로운 파일로)
        log_dir = "logging"
        os.makedirs(log_dir, exist_ok=True)
        # UTC 대신 KST 혹은 로컬 환경에 맞게 저장될 것 (TimedRotatingFileHandler 사용)
        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, "app.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        # 확장자를 YYYY-MM-DD.log 꼴로 남기기
        file_handler.suffix = "%Y-%m-%d.log"
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

global_logger = setup_logger("StockReport")

def send_error_webhook(err_msg: str):
    """
    역할 (Role):
        관리자용 텔레그램 채팅 채널로 치명적 에러 전문을 발송하는 웹훅 기능입니다.
    
    입력 (Input):
        err_msg (str): 발송할 에러 메시지 텍스트
        
    반환값 (Output / Returns):
        없음 (None)
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_chat_id = os.getenv("ADMIN_TELEGRAM_CHAT_ID")
    
    if not bot_token or not admin_chat_id:
        global_logger.warning("Telegram Bot Token 혹은 Admin Chat ID가 설정되지 않아 Webhook 발송 불가.")
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": admin_chat_id,
        "text": f"🚨 [주식 리포트 파이프라인 에러 알림]\n\n{err_msg}"
    }
    
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            global_logger.error(f"Telegram Webhook 전송 실패: {res.text}")
    except Exception as e:
        global_logger.error(f"Telegram Webhook 요청 중 자체 오류: {e}")

def log_critical_error(e: Exception, context: str = ""):
    """
    역할 (Role):
        예상치 못한 심각한 에러 발생 시,
        1) errorcase 폴더에 파일로 Traceback 저장
        2) 텔레그램 웹훅으로 관리자 호출
        3) global_logger에 에러 기록
        
    입력 (Input):
        e (Exception): 잡힌 예외(Exception) 객체
        context (str): 에러가 발생한 상황이나 맥락을 설명하는 문자열
        
    반환값 (Output / Returns):
        없음 (None)
    """
    tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    global_logger.error(f"[{context}] 치명적 오류 발생:\n{tb_str}")
    
    # 1. errorcase 파일 생성
    error_dir = "errorcase"
    os.makedirs(error_dir, exist_ok=True)
    err_file_path = os.path.join(error_dir, f"{now_str}_error.md")
    
    content = f"""# 🚨 System Critical Error Log

## 시간 정보
- 발생 시각: {now_str}

## 발생 컨텍스트
- {context}

## 에러 내용 (Traceback)
```python
{tb_str}
```
"""
    try:
        with open(err_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        global_logger.info(f"에러 로그가 {err_file_path} 에 저장되었습니다.")
    except Exception as io_e:
        global_logger.error(f"에러 파일 작성 중 실패: {io_e}")
        
    # 2. Webhook 발송
    webhook_msg = f"컨텍스트: {context}\n에러 정보:\n{str(e)}\n\n(상세 Traceback은 서버의 errorcase/{os.path.basename(err_file_path)} 참고)"
    send_error_webhook(webhook_msg)
