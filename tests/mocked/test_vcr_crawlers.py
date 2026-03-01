import pytest
import vcr
from src.crawlers.naver_news import get_market_news

# VCR 환경 설정: HTTP 응답 결과를 녹화(Record)하여 저장할 서브 디렉토리 지정
my_vcr = vcr.VCR(
    cassette_library_dir='tests/mocked/cassettes',
    # 'once': 한번 녹화한 파일이 있으면 실제 요청(Network)을 보내지 않고 무조건 재사용
    record_mode='once',
    match_on=['uri', 'method'],
)

@pytest.mark.asyncio
@my_vcr.use_cassette('naver_market_news.yaml')
async def test_get_market_news_with_vcr():
    """
    역할 (Role):
        vcrpy 모듈을 이용한 HTTP 네트워크 테스팅 고도화 데모 시나리오 파일.
        네이버 등 외부 API/웹 요청 시 1회차엔 실제 통신하여 '카세트(yaml)' 파일로 저장하고,
        이후 CI/CD 및 단위테스트부터는 인터넷 연결 없이도 가짜(녹화본) 응답을 반환하여 
        100% 독립된 안정성 테스트(멱등성)를 통과하게 만듭니다.
    """
    
    # 이 부분은 VCR 테이프가 없으면 진짜 HTTP 요청을 하고, 있으면 Yaml을 파싱해 리턴합니다.
    news_list = await get_market_news()
    
    # 멱등성 보장 검증 (결과가 외부 상태 변화에 의해 깨지지 않음)
    assert len(news_list) > 0
    assert getattr(news_list[0], 'title', None) is not None
    # 네이버 스토어/뉴스 스크립트 도메인 포함 여부 등 유효성 점검
    assert "naver" in news_list[0].url or "news.naver" in news_list[0].url
