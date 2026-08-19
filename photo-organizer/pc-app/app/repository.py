"""SQLiteへの読み書きをまとめたリポジトリ層。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from .models import MediaItem


def row_to_media_item(row: sqlite3.Row) -> MediaItem:
    return MediaItem(
        id=row["id"],
        file_name=row["file_name"],
        absolute_path=row["absolute_path"],
        relative_path=row["relative_path"],
        root_folder=row["root_folder"],
        media_type=row["media_type"],
        extension=row["extension"],
        file_size=row["file_size"],
        fs_created_at=row["fs_created_at"],
        fs_modified_at=row["fs_modified_at"],
        captured_at=row["captured_at"],
        sha256=row["sha256"],
        width=row["width"],
        height=row["height"],
        duration_seconds=row["duration_seconds"],
        fps=row["fps"],
        bitrate=row["bitrate"],
        codec=row["codec"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        camera_make=row["camera_make"],
        camera_model=row["camera_model"],
        orientation=row["orientation"],
        exif_json=row["exif_json"],
        is_screenshot=bool(row["is_screenshot"]) if row["is_screenshot"] is not None else None,
        screenshot_confidence=row["screenshot_confidence"],
        category_guess=row["category_guess"],
        category_confidence=row["category_confidence"],
        blur_variance=row["blur_variance"],
        brightness_mean=row["brightness_mean"],
        is_corrupt=bool(row["is_corrupt"]),
        is_screen_recording=bool(row["is_screen_recording"]) if row["is_screen_recording"] is not None else None,
        screen_recording_confidence=row["screen_recording_confidence"],
        phash=row["phash"],
        dhash=row["dhash"],
        quality_flags=json.loads(row["quality_flags_json"]) if row["quality_flags_json"] else [],
        metadata_errors=json.loads(row["metadata_errors_json"]) if row["metadata_errors_json"] else [],
        analysis_status=row["analysis_status"],
        analysis_error=row["analysis_error"],
        scan_mtime=row["scan_mtime"],
        scan_size=row["scan_size"],
        scanned_at=row["scanned_at"],
        analyzed_at=row["analyzed_at"],
    )


def get_all_media_items(conn: sqlite3.Connection, media_type: Optional[str] = None) -> list[MediaItem]:
    if media_type:
        rows = conn.execute(
            "SELECT * FROM media_items WHERE media_type = ? AND analysis_status = 'analyzed'", (media_type,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM media_items WHERE analysis_status = 'analyzed'").fetchall()
    return [row_to_media_item(r) for r in rows]


def get_media_item(conn: sqlite3.Connection, media_id: int) -> Optional[MediaItem]:
    row = conn.execute("SELECT * FROM media_items WHERE id = ?", (media_id,)).fetchone()
    return row_to_media_item(row) if row else None


def upsert_media_item(conn: sqlite3.Connection, existing_id: Optional[int], fields: dict[str, Any]) -> int:
    fields = dict(fields)
    now = datetime.now(timezone.utc).isoformat()
    if existing_id is not None:
        fields["id"] = existing_id
        columns = [k for k in fields if k != "id"]
        set_clause = ", ".join(f"{c} = :{c}" for c in columns)
        conn.execute(f"UPDATE media_items SET {set_clause} WHERE id = :id", fields)
        return existing_id
    else:
        columns = list(fields.keys())
        placeholders = ", ".join(f":{c}" for c in columns)
        conn.execute(
            f"INSERT INTO media_items ({', '.join(columns)}) VALUES ({placeholders})", fields
        )
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def clear_derived_tables(conn: sqlite3.Connection) -> None:
    """グルーピング/スコアは再計算のたびに作り直す(再解析の一貫性を保つため)。"""
    conn.execute("DELETE FROM duplicate_group_items")
    conn.execute("DELETE FROM duplicate_groups")
    conn.execute("DELETE FROM similarity_group_items")
    conn.execute("DELETE FROM similarity_groups")
    conn.execute("DELETE FROM delete_candidates")


def insert_duplicate_group(conn: sqlite3.Connection, sha256: str, items: list[MediaItem], keep_media_id: int) -> int:
    now = datetime.now(timezone.utc).isoformat()
    total_size = sum(i.file_size for i in items)
    cur = conn.execute(
        "INSERT INTO duplicate_groups (sha256, item_count, total_size, created_at) VALUES (?, ?, ?, ?)",
        (sha256, len(items), total_size, now),
    )
    group_id = cur.lastrowid
    for item in items:
        conn.execute(
            "INSERT INTO duplicate_group_items (group_id, media_id, is_keep_recommended) VALUES (?, ?, ?)",
            (group_id, item.id, 1 if item.id == keep_media_id else 0),
        )
    return group_id


def insert_similarity_group(
    conn: sqlite3.Connection,
    group_type: str,
    method: str,
    items: list[MediaItem],
    keep_media_id: int,
    distances: dict[int, float] | None = None,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO similarity_groups (group_type, method, representative_media_id, item_count, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (group_type, method, keep_media_id, len(items), now),
    )
    group_id = cur.lastrowid
    distances = distances or {}
    for item in items:
        conn.execute(
            "INSERT INTO similarity_group_items (group_id, media_id, distance, is_keep_recommended) "
            "VALUES (?, ?, ?, ?)",
            (group_id, item.id, distances.get(item.id), 1 if item.id == keep_media_id else 0),
        )
    return group_id


def upsert_delete_candidate(conn: sqlite3.Connection, media_id: int, score: int, reasons: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO delete_candidates (media_id, deletion_candidate_score, reasons_json, user_status, updated_at)
        VALUES (?, ?, ?, 'candidate', ?)
        ON CONFLICT(media_id) DO UPDATE SET
            deletion_candidate_score = excluded.deletion_candidate_score,
            reasons_json = excluded.reasons_json,
            updated_at = excluded.updated_at
        """,
        (media_id, score, json.dumps(reasons, ensure_ascii=False), now),
    )


def set_delete_candidate_status(conn: sqlite3.Connection, media_id: int, user_status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE delete_candidates SET user_status = ?, updated_at = ? WHERE media_id = ?",
        (user_status, now, media_id),
    )
