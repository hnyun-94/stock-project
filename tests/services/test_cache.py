"""
TTLCache 단위 테스트 모듈.

src/utils/cache.py의 TTLCache 클래스가 올바르게 동작하는지 검증합니다.
- 기본 set/get 동작
- TTL 만료
- max_size 제한 및 eviction
- clear 동작

[Task 6.17, REQ-Q03]
"""

import time
import unittest
from unittest.mock import patch


class TestTTLCache(unittest.TestCase):
    """TTLCache 클래스 단위 테스트."""

    def setUp(self):
        """각 테스트 전에 새 캐시 인스턴스 생성."""
        # src.utils.logger 모듈의 global_logger를 Mock으로 대체
        with patch.dict('sys.modules', {'src.utils.logger': unittest.mock.MagicMock()}):
            from src.utils.cache import TTLCache
            self.TTLCache = TTLCache
        self.cache = self.TTLCache(default_ttl=10, max_size=3)

    def test_set_and_get(self):
        """기본 set/get 동작 검증."""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_get_nonexistent_key(self):
        """존재하지 않는 키 조회 시 None 반환."""
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_ttl_expiration(self):
        """TTL 만료 후 None 반환 검증."""
        self.cache.set("key1", "value1", ttl=0)
        # monotonic 시간이 경과하면 만료
        time.sleep(0.01)
        self.assertIsNone(self.cache.get("key1"))

    def test_custom_ttl(self):
        """항목별 커스텀 TTL 설정 검증."""
        self.cache.set("key1", "value1", ttl=100)
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_max_size_eviction(self):
        """max_size 초과 시 가장 오래된 항목 제거."""
        self.cache.set("a", 1, ttl=10)
        self.cache.set("b", 2, ttl=20)
        self.cache.set("c", 3, ttl=30)
        # 4번째 삽입 → max_size=3이므로 가장 먼저 만료되는 "a" 제거
        self.cache.set("d", 4, ttl=40)
        self.assertIsNone(self.cache.get("a"))
        self.assertEqual(self.cache.get("d"), 4)

    def test_overwrite_existing_key(self):
        """같은 키에 값 덮어쓰기 시 max_size 증가하지 않음."""
        self.cache.set("key1", "v1")
        self.cache.set("key1", "v2")
        self.assertEqual(self.cache.get("key1"), "v2")
        self.assertEqual(self.cache.size, 1)

    def test_clear(self):
        """clear() 호출 시 모든 항목 삭제."""
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.clear()
        self.assertEqual(self.cache.size, 0)
        self.assertIsNone(self.cache.get("a"))

    def test_size_property(self):
        """size 프로퍼티 정확성 검증."""
        self.assertEqual(self.cache.size, 0)
        self.cache.set("a", 1)
        self.assertEqual(self.cache.size, 1)
        self.cache.set("b", 2)
        self.assertEqual(self.cache.size, 2)


if __name__ == "__main__":
    unittest.main()
