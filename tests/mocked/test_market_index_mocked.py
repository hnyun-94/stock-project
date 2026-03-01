"""
이 모듈은 src.crawlers.market_index 모듈의 get_market_indices 함수에 대한 단위 테스트를 포함합니다.
네이버 금융 페이지에서 시장 지수 및 투자자 동향 데이터를 올바르게 크롤링하고 파싱하는지 확인하기 위해
aiohttp.ClientSession.get 호출을 모의(mock)하여 실제 네트워크 요청 없이 테스트를 수행합니다.
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.crawlers.market_index import get_market_indices
from src.models import MarketIndex

@pytest.mark.asyncio
async def test_get_market_indices_mocked(mocker):
    """
    get_market_indices 함수가 네이버 금융에서 KOSPI 및 KOSDAQ 시장 지수와 투자자 동향 데이터를
    올바르게 크롤링하고 파싱하는지 테스트합니다.
    aiohttp.ClientSession.get 호출을 모의(mock)하여 실제 네트워크 요청 없이 미리 정의된 HTML 응답을 사용합니다.

    역할:
        - get_market_indices 함수가 모의된(mocked) 네트워크 응답을 사용하여 정확하게 작동하는지 검증합니다.
        - KOSPI와 KOSDAQ 지수 값 및 투자자별 매매 동향 요약이 올바르게 추출되는지 확인합니다.

    입력:
        mocker (pytest_mock.plugin.MockerFixture):
            pytest-mock 플러그인에서 제공하는 fixture로, 테스트 중 객체를 쉽게 모의(mock)할 수 있도록 합니다.
            이 테스트에서는 aiohttp.ClientSession.get 메서드를 모의하는 데 사용됩니다.
            예시: `mocker.patch("aiohttp.ClientSession.get", ...)`

    반환값:
        None:
            이 함수는 어설션(assertion)을 통해 테스트 성공/실패를 판단하며, 값을 반환하지 않습니다.
    """
    # Mock response classes
    class MockResponse:
        """
        aiohttp.ClientResponse 객체를 모의(mock)하기 위한 클래스입니다.
        테스트에서 aiohttp.ClientSession.get 호출 시 이 객체를 반환하여,
        미리 정의된 HTML 콘텐츠와 상태 코드를 제공합니다.
        비동기 컨텍스트 관리자(async context manager) 역할을 수행합니다.
        """
        def __init__(self, text_data, status=200):
            """
            MockResponse 객체를 초기화합니다. 모의할 텍스트 데이터와 HTTP 상태 코드를 설정합니다.

            역할:
                - MockResponse 인스턴스를 생성하고, 응답 본문 텍스트와 HTTP 상태를 설정합니다.

            입력:
                self (MockResponse):
                    객체 인스턴스 자신.
                text_data (str):
                    응답 본문으로 반환될 HTML 텍스트 데이터.
                    예시: `mock_home_html`, `mock_market_html`
                status (int, optional):
                    HTTP 상태 코드. 기본값은 200.
                    예시: `200`, `404`, `500`

            반환값:
                None
            """
            self._text_data = text_data
            self.status = status
            
        def raise_for_status(self):
            """
            HTTP 상태 코드가 200이 아닐 경우 예외를 발생시킵니다.
            aiohttp.ClientResponse의 raise_for_status 메서드를 모방합니다.

            역할:
                - 모의된 응답의 HTTP 상태를 확인하고, 문제가 있으면 예외를 발생시킵니다.

            입력:
                self (MockResponse):
                    객체 인스턴스 자신.

            반환값:
                None: 예외가 발생하지 않으면 아무것도 반환하지 않습니다.

            예외:
                Exception: HTTP 상태 코드가 200이 아닐 경우 발생합니다.
            """
            if self.status != 200:
                raise Exception(f"HTTP Error {self.status}")
                
        async def text(self, encoding=None):
            """
            응답 본문의 텍스트 데이터를 비동기적으로 반환합니다.
            aiohttp.ClientResponse의 text 메서드를 모방합니다.

            역할:
                - 모의된 응답 본문 텍스트를 제공합니다.

            입력:
                self (MockResponse):
                    객체 인스턴스 자신.
                encoding (str, optional):
                    텍스트 인코딩. 이 모의 객체에서는 사용되지 않지만,
                    원래 함수의 시그니처를 유지하기 위해 포함됩니다. 기본값은 `None`.

            반환값:
                str:
                    초기화 시 제공된 HTML 텍스트 데이터.
                    예시: `"<html>...</html>"`
            """
            return self._text_data

        async def __aenter__(self):
            """
            비동기 컨텍스트 관리자(async with 문) 진입 시 호출됩니다.
            현재 MockResponse 인스턴스를 반환하여 `async with` 문에서 사용될 수 있도록 합니다.

            역할:
                - `async with MockResponse(...) as resp:` 구문에서 `resp` 변수에 현재 인스턴스를 할당합니다.

            입력:
                self (MockResponse):
                    객체 인스턴스 자신.

            반환값:
                MockResponse:
                    현재 MockResponse 인스턴스.
                    예시: `self`
            """
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            """
            비동기 컨텍스트 관리자(async with 문) 종료 시 호출됩니다.
            이 모의 객체에서는 특별한 정리 작업이 필요 없으므로 아무것도 하지 않습니다.

            역할:
                - `async with` 블록이 끝날 때 호출되며, 필요한 경우 자원을 정리합니다.
                  이 모의 구현에서는 특별한 정리가 필요 없습니다.

            입력:
                self (MockResponse):
                    객체 인스턴스 자신.
                exc_type (type, optional):
                    `async with` 블록 내에서 발생한 예외의 타입.
                exc_val (Exception, optional):
                    `async with` 블록 내에서 발생한 예외의 값.
                exc_tb (traceback, optional):
                    `async with` 블록 내에서 발생한 예외의 트레이스백.

            반환값:
                None
            """
            pass

    mock_home_html = '''
    <div class="kospi_area">
        <div class="num_quot"><span class="num">2,500.00</span><span class="blind">상승</span></div>
    </div>
    <div class="kosdaq_area">
        <div class="num_quot"><span class="num">850.00</span><span class="blind">하락</span></div>
    </div>
    '''
    
    mock_market_html = '''
    <div class="graph_nav_area">
        <ul class="nav_lst">
            <li><span>개인</span><span class="num">1,000억</span></li>
            <li><span>외국인</span><span class="num">-500억</span></li>
            <li><span>기관</span><span class="num">-400억</span></li>
        </ul>
    </div>
    '''

    # mocker.patch aiohttp.ClientSession.get to return MockResponse based on URL
    async def mock_get(url, *args, **kwargs):
        if url == "https://finance.naver.com/":
            return MockResponse(mock_home_html)
        elif url == "https://finance.naver.com/marketindex/":
            return MockResponse(mock_market_html)
        return MockResponse("")

    with patch("aiohttp.ClientSession.get", new_callable=lambda: mock_get):
        indices = await get_market_indices()
        
        assert len(indices) == 2
        
        kospi = next(i for i in indices if i.name == "KOSPI")
        assert kospi.value == "2,500.00 상승"
        assert "개인: 1,000억" in kospi.investor_summary
        
        kosdaq = next(i for i in indices if i.name == "KOSDAQ")
        assert kosdaq.value == "850.00 하락"
        assert "외국인: -500억" in kosdaq.investor_summary
