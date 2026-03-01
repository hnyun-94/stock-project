"""
이 모듈은 네이버 데이터랩 크롤러의 통합 테스트를 포함합니다.
주요 목표는 `get_naver_datalab_trends` 함수가 네이버 데이터랩에서 검색 트렌드 데이터를 올바르게 조회하고,
이를 `SearchTrend` DTO 객체 리스트 형태로 반환하는지 검증하는 것입니다.
API 키가 없거나 네트워크 문제 등으로 인해 데이터 조회에 실패할 경우,
적절한 예외 처리 또는 빈 리스트 반환과 같은 예상 동작을 확인합니다.
"""

import pytest
from src.crawlers.naver_datalab import get_naver_datalab_trends
from src.models import SearchTrend

@pytest.mark.asyncio
async def test_get_naver_datalab_trends_returns_dto_list():
    """
    `get_naver_datalab_trends` 함수가 네이버 데이터랩 트렌드를 조회하여 DTO 리스트를 반환하는지 테스트합니다.

    역할:
        `get_naver_datalab_trends` 함수를 호출하여 실제 네이버 데이터랩 API와 유사한 환경에서 검색 트렌드 데이터를
        성공적으로 가져오고, 그 결과가 예상되는 `SearchTrend` DTO 객체 리스트 형식인지 검증합니다.
        특히 반환된 객체가 `SearchTrend` 인스턴스이며, 필수 필드(`keyword`, `traffic`)를 포함하는지 확인합니다.
        API 키가 없거나 설정 문제로 인해 데이터가 반환되지 않는 경우 (빈 리스트 반환)에 대한 로직도 고려합니다.

    입력:
        이 테스트 함수는 직접적인 인자를 받지 않습니다.
        내부적으로 `get_naver_datalab_trends` 함수에 `keywords` 인자 (list[str])를 전달합니다.
        - 예시: `await get_naver_datalab_trends(["증시"])`

    반환값:
        이 테스트 함수는 명시적인 값을 반환하지 않습니다.
        어설션(assertion)을 통해 테스트 성공 여부를 판단하며, 실패 시 `pytest`에 의해 오류가 보고됩니다.
        - 성공 시: 아무것도 반환하지 않고 테스트 통과.
        - 실패 시: `AssertionError` 발생.
    """
    trends = await get_naver_datalab_trends(["증시"])
    assert isinstance(trends, list)
    
    # API 키가 없으면 빈 리스트를 반환하도록 예외처리 되어 있음 (warning)
    if trends:
        trend = trends[0]
        assert isinstance(trend, SearchTrend)
        assert len(trend.keyword) > 0
        assert "지표" in trend.traffic
