"""操作ログ記録。

方針(仕様44): 解析開始/終了、対象件数、削除候補件数、照合結果件数、
削除実行結果などの「数値・件数・日時」のみを記録し、
写真/動画の内容やファイルパス・サムネイルは絶対に記録しない。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def log_event(conn: sqlite3.Connection, event_type: str, detail: dict[str, Any] | None = None) -> None:
    detail = detail or {}
    conn.execute(
        "INSERT INTO operation_logs (event_type, occurred_at, detail_json) VALUES (?, ?, ?)",
        (event_type, datetime.now(timezone.utc).isoformat(), json.dumps(detail, ensure_ascii=False)),
    )
    conn.commit()
