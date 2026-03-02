"""
크롤링 결과 인메모리 TTL 캐시 모듈.

동일한 키워드로 여러 사용자의 뉴스를 크롤링할 때 중복 HTTP 요청을 방지합니다.
예: 사용자 A와 B가 모두 '삼성전자' 키워드를 등록한 경우, 첫 번째 크롤링 결과를
캐싱해두고 두 번째 사용자는 캐시에서 즉시 반환합니다.

TTL(Time To Live)을 설정하여 일정 시간이 지나면 자동으로 캐시가 만료됩니다.

사용법:
    from src.utils.cache import crawl_cache

    # 캐시 조회
    cached = crawl_cache.get("naver_news:삼성전자")
    if cached is not None:
        return cached

    # 크롤링 실행 후 캐시 저장
    result = await do_crawl(keyword)
    crawl_cache.set("naver_news:삼성전자", result)
    return result

[Task 6.8, REQ-F03]
"""

import time
from typing import Any, Optional, Dict, Tuple
from src.utils.logger import global_logger


class TTLCache:
    """시간 기반 만료(Time To Live)를 지원하는 인메모리 캐시.

    Attributes:
        default_ttl: 기본 캐시 유효 시간(초). 기본값 600초(10분).
        max_size: 최대 캐시 항목 수. 초과 시 가장 오래된 항목부터 제거.
    """

    def __init__(self, default_ttl: int = 600, max_size: int = 100):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값을 조회합니다.

        Args:
            key: 캐시 키 (예: "naver_news:삼성전자")

        Returns:
            캐시된 값. 만료되었거나 없으면 None.
        """
        if key not in self._store:
            return None

        value, expires_at = self._store[key]

        if time.monotonic() > expires_at:
            # 만료된 항목 제거
            del self._store[key]
            return None

        global_logger.debug(f"🎯 [Cache HIT] '{key}' 캐시 적중")
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """캐시에 값을 저장합니다.

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: 이 항목의 유효 시간(초). None이면 default_ttl 사용.
        """
        # 최대 크기 초과 시 가장 오래된 항목 제거
        if len(self._store) >= self.max_size and key not in self._store:
            self._evict_oldest()

        actual_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.monotonic() + actual_ttl
        self._store[key] = (value, expires_at)

    def _evict_oldest(self) -> None:
        """가장 먼저 만료되는 항목을 제거합니다."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]
        global_logger.debug(f"🗑️ [Cache EVICT] '{oldest_key}' 캐시 항목 제거 (용량 초과)")

    def clear(self) -> None:
        """모든 캐시를 삭제합니다."""
        self._store.clear()

    @property
    def size(self) -> int:
        """현재 캐시 항목 수를 반환합니다."""
        return len(self._store)


# 모듈 레벨 글로벌 캐시 인스턴스
# 파이프라인 1회 실행 동안 동일 키워드 크롤링 결과를 재사용합니다.
# TTL 600초(10분)는 뉴스 데이터의 신선도를 유지하면서 중복 요청을 방지하는 균형점입니다.
crawl_cache = TTLCache(default_ttl=600, max_size=100)
