"""動画の代表フレーム抽出(ffmpeg)とサムネイルキャッシュ管理(仕様14)。"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# 開始直後・25%・50%・75%・終了直前 の割合
_DEFAULT_POSITIONS = (0.02, 0.25, 0.5, 0.75, 0.95)


@dataclass
class ExtractedFrame:
    frame_index: int
    position_ratio: float
    thumbnail_path: Path


def _positions_for_duration(duration_seconds: float, max_frames: int) -> list[float]:
    """短い動画では枚数を減らす(仕様14)。"""
    if duration_seconds <= 2:
        return [0.5]
    if duration_seconds <= 5:
        return [0.1, 0.5, 0.9][:max_frames]
    return list(_DEFAULT_POSITIONS[:max_frames])


def extract_representative_frames(
    file_path: Path,
    media_id: int,
    duration_seconds: float,
    thumbnail_cache_dir: Path,
    ffmpeg_path: str = "ffmpeg",
    max_frames: int = 5,
) -> list[ExtractedFrame]:
    """動画から代表フレームを抽出し、サムネイルキャッシュに保存する。

    失敗しても例外を投げず、抽出できたフレームのみのリストを返す(仕様6)。
    """
    if duration_seconds <= 0:
        return []

    media_thumb_dir = thumbnail_cache_dir / str(media_id)
    media_thumb_dir.mkdir(parents=True, exist_ok=True)

    positions = _positions_for_duration(duration_seconds, max_frames)
    frames: list[ExtractedFrame] = []

    for idx, ratio in enumerate(positions):
        timestamp = max(0.0, duration_seconds * ratio)
        out_path = media_thumb_dir / f"frame_{idx}.jpg"
        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", f"{timestamp:.3f}",
            "-i", str(file_path),
            "-frames:v", "1",
            "-q:v", "4",
            str(out_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
            if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
                frames.append(ExtractedFrame(frame_index=idx, position_ratio=ratio, thumbnail_path=out_path))
            else:
                logger.warning(
                    "代表フレーム抽出に失敗しました: %s position=%.2f stderr=%s",
                    file_path, ratio, result.stderr[:200].decode("utf-8", errors="ignore"),
                )
        except FileNotFoundError:
            logger.error("ffmpegが見つかりません。インストールを確認してください。")
            break
        except subprocess.TimeoutExpired:
            logger.warning("代表フレーム抽出がタイムアウトしました: %s", file_path)
            continue

    return frames


def clear_thumbnail_cache(thumbnail_cache_dir: Path) -> None:
    """サムネイルキャッシュを削除する(仕様42: キャッシュを削除可能にする)。"""
    import shutil

    if thumbnail_cache_dir.exists():
        shutil.rmtree(thumbnail_cache_dir)
    thumbnail_cache_dir.mkdir(parents=True, exist_ok=True)
