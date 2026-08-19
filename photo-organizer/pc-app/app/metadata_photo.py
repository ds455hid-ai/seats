"""写真のメタデータ抽出(Pillow + EXIF)。

失敗しても例外を外に投げず、空のPhotoMetadataと `errors` を返す。
呼び出し元(pipeline)はこれを見て analysis_status を 'failed' 等に振り分ける。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

_EXIF_DATETIME_TAGS = ("DateTimeOriginal", "DateTimeDigitized", "DateTime")


@dataclass
class PhotoMetadata:
    width: Optional[int] = None
    height: Optional[int] = None
    captured_at: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    orientation: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    exif_json: Optional[str] = None
    is_corrupt: bool = False
    errors: list[str] = field(default_factory=list)


def _to_degrees(value, ref: str) -> Optional[float]:
    try:
        deg, minutes, seconds = value
        result = float(deg) + float(minutes) / 60.0 + float(seconds) / 3600.0
        if ref in ("S", "W"):
            result = -result
        return result
    except Exception:  # noqa: BLE001
        return None


def _parse_exif(img) -> dict:
    from PIL.ExifTags import GPSTAGS, TAGS

    exif_raw = img.getexif()
    if not exif_raw:
        return {}

    tags: dict = {}
    for tag_id, value in exif_raw.items():
        tag_name = TAGS.get(tag_id, str(tag_id))
        tags[tag_name] = value

    gps_info = exif_raw.get_ifd(0x8825) if hasattr(exif_raw, "get_ifd") else None
    if gps_info:
        gps_tags = {}
        for tag_id, value in gps_info.items():
            gps_tags[GPSTAGS.get(tag_id, str(tag_id))] = value
        tags["GPSInfo"] = gps_tags

    return tags


def _json_safe(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value) if not isinstance(value, (int, float, str, bool, type(None))) else value


def extract_photo_metadata(file_path: Path) -> PhotoMetadata:
    meta = PhotoMetadata()
    try:
        from PIL import Image, UnidentifiedImageError

        with Image.open(file_path) as img:
            img.verify()  # 破損チェック(verify後は再オープンが必要)
        with Image.open(file_path) as img:
            meta.width, meta.height = img.size
            tags = _parse_exif(img)

            for tag in _EXIF_DATETIME_TAGS:
                if tag in tags:
                    raw = str(tags[tag])
                    try:
                        dt = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                        meta.captured_at = dt.isoformat()
                        break
                    except ValueError:
                        meta.errors.append(f"日時パース失敗: {tag}={raw}")

            meta.camera_make = str(tags.get("Make")) if tags.get("Make") else None
            meta.camera_model = str(tags.get("Model")) if tags.get("Model") else None
            orientation = tags.get("Orientation")
            meta.orientation = int(orientation) if isinstance(orientation, int) else None

            gps = tags.get("GPSInfo")
            if isinstance(gps, dict):
                lat = gps.get("GPSLatitude")
                lat_ref = gps.get("GPSLatitudeRef", "N")
                lon = gps.get("GPSLongitude")
                lon_ref = gps.get("GPSLongitudeRef", "E")
                if lat and lon:
                    meta.latitude = _to_degrees(lat, str(lat_ref))
                    meta.longitude = _to_degrees(lon, str(lon_ref))

            try:
                meta.exif_json = json.dumps(_json_safe(tags), ensure_ascii=False)
            except Exception as exc:  # noqa: BLE001
                meta.errors.append(f"EXIF JSON化失敗: {exc}")

    except UnidentifiedImageError as exc:
        meta.is_corrupt = True
        meta.errors.append(f"画像として認識できません: {exc}")
    except Exception as exc:  # noqa: BLE001 - メタデータ取得失敗で全体を止めない(仕様6)
        meta.errors.append(f"メタデータ取得失敗: {exc}")
        logger.warning("写真メタデータ取得に失敗しました: %s (%s)", file_path, exc)

    return meta
