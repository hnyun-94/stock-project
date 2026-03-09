"""
커뮤니티 입력 안전 필터 모듈.

역할:
1. 커뮤니티 소스 allowlist/blocklist 정책을 적용합니다.
2. 비속어, 혐오성 표현, 민감정보 패턴이 포함된 게시글 제목을 제거합니다.
3. 필터 결과를 구조화된 통계로 반환해 파이프라인이 안전하게 fallback 하도록 돕습니다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from src.models import CommunityPost


@dataclass(frozen=True)
class CommunitySourcePolicy:
    """커뮤니티 소스별 허용 정책과 병합 우선순위."""

    source_id: str
    enabled_by_default: bool = False
    merge_priority: int = 100
    allow_views: bool = False
    allow_likes: bool = False
    allow_comments: bool = False


_SOURCE_POLICIES = {
    "stockplus_insight": CommunitySourcePolicy(
        source_id="stockplus_insight",
        enabled_by_default=True,
        merge_priority=10,
        allow_views=True,
    ),
    "blind_stock_lounge": CommunitySourcePolicy(
        source_id="blind_stock_lounge",
        enabled_by_default=False,
        merge_priority=20,
        allow_views=True,
        allow_likes=True,
        allow_comments=True,
    ),
    "naver_board": CommunitySourcePolicy(
        source_id="naver_board",
        enabled_by_default=False,
        merge_priority=30,
    ),
    "reddit_wallstreetbets": CommunitySourcePolicy(
        source_id="reddit_wallstreetbets",
        enabled_by_default=True,
        merge_priority=40,
    ),
    "dc_stock_gallery": CommunitySourcePolicy(
        source_id="dc_stock_gallery",
        enabled_by_default=False,
        merge_priority=50,
    ),
}


# 기본 허용 소스는 보수적으로 유지하되, 집계형/비교적 안전한 소스만 최소 포함합니다.
DEFAULT_ENABLED_SOURCES = {
    source_id
    for source_id, policy in _SOURCE_POLICIES.items()
    if policy.enabled_by_default
}

_HIGH_RISK_KEYWORDS = {
    "씨발",
    "시발",
    "ㅅㅂ",
    "좆",
    "개새",
    "병신",
    "한녀",
    "한남",
    "페미",
    "능지",
    "죽여",
    "자살",
    "살인",
    "섹스",
    "nude",
    "rape",
    "kill",
    "느금",
    "틀딱",
    "좌빨",
    "우좀",
    "짱깨",
    "조선족",
}

_SENSITIVE_PATTERNS = [
    re.compile(r"\b01[0-9]-?\d{3,4}-?\d{4}\b"),
    re.compile(r"\b\d{2,4}-\d{3,4}-\d{4}\b"),
    re.compile(r"\b\d{6}-?[1-4]\d{6}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]
_PRIVATE_INVESTMENT_PATTERNS = [
    re.compile(r"(수익률|수익금|손익|평단|평단가|매수가|매수가격|보유수량|원금|시드)"),
    re.compile(r"(익절|손절).{0,8}(인증|후기|공개)"),
    re.compile(r"(수익률|손익|평단|매수가).{0,12}(\d+(?:\.\d+)?%|\d+(?:,\d{3})*(?:원|만원|억))"),
]
_LOW_SIGNAL_PATTERNS = [
    re.compile(r"^[ㅋㅎㅠㅜ!?~\.\s\d]+$"),
    re.compile(r"(ㅋㅋ|ㅎㅎ|ㅠㅠ|ㅜㅜ|ㄷㄷ)"),
]


@dataclass(frozen=True)
class CommunityFilterResult:
    """커뮤니티 필터링 결과."""

    source_id: str
    kept_posts: List[CommunityPost] = field(default_factory=list)
    input_count: int = 0
    filtered_count: int = 0
    skipped: bool = False
    reason: str = ""


def get_community_source_policy(source_id: str) -> CommunitySourcePolicy:
    """알려진 소스 정책을 반환합니다."""
    normalized = source_id.strip().lower()
    return _SOURCE_POLICIES.get(
        normalized,
        CommunitySourcePolicy(source_id=normalized),
    )


def get_enabled_community_sources(raw_value: str | None = None) -> set[str]:
    """환경변수 또는 기본 정책 기준의 활성 커뮤니티 소스 집합을 반환합니다."""
    if raw_value is None:
        raw_value = os.getenv("COMMUNITY_ENABLED_SOURCES")
    if raw_value is None:
        return set(DEFAULT_ENABLED_SOURCES)
    parsed = {
        item.strip().lower()
        for item in str(raw_value).split(",")
        if item.strip()
    }
    return parsed or set(DEFAULT_ENABLED_SOURCES)


def _sanitize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.replace("\u200b", " ")).strip()


def _is_high_risk_title(title: str) -> bool:
    normalized = title.lower()
    if any(keyword in normalized for keyword in _HIGH_RISK_KEYWORDS):
        return True
    return any(pattern.search(title) for pattern in _SENSITIVE_PATTERNS)


def _is_private_investment_title(title: str) -> bool:
    return any(pattern.search(title) for pattern in _PRIVATE_INVESTMENT_PATTERNS)


def _is_low_signal_title(title: str) -> bool:
    normalized = re.sub(r"\[[^\]]+\]", " ", title)
    compact = re.sub(r"\s+", " ", normalized).strip()
    alnum_length = len(re.sub(r"[^0-9A-Za-z가-힣]+", "", compact))
    if alnum_length < 3:
        return True
    return any(
        pattern.search(compact) and alnum_length < 12
        for pattern in _LOW_SIGNAL_PATTERNS
    )


def _sanitize_post_for_source(post: CommunityPost, source_id: str) -> CommunityPost:
    policy = get_community_source_policy(source_id)
    return CommunityPost(
        title=_sanitize_title(post.title or ""),
        link=(post.link or "").strip(),
        source_id=source_id,
        views=(post.views or "").strip() or None if policy.allow_views else None,
        likes=(post.likes or "").strip() or None if policy.allow_likes else None,
        comments=(post.comments or "").strip() or None if policy.allow_comments else None,
    )


def filter_community_posts(
    source_id: str,
    posts: Iterable[CommunityPost],
    max_items: int = 3,
    enabled_sources: set[str] | None = None,
) -> CommunityFilterResult:
    """소스 정책과 제목 패턴 기준으로 안전한 커뮤니티 게시글만 반환합니다."""
    post_list = list(posts)
    normalized_source = source_id.strip().lower()
    allowed_sources = enabled_sources or get_enabled_community_sources()

    if normalized_source not in allowed_sources:
        return CommunityFilterResult(
            source_id=normalized_source,
            input_count=len(post_list),
            filtered_count=len(post_list),
            skipped=True,
            reason="source_disabled",
        )

    kept_posts: List[CommunityPost] = []
    filtered_count = 0
    seen_titles: set[str] = set()

    for post in post_list:
        title = _sanitize_title(post.title or "")
        dedupe_key = re.sub(r"\s+", " ", title.lower())
        if not title or dedupe_key in seen_titles:
            filtered_count += 1
            continue
        if _is_high_risk_title(title) or _is_private_investment_title(title) or _is_low_signal_title(title):
            filtered_count += 1
            continue
        seen_titles.add(dedupe_key)
        kept_posts.append(_sanitize_post_for_source(post, normalized_source))
        if len(kept_posts) >= max_items:
            break

    reason = ""
    if not kept_posts:
        reason = "all_filtered"

    return CommunityFilterResult(
        source_id=normalized_source,
        kept_posts=kept_posts,
        input_count=len(post_list),
        filtered_count=filtered_count,
        skipped=False,
        reason=reason,
    )


def filter_community_posts_by_source(
    source_posts: Dict[str, Iterable[CommunityPost]],
    max_items_per_source: int = 3,
    enabled_sources: set[str] | None = None,
) -> Dict[str, CommunityFilterResult]:
    """여러 커뮤니티 소스를 한 번에 필터링합니다."""
    results: Dict[str, CommunityFilterResult] = {}
    for source_id, posts in source_posts.items():
        results[source_id] = filter_community_posts(
            source_id=source_id,
            posts=posts,
            max_items=max_items_per_source,
            enabled_sources=enabled_sources,
        )
    return results


def flatten_safe_community_posts(
    filter_results: Dict[str, CommunityFilterResult],
    max_items: int = 4,
) -> List[CommunityPost]:
    """필터된 결과를 하나의 안전한 게시글 리스트로 합칩니다."""
    merged: List[CommunityPost] = []
    sorted_results = sorted(
        filter_results.values(),
        key=lambda result: (
            get_community_source_policy(result.source_id).merge_priority,
            result.source_id,
        ),
    )
    for result in sorted_results:
        merged.extend(result.kept_posts)
        if len(merged) >= max_items:
            return merged[:max_items]
    return merged[:max_items]
