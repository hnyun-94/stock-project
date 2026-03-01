import asyncio
import os
import sys

# 상위 폴더 경로를 위해 Path 수정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.crawlers.market_index import get_market_indices
from src.services.user_manager import fetch_active_users
from src.services.notifier.telegram import TelegramSender
from src.utils.logger import global_logger, log_critical_error

async def check_thresholds():
    """사용자의 threshold 임계값을 읽고 현재 KOSPI 등락률이 그 이상 하락했다면 긴급 알림 수발신"""
    global_logger.info("🚨 [Alert Daemon] 시스템 긴급 하락 점검을 시작합니다.")
    indices = await get_market_indices()
    
    target_idx = "KOSPI" # 임의의 대표 비교 지수
    kospi_val = None
    kospi_change = None
    
    for idx in indices:
        if idx.name.upper() == target_idx:
            kospi_val = idx.value
            kospi_change = idx.change
            break
            
    if not kospi_change:
        global_logger.info("[Alert Daemon] 지수 데이터를 파싱하지 못했습니다.")
        return
        
    try:
        # e.g., "-3.5%" -> -3.5
        change_float = float(kospi_change.replace("%", "").strip())
    except Exception as e:
        global_logger.error(f"[Alert Daemon] 변화율 float 변환 에러: {e}")
        change_float = 0.0

    # 만약 코스피가 소량이라도 하락했으면 검사 대상이 됨
    if change_float < 0:
        users = fetch_active_users()
        telegram_sender = TelegramSender()
        for u in users:
            # Notion User 스키마에 alert_threshold 컬럼이 추가되었다고 가정, 없으면 -3.0%
            threshold = getattr(u, 'alert_threshold', -3.0) 
            if change_float <= threshold and "telegram" in u.channels:
                subject = f"🚨 [시장 비상 경보] {target_idx} 지수 {change_float}% 폭락"
                content = f"현재 **{target_idx} 지수가 {change_float}%를 기록**하며 설정하신 긴급 위험 임계점({threshold}%)을 돌파했습니다.\n({kospi_val} 포인트 진행 중)\n\n빠른 계좌 대응 및 포지션 확인을 권장합니다!"
                
                # 텔레그램 스레드로 즉각 푸시
                telegram_sender.send(u, subject, content)
                global_logger.critical(f"[Alert Daemon] {u.name}님에게 긴급 경보(Fast Track) 푸시 발송 완료.")

async def start_alert_daemon(interval_minutes: int = 15):
    """지정된 분 단위로 계속 루프를 돌며 API 변화를 관제하는 Fast Track Daemon"""
    global_logger.info(f"\n============================================\n### 🛡️ 긴급 시장 관제 데몬 가동 중 ({interval_minutes}분 주기) ###\n============================================")
    while True:
        try:
            await check_thresholds()
        except Exception as e:
            log_critical_error(e, "Alert Daemon 실시간 감시 중지 (재시도 대기)")
        await asyncio.sleep(interval_minutes * 60)

if __name__ == "__main__":
    # 개발 / 실행 모드일 경우 (단독 실행)
    asyncio.run(start_alert_daemon(5))
