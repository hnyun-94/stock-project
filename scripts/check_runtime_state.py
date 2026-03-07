"""GitHub Actions/로컬용 SQLite 런타임 상태 점검 스크립트."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import Database, resolve_db_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQLite runtime state health check")
    parser.add_argument("--db-path", default="", help="검사할 SQLite 경로")
    parser.add_argument("--label", default="runtime", help="출력 라벨")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved_path = resolve_db_path(args.db_path or None)
    db = Database(resolved_path)
    try:
        counts = db.get_runtime_state_counts()
        payload = {
            "label": args.label,
            "db_path": resolved_path,
            "counts": counts,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
