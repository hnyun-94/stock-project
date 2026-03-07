import time
import asyncio
from functools import wraps
from src.utils.logger import global_logger


def async_circuit_breaker(
    failure_threshold: int = 3,
    recovery_timeout: int = 60,
    fallback_value=None,
    non_trip_exceptions=(),
):
    """
    역할 (Role):
        비동기 네트워크 I/O나 API 호출에서 간헐적 장애가 아닌 "장기적/영구적 장애"를 감지했을 경우,
        해당 함수를 계속 재시도하지 않고 차단(Open)하여 시스템 전체의 지연(Hang)을 방지하는 서킷 브레이커 데코레이터입니다.
    
    입력 (Input):
        failure_threshold (int): 실패가 연속으로 이 횟수만큼 발생하면 서킷을 엽니다(Open).
        recovery_timeout (int): 서킷 개방 후 다시 시도해볼 때(Half-Open)까지 대기하는 초(seconds).
        fallback_value (Any): 서킷이 열렸을 때 에러를 뿜지 않고 시스템 보호를 위해 대신 반환할 기본값이나 함수 콜백입니다.
        non_trip_exceptions (tuple[type[BaseException], ...]): 서킷 실패 카운트에서 제외할 예외 타입 묶음입니다.
    """
    def decorator(func):
        state = {
            'fail_count': 0,
            'is_open': False,
            'last_failure_time': None
        }

        @wraps(func)
        async def wrapper(*args, **kwargs):
            now = time.time()
            
            # 서킷 오픈 상태 즉각 차단 (Fail Fast)
            if state['is_open']:
                if now - state['last_failure_time'] > recovery_timeout:
                    global_logger.info(f"[CircuitBreaker] '{func.__name__}' Half-Open (복구 시도)")
                    state['is_open'] = False
                else:
                    global_logger.warning(f"[CircuitBreaker] '{func.__name__}' Call Blocked (Circuit Open). Returning Fallback.")
                    return fallback_value() if callable(fallback_value) else fallback_value

            try:
                result = await func(*args, **kwargs)
                if state['fail_count'] > 0:
                    state['fail_count'] = 0  # 성공 시 리셋 (Closed)
                return result
                
            except Exception as e:
                if non_trip_exceptions and isinstance(e, non_trip_exceptions):
                    global_logger.warning(
                        f"[CircuitBreaker] '{func.__name__}' Non-trip exception detected: {e}"
                    )
                    raise e

                state['fail_count'] += 1
                state['last_failure_time'] = time.time()
                global_logger.error(f"[CircuitBreaker] '{func.__name__}' Failed (누적 {state['fail_count']}/{failure_threshold}): {e}")
                
                # 임계치를 초과하면 서킷 오픈
                if state['fail_count'] >= failure_threshold:
                    if not state['is_open']:
                        global_logger.critical(f"🔥 [CircuitBreaker] '{func.__name__}' 연속 실패 임계치 도달. 기능을 차단(Open)합니다.")
                    state['is_open'] = True
                    return fallback_value() if callable(fallback_value) else fallback_value
                
                # 아직 임계치 도달 전이면 예외를 그대로 던져서 Tenacity 등이 재시도하게 둠
                raise e

        return wrapper
    return decorator
