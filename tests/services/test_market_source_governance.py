"""
시장 소스 정책/무료 한도 판정 테스트 모듈.
"""

import unittest

from src.services.market_source_governance import (
    SourceWorkload,
    assess_source_feasibility,
    build_active_workloads,
    evaluate_active_sources,
    get_default_source_policies,
    parse_active_source_ids,
    recommend_production_source_ids,
    runs_per_day,
)


class TestMarketSourceGovernance(unittest.TestCase):
    """소스 정책 및 한도 판정 테스트."""

    def test_runs_per_day_with_three_hour_interval(self):
        self.assertEqual(runs_per_day(3), 8)

    def test_recommendation_excludes_krx_openapi(self):
        policies = get_default_source_policies()
        recommended = recommend_production_source_ids(policies)
        self.assertNotIn("krx_openapi", recommended)
        self.assertIn("opendart", recommended)
        self.assertIn("sec_edgar", recommended)

    def test_alpha_vantage_limit_exceeded_is_detected(self):
        policies = get_default_source_policies()
        workloads = [SourceWorkload(source_id="alpha_vantage", calls_per_run=4)]
        results = assess_source_feasibility(policies, workloads, run_interval_hours=3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "exceed")
        self.assertEqual(results[0].estimated_daily_calls, 32)

    def test_non_commercial_source_is_blocked(self):
        policies = get_default_source_policies()
        workloads = [SourceWorkload(source_id="krx_openapi", calls_per_run=1)]
        results = assess_source_feasibility(policies, workloads, run_interval_hours=3)
        self.assertEqual(results[0].status, "blocked")

    def test_parse_active_source_ids_removes_empty_and_duplicates(self):
        parsed = parse_active_source_ids(" naver_datalab, ,opendart,naver_datalab ")
        self.assertEqual(parsed, ["naver_datalab", "opendart"])

    def test_parse_active_source_ids_uses_default_when_none(self):
        parsed = parse_active_source_ids(None, default_source_ids=["naver_datalab"])
        self.assertEqual(parsed, ["naver_datalab"])

    def test_build_active_workloads_applies_overrides(self):
        workloads = build_active_workloads(
            ["naver_datalab", "alpha_vantage"],
            default_calls_per_run=1,
            calls_per_run_overrides={"alpha_vantage": 3},
        )
        calls = {workload.source_id: workload.calls_per_run for workload in workloads}
        self.assertEqual(calls["naver_datalab"], 1)
        self.assertEqual(calls["alpha_vantage"], 3)

    def test_evaluate_active_sources_detects_exceed(self):
        results = evaluate_active_sources(
            ["alpha_vantage"],
            run_interval_hours=3,
            default_calls_per_run=4,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "exceed")


if __name__ == "__main__":
    unittest.main()
