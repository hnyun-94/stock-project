"""
공통 데이터 트랜스퍼 오브젝트(DTO) 모듈.

크롤러, 서비스, 이메일 시스템 간 데이터의 명확한 구조와
타입 안전성 확보를 위해 dataclass 패턴을 사용합니다.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class NewsArticle:
    """뉴스와 관련된 기사 정보를 담는 데이터 모델."""
    title: str
    link: str
    summary: Optional[str] = None
    date: Optional[str] = None

@dataclass
class MarketIndex:
    """증시 지표(코스피, 코스닥 등)와 투자자 동향을 담는 데이터 모델."""
    name: str                   # 지수 이름 (예: KOSPI)
    value: str                  # 지수 값 (예: 2,500.12)
    change: str                 # 변동폭 (예: +12.34)
    investor_summary: str = ""  # 투자 주체별 거래 동향

@dataclass
class CommunityPost:
    """커뮤니티(종토방, 디시인사이드) 등의 게시글 정보를 담는 데이터 모델."""
    title: str
    link: str
    views: Optional[str] = None
    likes: Optional[str] = None

@dataclass
class SearchTrend:
    """구글 및 주요 포털의 검색어 트렌드 정보를 담는 데이터 모델."""
    keyword: str
    traffic: Optional[str] = None
    news_title: Optional[str] = None
    news_link: Optional[str] = None

@dataclass
class User:
    """주식 리포트 수신 대상자 정보를 담는 데이터 모델."""
    name: str
    email: str
    keywords: list[str]
    telegram_id: Optional[str] = None
    channels: list[str] = None
    holdings: list[str] = None
    alert_threshold: Optional[float] = None

    def __post_init__(self):
        if self.channels is None:
            self.channels = ["email"]
        if self.holdings is None:
            self.holdings = []
