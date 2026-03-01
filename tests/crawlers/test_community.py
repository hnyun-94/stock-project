import pytest
from src.models import CommunityPost
from src.crawlers.community import get_popular_stocks, get_naver_board_posts, get_dc_stock_gallery, get_reddit_wallstreetbets

"""
이 모듈은 커뮤니티 크롤링 함수들의 비동기 테스트 케이스를 포함합니다.

주요 역할:
    - `src.crawlers.community` 모듈에 정의된 크롤러 함수들이 예상된 데이터 형식(딕셔너리 또는 CommunityPost DTO)으로 데이터를 올바르게 반환하는지 검증합니다.
    - 특히, 각 크롤러가 수집한 데이터의 타입, 구조, 그리고 특정 필드의 존재 여부 등을 확인합니다.
    - pytest 프레임워크와 `pytest-asyncio` 플러그인을 사용하여 비동기 함수를 테스트합니다.
"""

@pytest.mark.asyncio
async def test_get_popular_stocks_returns_dicts():
    """
    `get_popular_stocks` 함수가 인기 종목 데이터를 올바른 형식(딕셔너리 리스트)으로 반환하는지 비동기적으로 테스트합니다.

    역할:
        - `get_popular_stocks` 함수를 호출하여 반환된 데이터가 리스트 타입인지 확인합니다.
        - 리스트의 각 요소가 딕셔너리 타입이며, 'name' 및 'code' 키를 포함하는지 검증합니다.

    입력:
        없음. 이 테스트 함수는 직접적인 입력을 받지 않습니다.

    반환값:
        없음. (pytest의 assert 문을 통해 검증하며, 실패 시 예외 발생)

    예시:
        `stocks` 변수에 다음과 유사한 형태의 데이터가 반환될 것으로 예상합니다:
        [
            {"name": "삼성전자", "code": "005930"},
            {"name": "SK하이닉스", "code": "000660"},
            ...
        ]
    """
    stocks = await get_popular_stocks()
    assert isinstance(stocks, list)
    if stocks:
        assert isinstance(stocks[0], dict)
        assert "name" in stocks[0]
        assert "code" in stocks[0]

@pytest.mark.asyncio
async def test_get_naver_board_posts_returns_dto():
    """
    `get_naver_board_posts` 함수가 네이버 종목토론방 게시글을 `CommunityPost` DTO 리스트로 올바르게 반환하는지 비동기적으로 테스트합니다.

    역할:
        - 특정 종목 코드와 이름을 사용하여 `get_naver_board_posts` 함수를 호출합니다.
        - 반환된 데이터가 `CommunityPost` DTO의 리스트이며, 개수가 `max_items`를 초과하지 않는지 확인합니다.
        - 각 `CommunityPost` 객체의 'title' 및 'link' 속성이 예상된 값을 포함하는지 검증합니다.

    입력:
        없음. 이 테스트 함수는 직접적인 입력을 받지 않습니다.
        (내부적으로 `get_naver_board_posts("005930", "삼성전자", max_items=2)`를 호출합니다.)

    반환값:
        없음. (pytest의 assert 문을 통해 검증하며, 실패 시 예외 발생)

    예시:
        `posts` 변수에 다음과 유사한 형태의 데이터가 반환될 것으로 예상합니다:
        [
            CommunityPost(title="[삼성전자] 좋은 소식", link="https://finance.naver.com/...", ...),
            CommunityPost(title="[삼성전자] 주가 전망", link="https://finance.naver.com/...", ...),
        ]
    """
    # 005930(삼성전자) 테스트
    posts = await get_naver_board_posts("005930", "삼성전자", max_items=2)
    assert isinstance(posts, list)
    assert len(posts) <= 2
    
    if posts:
        post = posts[0]
        assert isinstance(post, CommunityPost)
        assert "[삼성전자]" in post.title
        assert "naver.com" in post.link

@pytest.mark.asyncio
async def test_get_dc_stock_gallery_returns_dto():
    """
    `get_dc_stock_gallery` 함수가 디시인사이드 주식 갤러리 게시글을 `CommunityPost` DTO 리스트로 올바르게 반환하는지 비동기적으로 테스트합니다.

    역할:
        - `get_dc_stock_gallery` 함수를 호출하여 반환된 데이터가 `CommunityPost` DTO의 리스트이며, 개수가 `max_items`를 초과하지 않는지 확인합니다.
        - 각 `CommunityPost` 객체의 'title' 및 'link' 속성이 예상된 값을 포함하는지 검증합니다.

    입력:
        없음. 이 테스트 함수는 직접적인 입력을 받지 않습니다.
        (내부적으로 `get_dc_stock_gallery(max_items=2)`를 호출합니다.)

    반환값:
        없음. (pytest의 assert 문을 통해 검증하며, 실패 시 예외 발생)

    예시:
        `posts` 변수에 다음과 유사한 형태의 데이터가 반환될 것으로 예상합니다:
        [
            CommunityPost(title="[식갤] 오늘의 매매일지", link="https://gall.dcinside.com/...", ...),
            CommunityPost(title="[식갤] 주갤 질문", link="https://gall.dcinside.com/...", ...),
        ]
    """
    posts = await get_dc_stock_gallery(max_items=2)
    assert isinstance(posts, list)
    assert len(posts) <= 2
    
    if posts:
        post = posts[0]
        assert isinstance(post, CommunityPost)
        assert "[식갤]" in post.title
        assert "gall.dcinside.com" in post.link

@pytest.mark.asyncio
async def test_get_reddit_wallstreetbets():
    """
    `get_reddit_wallstreetbets` 함수가 레딧 WallStreetBets 게시글을 `CommunityPost` DTO 리스트로 올바르게 반환하는지 비동기적으로 테스트합니다.

    역할:
        - `get_reddit_wallstreetbets` 함수를 호출하여 반환된 데이터가 `CommunityPost` DTO의 리스트이며, 개수가 `max_items`를 초과하지 않는지 확인합니다.
        - 각 `CommunityPost` 객체의 'title' 및 'link' 속성이 예상된 값을 포함하는지 검증합니다.

    입력:
        없음. 이 테스트 함수는 직접적인 입력을 받지 않습니다.
        (내부적으로 `get_reddit_wallstreetbets(max_items=2)`를 호출합니다.)

    반환값:
        없음. (pytest의 assert 문을 통해 검증하며, 실패 시 예외 발생)

    예시:
        `posts` 변수에 다음과 유사한 형태의 데이터가 반환될 것으로 예상합니다:
        [
            CommunityPost(title="[WSB] GME to the moon!", link="https://www.reddit.com/...", ...),
            CommunityPost(title="[WSB] YOLO trade update", link="https://www.reddit.com/...", ...),
        ]
    """
    posts = await get_reddit_wallstreetbets(max_items=2)
    assert isinstance(posts, list)
    assert len(posts) <= 2
    
    if posts:
        post = posts[0]
        assert isinstance(post, CommunityPost)
        assert "[WSB" in post.title
        assert "reddit.com" in post.link
