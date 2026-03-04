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
                analysis_snip TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_user
                ON feedbacks(user_name);
            CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                ON feedbacks(timestamp);
            CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp
                ON prediction_snapshots(timestamp);
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
