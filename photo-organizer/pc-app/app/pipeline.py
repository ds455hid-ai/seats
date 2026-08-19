"""解析パイプライン全体のオーケストレーション。

流れ:
  1. scan_and_analyze(): フォルダ再帰スキャン → 変更ファイルのみメタデータ/ハッシュ/画質解析 → DB保存
  2. run_grouping_and_scoring(): 重複/類似グループ化 → 削除候補スコア算出 → DB保存

自動削除は一切行わない。ここで生成されるのは「候補」までであり、
確定はUI上でユーザーが行う(仕様19)。
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import repository as repo
from .config import Settings
from .grouping import (
    group_exact_duplicates,
    group_similar_photos,
    group_similar_videos,
    recommend_keep_photo,
    recommend_keep_video,
)
from .hashing import compute_photo_hashes, compute_sha256
from .logging_utils import log_event
from .metadata_photo import extract_photo_metadata
from .metadata_video import extract_video_metadata
from .quality import analyze_photo_quality
from .scoring import compute_deletion_score, determine_quality_flags
from .scanner import ScanEntry, needs_analysis, scan_folder
from .screenshot import estimate_screen_recording, estimate_screenshot
from .settings_repo import apply_overrides, get_threshold_overrides
from .video_frames import extract_representative_frames

logger = logging.getLogger(__name__)


def _analyze_entry(conn: sqlite3.Connection, entry: ScanEntry, existing_id: int | None, settings: Settings) -> None:
    now = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    try:
        sha256 = compute_sha256(entry.absolute_path)
    except Exception as exc:  # noqa: BLE001
        sha256 = None
        errors.append(f"SHA-256計算失敗: {exc}")
        logger.warning("SHA-256計算に失敗: %s (%s)", entry.absolute_path, exc)

    fields: dict[str, Any] = {
        "file_name": entry.file_name,
        "absolute_path": str(entry.absolute_path),
        "relative_path": entry.relative_path,
        "root_folder": entry.root_folder,
        "media_type": entry.media_type,
        "extension": entry.extension,
        "file_size": entry.file_size,
        "sha256": sha256,
        "scan_mtime": entry.mtime,
        "scan_size": entry.file_size,
        "scanned_at": now,
        "analysis_status": "analyzed",
        "analysis_error": None,
        "analyzed_at": now,
        "is_corrupt": 0,
        "quality_flags_json": "[]",
    }

    try:
        if entry.media_type == "photo":
            photo_meta = extract_photo_metadata(entry.absolute_path)
            quality = analyze_photo_quality(entry.absolute_path)
            phash, dhash = compute_photo_hashes(entry.absolute_path)
            screenshot_est = estimate_screenshot(
                entry.file_name, entry.extension, photo_meta.width, photo_meta.height,
                photo_meta.camera_make, photo_meta.camera_model,
            )

            errors.extend(photo_meta.errors)
            errors.extend(quality.errors)

            fields.update(
                width=photo_meta.width,
                height=photo_meta.height,
                captured_at=photo_meta.captured_at,
                camera_make=photo_meta.camera_make,
                camera_model=photo_meta.camera_model,
                orientation=photo_meta.orientation,
                latitude=photo_meta.latitude,
                longitude=photo_meta.longitude,
                exif_json=photo_meta.exif_json,
                is_corrupt=1 if (photo_meta.is_corrupt or quality.is_corrupt) else 0,
                blur_variance=quality.blur_variance,
                brightness_mean=quality.brightness_mean,
                phash=phash,
                dhash=dhash,
                is_screenshot=1 if screenshot_est.is_screenshot else 0,
                screenshot_confidence=screenshot_est.confidence,
                is_screen_recording=None,
                screen_recording_confidence=None,
                duration_seconds=None,
                fps=None,
                bitrate=None,
                codec=None,
            )

        else:  # video
            video_meta = extract_video_metadata(entry.absolute_path, settings.ffprobe_path)
            errors.extend(video_meta.errors)

            screen_recording_est = estimate_screen_recording(
                entry.file_name, video_meta.width, video_meta.height, video_meta.fps
            )

            fields.update(
                width=video_meta.width,
                height=video_meta.height,
                duration_seconds=video_meta.duration_seconds,
                fps=video_meta.fps,
                bitrate=video_meta.bitrate,
                codec=video_meta.codec,
                captured_at=video_meta.captured_at,
                latitude=video_meta.latitude,
                longitude=video_meta.longitude,
                is_corrupt=1 if video_meta.is_corrupt else 0,
                is_screenshot=None,
                screenshot_confidence=None,
                is_screen_recording=1 if screen_recording_est.is_screen_recording else 0,
                screen_recording_confidence=screen_recording_est.confidence,
                phash=None,
                dhash=None,
                blur_variance=None,
                brightness_mean=None,
                camera_make=None,
                camera_model=None,
                orientation=None,
                exif_json=None,
            )

            if not fields["is_corrupt"] and video_meta.duration_seconds:
                media_id_for_frames = existing_id
                # フレーム抽出はmedia_id確定後に行うため、ここではスキップしフラグのみ保持
                fields["_needs_frames"] = True

    except Exception as exc:  # noqa: BLE001 - 仕様6: メタデータ取得失敗で全体を止めない
        errors.append(f"解析中に想定外のエラー: {exc}")
        logger.exception("解析中にエラーが発生しました: %s", entry.absolute_path)
        fields["analysis_status"] = "failed"
        fields["analysis_error"] = str(exc)

    needs_frames = fields.pop("_needs_frames", False)
    fields["metadata_errors_json"] = __import__("json").dumps(errors, ensure_ascii=False)

    media_id = repo.upsert_media_item(conn, existing_id, fields)

    if needs_frames and entry.media_type == "video":
        try:
            frames = extract_representative_frames(
                entry.absolute_path,
                media_id,
                fields["duration_seconds"],
                settings.thumbnail_cache_dir,
                settings.ffmpeg_path,
                settings.max_video_frames,
            )
            conn.execute("DELETE FROM video_frames WHERE media_id = ?", (media_id,))
            now2 = datetime.now(timezone.utc).isoformat()
            for frame in frames:
                conn.execute(
                    "INSERT INTO video_frames (media_id, frame_index, position_ratio, thumbnail_path, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (media_id, frame.frame_index, frame.position_ratio, str(frame.thumbnail_path), now2),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("代表フレーム抽出に失敗: %s (%s)", entry.absolute_path, exc)


def scan_and_analyze(conn: sqlite3.Connection, settings: Settings, root: Path) -> dict[str, int]:
    started_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO jobs (job_type, status, target_root, started_at) VALUES ('scan_and_analyze', 'running', ?, ?)",
        (str(root), started_at),
    )
    job_id = cur.lastrowid
    conn.commit()

    total = 0
    processed = 0
    skipped_unchanged = 0
    errors = 0

    for entry in scan_folder(root, settings):
        total += 1
        needs, existing_id = needs_analysis(conn, entry)
        if not needs:
            skipped_unchanged += 1
            continue
        try:
            _analyze_entry(conn, entry, existing_id, settings)
            processed += 1
        except Exception:  # noqa: BLE001 - 1件の失敗で全体を止めない(仕様6)
            errors += 1
            logger.exception("ファイル解析に失敗しました: %s", entry.absolute_path)

        if total % settings.batch_size == 0:
            conn.execute(
                "UPDATE jobs SET total_files = ?, processed_files = ?, error_count = ? WHERE id = ?",
                (total, processed, errors, job_id),
            )
            conn.commit()

    conn.commit()

    finished_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "total_files": total,
        "processed": processed,
        "skipped_unchanged": skipped_unchanged,
        "errors": errors,
    }
    conn.execute(
        "UPDATE jobs SET status = 'completed', finished_at = ?, total_files = ?, processed_files = ?, "
        "error_count = ?, summary_json = ? WHERE id = ?",
        (finished_at, total, processed, errors, __import__("json").dumps(summary, ensure_ascii=False), job_id),
    )
    conn.commit()

    log_event(conn, "scan_and_analyze_completed", summary)
    return summary


def run_grouping_and_scoring(conn: sqlite3.Connection, settings: Settings, scoring_rules: dict) -> dict[str, int]:
    """全media_itemsを対象に重複/類似グループ化とスコア算出をやり直す。"""
    repo.clear_derived_tables(conn)

    thresholds = apply_overrides(scoring_rules.get("thresholds", {}), get_threshold_overrides(conn))
    photos = repo.get_all_media_items(conn, "photo")
    videos = repo.get_all_media_items(conn, "video")
    all_items = photos + videos

    non_keep_ids: set[int] = set()

    # 完全重複(写真・動画共通)
    exact_groups = group_exact_duplicates(all_items)
    for group in exact_groups:
        # グループ内の残す推奨: 写真は画質基準、動画は解像度/ビットレート基準
        if group[0].media_type == "photo":
            keep = recommend_keep_photo(group)
        else:
            keep = recommend_keep_video(group)
        repo.insert_duplicate_group(conn, group[0].sha256, group, keep.keep_media_id)
        for item in group:
            if item.id != keep.keep_media_id:
                non_keep_ids.add(item.id)

    # 類似写真
    similarity_non_keep_ids: set[int] = set()
    similar_photo_groups = group_similar_photos(photos, thresholds.get("phash_similarity_max_distance", 10))
    for group in similar_photo_groups:
        keep = recommend_keep_photo(group)
        repo.insert_similarity_group(conn, "photo", "phash", group, keep.keep_media_id)
        for item in group:
            if item.id != keep.keep_media_id:
                similarity_non_keep_ids.add(item.id)

    # 類似動画
    similar_video_non_keep_ids: set[int] = set()
    similar_video_groups = group_similar_videos(videos)
    for group in similar_video_groups:
        keep = recommend_keep_video(group)
        repo.insert_similarity_group(conn, "video", "duration_size_heuristic", group, keep.keep_media_id)
        for item in group:
            if item.id != keep.keep_media_id:
                similar_video_non_keep_ids.add(item.id)

    # スコア算出(全アイテム)
    candidate_count = 0
    for item in all_items:
        quality_flags = determine_quality_flags(item, thresholds)
        result = compute_deletion_score(
            quality_flags,
            scoring_rules,
            is_exact_duplicate_non_keep=item.id in non_keep_ids,
            is_similarity_non_keep=item.id in similarity_non_keep_ids,
            is_similar_video_non_keep=item.id in similar_video_non_keep_ids,
        )
        if result.score > 0:
            repo.upsert_delete_candidate(conn, item.id, result.score, result.reasons)
            candidate_count += 1

    conn.commit()

    summary = {
        "exact_duplicate_groups": len(exact_groups),
        "similar_photo_groups": len(similar_photo_groups),
        "similar_video_groups": len(similar_video_groups),
        "delete_candidates": candidate_count,
    }
    log_event(conn, "grouping_and_scoring_completed", summary)
    return summary
