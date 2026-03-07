"""
SQLite 데이터베이스 추상화 모듈.

기존 JSON 파일 기반 영구 저장소를 SQLite로 교체합니다.
JSON 파일의 문제점:
1. 동시 쓰기 시 데이터 손실 위험 (파일 잠금 없음)
2. 전체 파일을 읽어야 하므로 데이터가 커지면 느려짐 (O(n) 탐색)
3. 날짜 범위 검색 등 쿼리가 불가능

SQLite의 장점:
1. ACID 트랜잭션으로 데이터 무결성 보장
2. 인덱스 기반 빠른 검색
3. Python 표준 라이브러리 (추가 설치 없음)

사용법:
    from src.utils.database import get_db

    db = get_db()
    db.insert_feedback("홍길동", 5, "좋아요")
    feedbacks = db.get_recent_feedbacks(days=7)

[Task 6.20, REQ-P06]
"""

import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.utils.logger import global_logger

# 데이터베이스 파일 경로
DB_PATH = os.path.join("data", "stock_project.db")

# 싱글톤 인스턴스 (스레드 안전)
_db_instance = None
_lock = threading.Lock()


class Database:
    """SQLite 데이터베이스 래퍼.

    싱글톤 패턴으로 프로세스 내 단일 인스턴스만 생성됩니다.
    """

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")  # 성능 최적화
        self._create_tables()
        global_logger.info(f"🗄️ [DB] SQLite 연결 완료: {db_path}")

    def _create_tables(self):
        """필요한 테이블을 생성합니다 (없을 경우에만)."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS feedbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                comment TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS prediction_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_name TEXT NOT NULL,
                holdings TEXT NOT NULL,
                analysis_snip TEXT NOT NULL,
                accuracy_score REAL DEFAULT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_user
                ON feedbacks(user_name);
            CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                ON feedbacks(timestamp);
            CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp
                ON prediction_snapshots(timestamp);

            CREATE TABLE IF NOT EXISTS report_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_name TEXT NOT NULL,
                headline TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                report_snip TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_report_snapshot_user
                ON report_snapshots(user_name);
            CREATE INDEX IF NOT EXISTS idx_report_snapshot_timestamp
                ON report_snapshots(timestamp);

            CREATE TABLE IF NOT EXISTS prompt_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                prompt_type TEXT NOT NULL,
                version TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_prompt_usage_type
                ON prompt_usage_log(prompt_type);

            CREATE TABLE IF NOT EXISTS external_connector_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source_id TEXT NOT NULL,
                status TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                detail TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_connector_runs_source
                ON external_connector_runs(source_id);
            CREATE INDEX IF NOT EXISTS idx_connector_runs_timestamp
                ON external_connector_runs(timestamp);
        """)
        self._conn.commit()

    # ==========================================
    # 피드백 관련 메서드
    # ==========================================

    def insert_feedback(self, user_name: str, score: int, comment: str = "") -> None:
        """사용자 피드백을 저장합니다.

        Args:
            user_name: 평가자 이름
            score: 별점 (1~5)
            comment: 추가 코멘트 (선택)
        """
        self._conn.execute(
            "INSERT INTO feedbacks (timestamp, user_name, score, comment) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), user_name, score, comment)
        )
        self._conn.commit()
        global_logger.info(f"💌 [DB] {user_name}님의 피드백({score}점)이 저장되었습니다.")

    def get_recent_feedbacks(self, days: int = 7) -> List[Dict[str, Any]]:
        """최근 N일간 피드백을 조회합니다.

        Args:
            days: 조회 기간 (일)

        Returns:
            피드백 딕셔너리 리스트
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            "SELECT * FROM feedbacks WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_average_score(self, days: int = 30) -> float:
        """최근 N일간 평균 별점을 반환합니다.

        Args:
            days: 조회 기간 (일)

        Returns:
            평균 점수. 데이터 없으면 0.0.
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            "SELECT AVG(score) FROM feedbacks WHERE timestamp >= ?",
            (since,)
        )
        result = cursor.fetchone()[0]
        return round(result, 2) if result else 0.0

    # ==========================================
    # 예측 스냅샷 관련 메서드
    # ==========================================

    def insert_snapshot(self, user_name: str, holdings: str, analysis_text: str) -> None:
        """AI 예측 분석 스냅샷을 저장합니다.

        Args:
            user_name: 대상 유저
            holdings: 보유 종목 문자열
            analysis_text: AI 분석 텍스트 (최대 1000자)
        """
        self._conn.execute(
            "INSERT INTO prediction_snapshots (timestamp, user_name, holdings, analysis_snip) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), user_name, holdings, analysis_text[:1000])
        )
        self._conn.commit()
        global_logger.info(f"🤖 [DB] '{user_name}'님의 포트폴리오 분석 스냅샷이 저장되었습니다.")

    def get_recent_snapshots(self, limit: int = 3) -> List[Dict[str, Any]]:
        """최근 스냅샷을 조회합니다.

        Args:
            limit: 최대 조회 건수

        Returns:
            스냅샷 딕셔너리 리스트
        """
        cursor = self._conn.execute(
            "SELECT * FROM prediction_snapshots ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """데이터베이스 연결을 닫습니다."""
        self._conn.close()
        global_logger.info("🗄️ [DB] SQLite 연결 종료")

    def update_snapshot_score(self, snapshot_id: int, score: float) -> None:
        """예측 스냅샷의 적중률 점수를 업데이트합니다.

        Args:
            snapshot_id: 스냅샷 ID
            score: 적중률 점수 (0.0 ~ 1.0)
        """
        self._conn.execute(
            "UPDATE prediction_snapshots SET accuracy_score = ? WHERE id = ?",
            (score, snapshot_id)
        )
        self._conn.commit()

    def get_average_accuracy(self, days: int = 30) -> float:
        """최근 N일간 예측 적중률 평균을 반환합니다.

        Args:
            days: 조회 기간

        Returns:
            평균 적중률. 데이터 없으면 0.0.
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            "SELECT AVG(accuracy_score) FROM prediction_snapshots WHERE timestamp >= ? AND accuracy_score IS NOT NULL",
            (since,)
        )
        result = cursor.fetchone()[0]
        return round(result, 2) if result else 0.0

    def get_unscored_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        """아직 점수가 매겨지지 않은 스냅샷을 조회합니다.

        Args:
            limit: 최대 조회 건수

        Returns:
            스냅샷 딕셔너리 리스트
        """
        cursor = self._conn.execute(
            "SELECT * FROM prediction_snapshots WHERE accuracy_score IS NULL ORDER BY timestamp ASC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ==========================================
    # 외부 커넥터 텔레메트리 메서드
    # ==========================================

    def insert_connector_run(
        self,
        source_id: str,
        status: str,
        count: int,
        latency_ms: int,
        detail: str = "",
    ) -> None:
        """외부 커넥터 실행 결과를 저장합니다."""
        self._conn.execute(
            (
                "INSERT INTO external_connector_runs "
                "(timestamp, source_id, status, count, latency_ms, detail) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
            (
                datetime.now().isoformat(),
                source_id,
                status,
                max(0, int(count)),
                max(0, int(latency_ms)),
                detail or "",
            ),
        )
        self._conn.commit()

    def get_recent_connector_runs(
        self,
        limit: int = 50,
        source_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """최근 외부 커넥터 실행 이력을 조회합니다."""
        if source_id:
            cursor = self._conn.execute(
                (
                    "SELECT * FROM external_connector_runs "
                    "WHERE source_id = ? "
                    "ORDER BY timestamp DESC LIMIT ?"
                ),
                (source_id, limit),
            )
        else:
            cursor = self._conn.execute(
                "SELECT * FROM external_connector_runs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_connector_success_rate(self, days: int = 7) -> Dict[str, float]:
        """최근 N일 기준 source별 성공률(status=ok 비중)을 반환합니다."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            """
            SELECT
                source_id,
                SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS success_count,
                COUNT(*) AS total_count
            FROM external_connector_runs
            WHERE timestamp >= ?
            GROUP BY source_id
            """,
            (since,),
        )

        rates: Dict[str, float] = {}
        for row in cursor.fetchall():
            total = row["total_count"] or 0
            success = row["success_count"] or 0
            if total <= 0:
                rates[row["source_id"]] = 0.0
            else:
                rates[row["source_id"]] = round(success / total, 4)
        return rates

    # ==========================================
    # 리포트 스냅샷 메서드
    # ==========================================

    def insert_report_snapshot(
        self,
        user_name: str,
        headline: str,
        snapshot_json: str,
        report_text: str = "",
    ) -> None:
        """사용자별 리포트 요약 스냅샷을 저장합니다."""
        self._conn.execute(
            (
                "INSERT INTO report_snapshots "
                "(timestamp, user_name, headline, snapshot_json, report_snip) "
                "VALUES (?, ?, ?, ?, ?)"
            ),
            (
                datetime.now().isoformat(),
                user_name,
                (headline or "")[:300],
                (snapshot_json or "")[:8000],
                (report_text or "")[:2000],
            ),
        )
        self._conn.commit()

    def get_recent_report_snapshots(
        self,
        user_name: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """특정 사용자의 최근 리포트 스냅샷을 최신순으로 조회합니다."""
        cursor = self._conn.execute(
            (
                "SELECT * FROM report_snapshots "
                "WHERE user_name = ? "
                "ORDER BY timestamp DESC LIMIT ?"
            ),
            (user_name, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_report_snapshots_since(
        self,
        user_name: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """특정 사용자의 최근 N일 리포트 스냅샷을 조회합니다."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            (
                "SELECT * FROM report_snapshots "
                "WHERE user_name = ? AND timestamp >= ? "
                "ORDER BY timestamp DESC"
            ),
            (user_name, since),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_db(db_path: str = DB_PATH) -> Database:
    """Database 싱글톤 인스턴스를 반환합니다.

    스레드 안전하게 한 번만 생성됩니다.

    Args:
        db_path: 데이터베이스 파일 경로

    Returns:
        Database 인스턴스
    """
    global _db_instance
    if _db_instance is None:
        with _lock:
            if _db_instance is None:
                _db_instance = Database(db_path)
    return _db_instance


def close_db() -> None:
    """전역 Database 인스턴스를 안전하게 종료합니다."""
    global _db_instance
    if _db_instance is None:
        return
    with _lock:
        if _db_instance is not None:
            _db_instance.close()
            _db_instance = None
