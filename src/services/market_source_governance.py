"""
시장 데이터 소스 정책/무료 한도 검증 모듈.

역할:
1. 국내/미국 데이터 소스의 무료 한도, 상업 이용 가능 여부, 재배포 제약을 코드로 관리합니다.
2. 파이프라인 실행 주기(예: 3시간) 기준으로 예상 일 호출량을 계산합니다.
3. 무과금 운영 가능 여부를 사전 판정하여 운영 리스크를 줄입니다.
"""

from dataclasses import dataclass
from math import ceil
from typing import Dict, Iterable, List, Optional


CommercialPolicy = str
RedistributionPolicy = str


@dataclass(frozen=True)
class SourcePolicy:
    """데이터 소스 정책 정의."""

    source_id: str
    name: str
    market: str
    free_supported: bool
    free_daily_limit: Optional[int]
    commercial_policy: CommercialPolicy
    redistribution_policy: RedistributionPolicy
    notes: str = ""


@dataclass(frozen=True)
class SourceWorkload:
    """소스별 1회 실행당 호출량 계획."""

    source_id: str
    calls_per_run: int


@dataclass(frozen=True)
class SourceFeasibility:
    """소스별 무과금 운영 적합성 평가 결과."""

    source_id: str
    status: str
    estimated_daily_calls: int
    free_daily_limit: Optional[int]
    reason: str


def get_default_source_policies() -> List[SourcePolicy]:
    """프로젝트 기준 기본 소스 정책 목록을 반환합니다."""
    return [
        SourcePolicy(
            source_id="fsc_stock_price",
            name="금융위_주식시세정보(data.go.kr)",
            market="KR",
            free_supported=True,
            free_daily_limit=10000,
            commercial_policy="allowed",
            redistribution_policy="allowed",
            notes="개발계정 트래픽 10,000회/일",
        ),
        SourcePolicy(
            source_id="fsc_listed_info",
            name="금융위_KRX상장종목정보(data.go.kr)",
            market="KR",
            free_supported=True,
            free_daily_limit=10000,
            commercial_policy="allowed",
            redistribution_policy="allowed",
            notes="개발계정 트래픽 10,000회/일",
        ),
        SourcePolicy(
            source_id="opendart",
            name="OpenDART",
            market="KR",
            free_supported=True,
            free_daily_limit=20000,
            commercial_policy="allowed",
            redistribution_policy="conditional",
            notes="분당 1,000회 이상 과다 접속 시 제한 가능",
        ),
        SourcePolicy(
            source_id="naver_datalab",
            name="Naver DataLab API",
            market="KR",
            free_supported=True,
            free_daily_limit=1000,
            commercial_policy="conditional",
            redistribution_policy="conditional",
            notes="하루 호출 한도 1,000회",
        ),
        SourcePolicy(
            source_id="sec_edgar",
            name="SEC EDGAR API",
            market="US",
            free_supported=True,
            free_daily_limit=None,
            commercial_policy="allowed",
            redistribution_policy="allowed",
            notes="초당 10요청 이하 권고, User-Agent 필요",
        ),
        SourcePolicy(
            source_id="fred",
            name="FRED API",
            market="US",
            free_supported=True,
            free_daily_limit=None,
            commercial_policy="allowed",
            redistribution_policy="conditional",
            notes="일부 시리즈는 제3자 저작권 제한 가능",
        ),
        SourcePolicy(
            source_id="alpha_vantage",
            name="Alpha Vantage",
            market="US",
            free_supported=True,
            free_daily_limit=25,
            commercial_policy="allowed",
            redistribution_policy="allowed",
            notes="무료 플랜 25요청/일, 실시간 US 데이터는 premium-only",
        ),
        SourcePolicy(
            source_id="krx_openapi",
            name="KRX OpenAPI",
            market="KR",
            free_supported=True,
            free_daily_limit=10000,
            commercial_policy="non_commercial_only",
            redistribution_policy="restricted",
            notes="약관상 비상업 목적 및 제3자 제공 제한 조항",
        ),
        SourcePolicy(
            source_id="kosis",
            name="KOSIS OpenAPI",
            market="KR",
            free_supported=True,
            free_daily_limit=None,
            commercial_policy="allowed",
            redistribution_policy="allowed",
            notes="과다 트래픽은 별도 협의 가능",
        ),
    ]


def parse_active_source_ids(
    raw_value: Optional[str],
    default_source_ids: Optional[Iterable[str]] = None,
) -> List[str]:
    """환경변수 문자열을 활성 소스 ID 리스트로 파싱합니다."""
    if raw_value is None:
        source_ids = list(default_source_ids or [])
    else:
        source_ids = [item.strip() for item in raw_value.split(",")]

    normalized: List[str] = []
    seen = set()
    for source_id in source_ids:
        if not source_id:
            continue
        if source_id in seen:
            continue
        seen.add(source_id)
        normalized.append(source_id)
    return normalized


def runs_per_day(run_interval_hours: int) -> int:
    """실행 주기(시간) 기준 일 실행 횟수를 계산합니다."""
    if run_interval_hours <= 0:
        raise ValueError("run_interval_hours must be greater than 0")
    return ceil(24 / run_interval_hours)


def estimate_daily_calls(
    workloads: Iterable[SourceWorkload],
    run_interval_hours: int,
) -> Dict[str, int]:
    """소스별 예상 일 호출량을 반환합니다."""
    daily_runs = runs_per_day(run_interval_hours)
    return {
        workload.source_id: max(0, workload.calls_per_run) * daily_runs
        for workload in workloads
    }


def build_active_workloads(
    active_source_ids: Iterable[str],
    default_calls_per_run: int = 1,
    calls_per_run_overrides: Optional[Dict[str, int]] = None,
) -> List[SourceWorkload]:
    """활성 소스 목록을 실행당 호출량 계획으로 변환합니다."""
    overrides = calls_per_run_overrides or {}
    workloads: List[SourceWorkload] = []
    for source_id in active_source_ids:
        calls = overrides.get(source_id, default_calls_per_run)
        workloads.append(SourceWorkload(source_id=source_id, calls_per_run=max(0, calls)))
    return workloads


def recommend_production_source_ids(
    policies: Iterable[SourcePolicy],
) -> List[str]:
    """배포형 리포트 서비스에서 우선 추천 가능한 소스 ID를 반환합니다."""
    recommended: List[str] = []
    for policy in policies:
        if not policy.free_supported:
            continue
        if policy.commercial_policy == "non_commercial_only":
            continue
        if policy.redistribution_policy == "restricted":
            continue
        recommended.append(policy.source_id)
    return recommended


def evaluate_active_sources(
    active_source_ids: Iterable[str],
    run_interval_hours: int,
    default_calls_per_run: int = 1,
    calls_per_run_overrides: Optional[Dict[str, int]] = None,
    policies: Optional[Iterable[SourcePolicy]] = None,
) -> List[SourceFeasibility]:
    """활성 소스 기준 무과금 운영 적합성을 평가합니다."""
    active_list = list(active_source_ids)
    selected_policies = list(policies or get_default_source_policies())
    workloads = build_active_workloads(
        active_list,
        default_calls_per_run=default_calls_per_run,
        calls_per_run_overrides=calls_per_run_overrides,
    )
    return assess_source_feasibility(
        selected_policies,
        workloads,
        run_interval_hours=run_interval_hours,
    )


def assess_source_feasibility(
    policies: Iterable[SourcePolicy],
    workloads: Iterable[SourceWorkload],
    run_interval_hours: int,
) -> List[SourceFeasibility]:
    """소스별 무과금 운영 적합성을 판정합니다."""
    policy_map = {policy.source_id: policy for policy in policies}
    daily_calls_map = estimate_daily_calls(workloads, run_interval_hours)
    evaluations: List[SourceFeasibility] = []

    for source_id, daily_calls in daily_calls_map.items():
        policy = policy_map.get(source_id)
        if not policy:
            evaluations.append(
                SourceFeasibility(
                    source_id=source_id,
                    status="unknown",
                    estimated_daily_calls=daily_calls,
                    free_daily_limit=None,
                    reason="정책 정보가 등록되지 않은 소스입니다.",
                )
            )
            continue

        if not policy.free_supported:
            evaluations.append(
                SourceFeasibility(
                    source_id=source_id,
                    status="blocked",
                    estimated_daily_calls=daily_calls,
                    free_daily_limit=policy.free_daily_limit,
                    reason="무료 플랜 미지원 소스입니다.",
                )
            )
            continue

        if policy.commercial_policy == "non_commercial_only":
            evaluations.append(
                SourceFeasibility(
                    source_id=source_id,
                    status="blocked",
                    estimated_daily_calls=daily_calls,
                    free_daily_limit=policy.free_daily_limit,
                    reason="비상업 목적 전용 약관으로 배포형 서비스와 충돌합니다.",
                )
            )
            continue

        if policy.redistribution_policy == "restricted":
            evaluations.append(
                SourceFeasibility(
                    source_id=source_id,
                    status="blocked",
                    estimated_daily_calls=daily_calls,
                    free_daily_limit=policy.free_daily_limit,
                    reason="제3자 제공 제한 조항이 있어 리포트 배포에 부적합합니다.",
                )
            )
            continue

        if policy.free_daily_limit is not None and daily_calls > policy.free_daily_limit:
            evaluations.append(
                SourceFeasibility(
                    source_id=source_id,
                    status="exceed",
                    estimated_daily_calls=daily_calls,
                    free_daily_limit=policy.free_daily_limit,
                    reason="예상 일 호출량이 무료 한도를 초과합니다.",
                )
            )
            continue

        if policy.redistribution_policy == "conditional":
            evaluations.append(
                SourceFeasibility(
                    source_id=source_id,
                    status="conditional",
                    estimated_daily_calls=daily_calls,
                    free_daily_limit=policy.free_daily_limit,
                    reason="약관/저작권 추가 점검이 필요합니다.",
                )
            )
            continue

        evaluations.append(
            SourceFeasibility(
                source_id=source_id,
                status="ok",
                estimated_daily_calls=daily_calls,
                free_daily_limit=policy.free_daily_limit,
                reason="무료 운영 조건에서 즉시 사용 가능합니다.",
            )
        )

    return evaluations
