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


# 기본 허용 소스는 보수적으로 유지해 모델 safety 오류 가능성을 낮춥니다.
DEFAULT_ENABLED_SOURCES = {"reddit_wallstreetbets"}

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
}

_SENSITIVE_PATTERNS = [
    re.compile(r"\b01[0-9]-?\d{3,4}-?\d{4}\b"),
    re.compile(r"\b\d{2,4}-\d{3,4}-\d{4}\b"),
    re.compile(r"\b\d{6}-?[1-4]\d{6}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
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


def _parse_enabled_sources(raw_value: str | None) -> set[str]:
    if raw_value is None:
        return set(DEFAULT_ENABLED_SOURCES)
    parsed = {
        item.strip().lower()
        for item in raw_value.split(",")
        if item.strip()
    }
    return parsed


def _is_high_risk_title(title: str) -> bool:
    normalized = title.lower()
    if any(keyword in normalized for keyword in _HIGH_RISK_KEYWORDS):
        return True
    return any(pattern.search(title) for pattern in _SENSITIVE_PATTERNS)


def filter_community_posts(
    source_id: str,
    posts: Iterable[CommunityPost],
    max_items: int = 3,
    enabled_sources: set[str] | None = None,
) -> CommunityFilterResult:
    """소스 정책과 제목 패턴 기준으로 안전한 커뮤니티 게시글만 반환합니다."""
    post_list = list(posts)
    normalized_source = source_id.strip().lower()
    allowed_sources = enabled_sources or _parse_enabled_sources(
        os.getenv("COMMUNITY_ENABLED_SOURCES")
    )

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
        title = (post.title or "").strip()
        dedupe_key = re.sub(r"\s+", " ", title.lower())
        if not title or dedupe_key in seen_titles:
            filtered_count += 1
            continue
        if _is_high_risk_title(title):
            filtered_count += 1
            continue
        seen_titles.add(dedupe_key)
        kept_posts.append(post)
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
    for result in filter_results.values():
        merged.extend(result.kept_posts)
        if len(merged) >= max_items:
            return merged[:max_items]
    return merged[:max_items]
