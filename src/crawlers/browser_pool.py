import asyncio
from playwright.async_api import async_playwright
from src.utils.logger import global_logger

class BrowserPool:
    """
    Playwright 기반 동적 크롤링 최적화를 위한 브라우저 풀/싱글톤 관리 스레드
    요청마다 Chromium 인스턴스를 띄우는 렌더링 부하를 막기 위해
    최초 1회만 브라우저를 띄워두고(Warm Start) 컨텍스트만 재활용합니다.
    """
    _playwright = None
    _browser = None

    @classmethod
    async def get_browser(cls):
        """싱글톤 브라우저 인스턴스를 반환하며, 죽었을 경우 다시 살립니다."""
        if cls._browser is None or not cls._browser.is_connected():
            global_logger.info("새 렌더링 브라우저 인스턴스(Chromium)를 할당합니다...")
            if cls._playwright is None:
                cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(headless=True)
        return cls._browser

    @classmethod
    async def cleanup(cls):
        """메인 애플리케이션 종료 시 자원을 회수합니다."""
        if cls._browser:
            await cls._browser.close()
            cls._browser = None
        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None
        global_logger.info("모든 백그라운드 브라우저 자원이 해제되었습니다.")
