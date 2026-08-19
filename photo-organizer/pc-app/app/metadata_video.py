"""動画メタデータ抽出(ffprobeをsubprocessで呼び出す)。

動画そのものをどこにも送信せず、ffprobeの標準出力(JSON)のみを解析する。
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    captured_at: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_corrupt: bool = False
    errors: list[str] = field(default_factory=list)


def _parse_fps(rate_str: str) -> Optional[float]:
    try:
        if "/" in rate_str:
            num, den = rate_str.split("/")
            den_f = float(den)
            return float(num) / den_f if den_f else None
        return float(rate_str)
    except Exception:  # noqa: BLE001
        return None


def _parse_location(location_str: str) -> tuple[Optional[float], Optional[float]]:
    # ISO6709形式 例: "+35.6895+139.6917/"
    import re

    match = re.match(r"^([+-]\d+\.?\d*)([+-]\d+\.?\d*)", location_str)
    if not match:
        return None, None
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return None, None


def extract_video_metadata(file_path: Path, ffprobe_path: str = "ffprobe") -> VideoMetadata:
    meta = VideoMetadata()
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, check=False
        )
        if result.returncode != 0:
            meta.errors.append(f"ffprobe終了コード異常: {result.returncode} {result.stderr[:300]}")
            meta.is_corrupt = True
            return meta

        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

        if fmt.get("duration"):
            try:
                meta.duration_seconds = float(fmt["duration"])
            except ValueError:
                meta.errors.append("duration解析失敗")
        if fmt.get("bit_rate"):
            try:
                meta.bitrate = int(fmt["bit_rate"])
            except ValueError:
                pass

        tags = fmt.get("tags", {}) or {}
        creation_time = tags.get("creation_time")
        if creation_time:
            try:
                meta.captured_at = datetime.fromisoformat(creation_time.replace("Z", "+00:00")).isoformat()
            except ValueError:
                meta.errors.append(f"creation_time解析失敗: {creation_time}")

        location = tags.get("location") or tags.get("com.apple.quicktime.location.ISO6709")
        if location:
            meta.latitude, meta.longitude = _parse_location(location)

        if video_stream:
            meta.width = video_stream.get("width")
            meta.height = video_stream.get("height")
            meta.codec = video_stream.get("codec_name")
            rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
            if rate:
                meta.fps = _parse_fps(rate)
            if meta.bitrate is None and video_stream.get("bit_rate"):
                try:
                    meta.bitrate = int(video_stream["bit_rate"])
                except ValueError:
                    pass
        else:
            meta.errors.append("映像ストリームが見つかりません")

    except FileNotFoundError:
        meta.errors.append(
            "ffprobeが見つかりません。ffmpegをインストールしてPATHを通してください。"
        )
        logger.error("ffprobeが見つかりません: %s", ffprobe_path)
    except subprocess.TimeoutExpired:
        meta.errors.append("ffprobeがタイムアウトしました")
        meta.is_corrupt = True
    except json.JSONDecodeError as exc:
        meta.errors.append(f"ffprobe出力のJSON解析失敗: {exc}")
        meta.is_corrupt = True
    except Exception as exc:  # noqa: BLE001 - メタデータ取得失敗で全体を止めない(仕様6)
        meta.errors.append(f"動画メタデータ取得失敗: {exc}")
        logger.warning("動画メタデータ取得に失敗しました: %s (%s)", file_path, exc)

    return meta
