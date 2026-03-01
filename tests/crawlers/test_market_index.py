"""
이 모듈은 시장 지수 크롤러 (`src.crawlers.market_index.get_market_indices`)의 기능을 테스트합니다.

주요 역할은 `get_market_indices` 함수가 네이버 금융 웹사이트에서 코스피, 코스닥 등의 주요 시장 지수 데이터를
정확하게 가져오고, `MarketIndex` DTO (Data Transfer Object) 객체의 리스트 형태로 올바르게 반환하는지
비동기적으로 검증하는 것입니다. 반환되는 데이터의 타입, 구조, 그리고 각 DTO 객체의 필수 속성 및 유효성을
확인하여 데이터 크롤링 및 파싱 로직의 신뢰성을 보장합니다.
"""
import pytest
from src.models import MarketIndex
from src.crawlers.market_index import get_market_indices

@pytest.mark.asyncio
async def test_get_market_indices_returns_list_of_dto():
    """
    `get_market_indices` 함수가 네이버 금융에서 코스피, 코스닥 지수를 DTO 리스트로 가져오는지 비동기적으로 테스트합니다.

    역할:
        `get_market_indices` 함수를 호출하여 네이버 금융 우상단에 표시되는 시장 지수 데이터를 가져옵니다.
        가져온 데이터가 `MarketIndex` DTO 객체의 리스트 형태이며, 각 DTO가 올바른 속성을 가지고
        유효한 데이터를 포함하는지 검증합니다.

    입력:
        이 함수는 직접적인 입력 인자를 받지 않습니다.
        pytest 프레임워크에 의해 실행되며, 내부적으로 `get_market_indices` 함수를 호출합니다.

    반환값:
        이 함수는 명시적인 반환값을 가지지 않습니다.
        테스트 어설션(assert)이 모두 통과하면 테스트 성공으로 간주됩니다.
        - `isinstance(indices, list)`: 반환값이 리스트인지 확인
        - `len(indices) >= 1`: 반환된 리스트에 최소 1개 이상의 요소가 있는지 확인
        - `isinstance(index, MarketIndex)`: 리스트의 각 요소가 MarketIndex DTO 객체인지 확인
        - `hasattr(index, 'name')`, `hasattr(index, 'value')`, `hasattr(index, 'change')`, `hasattr(index, 'investor_summary')`:
          각 MarketIndex DTO가 필수 속성을 가지고 있는지 확인
        - `index.name in ["KOSPI", "KOSDAQ", "KOSPI200", "미국 USD", "WTI", "국제 금"]`:
          이름이 예상된 값 중 하나인지 확인
        - `index.value != "0"`: 값 필드가 "0"이 아닌 유효한 데이터를 포함하는지 확인
    """
    indices = await get_market_indices()
    
    # 반환값이 리스트여야 함
    assert isinstance(indices, list)
    
    # 2개(KOSPI, KOSDAQ)가 있거나 최소 1개가 존재해야 함 (웹 변경 등에 따라 유동적일 수 있으나 기본적으로 KOSPI는 있어야 함)
    assert len(indices) >= 1
    
    # 반환된 요소들이 MarketIndex DTO 객체인지 확인
    for index in indices:
        assert isinstance(index, MarketIndex)
        assert hasattr(index, 'name')
        assert hasattr(index, 'value')
        assert hasattr(index, 'change')
        assert hasattr(index, 'investor_summary')
        
        # 이름은 비어있지 않아야 함
        assert index.name in ["KOSPI", "KOSDAQ", "KOSPI200", "미국 USD", "WTI", "국제 금"]
        # 값도 비어있지 않아야 함 (네트워크 오류가 아니라면)
        assert index.value != "0"
