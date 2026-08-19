"""settingsテーブル(ユーザーがUIから変更した閾値の上書き値)。

scoring_rules.yamlが「デフォルト値」、settingsテーブルが「ユーザーによる上書き」。
ハードコードを避けるため、両方とも実行時に読み込む。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

OVERRIDABLE_THRESHOLD_KEYS = (
    "large_video_bytes",
    "blur_laplacian_variance",
    "dark_brightness_mean",
    "too_short_video_seconds",
)


def get_threshold_overrides(conn: sqlite3.Connection) -> dict[str, float]:
    rows = conn.execute(
        "SELECT key, value FROM settings WHERE key LIKE 'threshold.%'"
    ).fetchall()
    overrides: dict[str, float] = {}
    for row in rows:
        key = row["key"].removeprefix("threshold.")
        try:
            overrides[key] = float(row["value"])
        except ValueError:
            continue
    return overrides


def set_threshold_override(conn: sqlite3.Connection, key: str, value: float) -> None:
    if key not in OVERRIDABLE_THRESHOLD_KEYS:
        raise ValueError(f"変更不可な設定キーです: {key}")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (f"threshold.{key}", str(value), now),
    )
    conn.commit()


def apply_overrides(thresholds: dict[str, Any], overrides: dict[str, float]) -> dict[str, Any]:
    merged = dict(thresholds)
    merged.update(overrides)
    return merged
