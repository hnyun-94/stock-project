import asyncio
from typing import List
from src.models import User
from src.services.notifier.base import NotificationSender
from src.utils.logger import global_logger

class NotificationAction:
    def __init__(self, sender: NotificationSender, user: User, subject: str, content: str):
         self.sender = sender
         self.user = user
         self.subject = subject
         self.content = content

class MessageQueueWorker:
    """
    발송 채널 비동기 큐잉 시스템 (Phase 3 고도화)
    리포트 전송 규모가 수백 명으로 커질 경우 병목 현상을 방지하기 위해,
    이메일과 텔레그램 등의 발송 작업을 별도의 Queue에 담아 백그라운드 워커가 비동기적으로(또는 일괄) 처리합니다.
    """
    def __init__(self, concurrency: int = 5):
        self.queue = asyncio.Queue()
        self.concurrency = concurrency
        self._workers = []

    async def enqueue(self, action: NotificationAction):
        """새로운 발송 작업을 큐에 추가합니다."""
        await self.queue.put(action)
        
    async def _worker_loop(self, worker_id: int):
        """개별 워커 코루틴 - 큐에서 작업을 꺼내어 발송을 수행합니다."""
        while True:
            action = await self.queue.get()
            try:
                # CPU Bound인 이메일/소켓 통신 전송(SMTP 등)을 위해 asyncio.to_thread로 블로킹 해소 (필요시)
                # 여기서는 일단 sender.send가 동기 함수이므로 to_thread를 사용하여 비동기 논블로킹화 처리함.
                success = await asyncio.to_thread(
                    action.sender.send, 
                    action.user, 
                    action.subject, 
                    action.content
                )
                if not success:
                    global_logger.warning(f"[QueueWorker-{worker_id}] {action.user.name} 님에게 발송 실패.")
            except Exception as e:
                global_logger.error(f"[QueueWorker-{worker_id}] 작업 처리 중 예외 발생: {e}")
            finally:
                self.queue.task_done()

    def start_workers(self):
        """설정된 동시성 수준만큼 백그라운드 워커를 생성(실행)합니다."""
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker_loop(i))
            self._workers.append(task)
        global_logger.info(f"Message Queue Worker {self.concurrency}개가 시작되었습니다.")
            
    async def join(self):
        """큐에 담긴 모든 작업이 처리될 때까지 대기합니다."""
        await self.queue.join()
        
    def stop_workers(self):
        """모든 워커 코루틴을 취소(정지)시킵니다."""
        for task in self._workers:
            task.cancel()
        global_logger.info("Message Queue Worker들이 모두 정지되었습니다.")

# 글로벌 워커 인스턴스 (필요시 main.py에서 초기화하여 사용)
global_message_queue = MessageQueueWorker(concurrency=3)
