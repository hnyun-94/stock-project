"""
프롬프트 버전 관리 및 A/B 테스트 모듈.

프롬프트를 버전별로 관리하고, 랜덤하게 A/B 그룹으로 배정하여
어떤 프롬프트 버전이 더 좋은 피드백을 받는지 추적합니다.

동작 원리:
1. 프롬프트 템플릿에 version 라벨 부여
2. 사용자를 A/B 그룹으로 해싱 배정 (일관성 보장)
3. 피드백을 버전별로 집계하여 성과 비교
4. DB에 프롬프트 실행 이력 저장

사용법:
    from src.services.prompt_versioning import PromptVersionManager

    pvm = PromptVersionManager()
    version = pvm.assign_version("홍길동", "market_summary")
    pvm.record_usage("홍길동", "market_summary", version)

[Task 6.23, REQ-F07]
"""

import hashlib
from typing import Dict, List, Optional, Any
from src.utils.database import get_db
from src.utils.logger import global_logger


class PromptVersionManager:
    """프롬프트 버전 관리 및 A/B 테스트 매니저.

    사용자 이름을 해싱하여 A/B 그룹에 일관되게 배정합니다.
    같은 사용자는 항상 같은 그룹에 배정되어 일관된 경험을 제공합니다.
    """

    def __init__(self, versions: Optional[Dict[str, List[str]]] = None):
        """초기화.

        Args:
            versions: 프롬프트 타입별 사용 가능한 버전 목록.
                      예: {"market_summary": ["v1", "v2"]}
                      None이면 기본값 사용.
        """
        self._versions = versions or {
            "market_summary": ["v1"],
            "theme_briefing": ["v1"],
            "portfolio_analysis": ["v1"],
        }

    def assign_version(self, user_name: str, prompt_type: str) -> str:
        """사용자를 프롬프트 버전에 배정합니다.

        사용자 이름의 해시값을 기반으로 버전을 선택합니다.
        같은 사용자는 항상 같은 버전을 받습니다.

        Args:
            user_name: 사용자 이름
            prompt_type: 프롬프트 유형 (예: "market_summary")

        Returns:
            배정된 버전 문자열 (예: "v1")
        """
        available = self._versions.get(prompt_type, ["v1"])
        if len(available) == 1:
            return available[0]

        # 일관된 해싱으로 그룹 배정
        hash_val = int(hashlib.md5(
            f"{user_name}:{prompt_type}".encode()
        ).hexdigest(), 16)
        idx = hash_val % len(available)

        version = available[idx]
        global_logger.info(
            f"🔀 [A/B] {user_name} → {prompt_type}:{version}"
        )
        return version

    def record_usage(self, user_name: str, prompt_type: str, version: str) -> None:
        """프롬프트 사용 이력을 DB에 기록합니다.

        Args:
            user_name: 사용자 이름
            prompt_type: 프롬프트 유형
            version: 사용된 버전
        """
        db = get_db()
        db._conn.execute(
            """INSERT INTO prompt_usage_log
               (user_name, prompt_type, version, timestamp)
               VALUES (?, ?, ?, datetime('now'))""",
            (user_name, prompt_type, version)
        )
        db._conn.commit()

    def get_version_stats(self, prompt_type: str) -> List[Dict[str, Any]]:
        """프롬프트 타입별 버전 사용 통계를 조회합니다.

        Args:
            prompt_type: 프롬프트 유형

        Returns:
            버전별 사용 횟수 딕셔너리 리스트
        """
        db = get_db()
        cursor = db._conn.execute(
            """SELECT version, COUNT(*) as count
               FROM prompt_usage_log
               WHERE prompt_type = ?
               GROUP BY version
               ORDER BY count DESC""",
            (prompt_type,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def add_version(self, prompt_type: str, version: str) -> None:
        """새 프롬프트 버전을 추가합니다 (A/B 테스트 시작).

        Args:
            prompt_type: 프롬프트 유형
            version: 추가할 버전
        """
        if prompt_type not in self._versions:
            self._versions[prompt_type] = []
        if version not in self._versions[prompt_type]:
            self._versions[prompt_type].append(version)
            global_logger.info(
                f"🆕 [A/B] {prompt_type}에 버전 '{version}' 추가 → "
                f"총 {len(self._versions[prompt_type])}개 버전"
            )
