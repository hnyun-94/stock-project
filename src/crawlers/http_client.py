"""
HTTP 클라이언트 세션 싱글톤 모듈.

이 모듈은 모든 크롤러가 공유하는 단일 aiohttp.ClientSession 인스턴스를 관리합니다.
매번 새 세션을 생성/파괴하면 DNS 조회 → TCP 핸드셰이크 → TLS 협상이 반복되어
전체 파이프라인의 20~40%가 커넥션 오버헤드로 소비됩니다.

싱글톤 패턴으로 세션을 재사용하면 커넥션 풀링(connection pooling) 효과를 얻어
크롤링 전체 시간을 20~40% 단축할 수 있습니다.

사용법:
    from src.crawlers.http_client import get_session, close_session

    # 크롤러 함수 내부에서
    session = await get_session()
    async with session.get(url, headers=headers) as response:
        ...

    # 파이프라인 종료 시 (main.py finally 블록)
    await close_session()

[Task 6.1, REQ-P01]
"""

import aiohttp
from src.utils.logger import global_logger

# 모듈 레벨 글로벌 세션 변수
_session: aiohttp.ClientSession | None = None

# 모든 크롤러가 공유하는 기본 헤더와 타임아웃 설정
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )
}
_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)


async def get_session() -> aiohttp.ClientSession:
    """글로벌 싱글톤 ClientSession을 반환합니다.

    세션이 아직 존재하지 않거나, 이전에 close되어 닫힌 상태라면
    자동으로 새 세션을 생성하여 반환합니다.

    Returns:
        aiohttp.ClientSession: 재사용 가능한 HTTP 클라이언트 세션

    Note:
        이 함수는 반드시 async 컨텍스트 내에서 호출해야 합니다.
        aiohttp.ClientSession은 이벤트 루프가 활성화된 상태에서만 생성 가능합니다.
    """
    global _session

    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            headers=_DEFAULT_HEADERS,
            timeout=_DEFAULT_TIMEOUT,
        )
        global_logger.info("🌐 [HTTP] 글로벌 ClientSession이 생성되었습니다. (커넥션 풀링 활성화)")

    return _session


async def close_session() -> None:
    """글로벌 ClientSession을 안전하게 종료합니다.

    파이프라인 실행이 완료된 후 반드시 호출하여 열린 소켓과 리소스를 정리합니다.
    이미 닫혀 있거나 존재하지 않는 경우 아무 동작도 하지 않습니다.
    """
    global _session

    if _session is not None and not _session.closed:
        await _session.close()
        global_logger.info("🔒 [HTTP] 글로벌 ClientSession이 정상 종료되었습니다.")

    _session = None
