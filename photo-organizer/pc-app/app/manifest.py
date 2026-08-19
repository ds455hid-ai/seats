"""delete_manifest.json 生成(仕様29)。

このファイルだけがPC側とiPhone側の橋渡しをする。ネットワーク通信は行わず、
USB/SSD経由でユーザーが手動でコピーする想定。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import MediaItem

MANIFEST_VERSION = 1


@dataclass
class ManifestItem:
    media_id: str
    file_name: str
    media_type: str
    captured_at: Optional[str]
    file_size: int
    width: Optional[int]
    height: Optional[int]
    duration: Optional[float]
    sha256: Optional[str]
    iphone_local_identifier: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "media_id": self.media_id,
            "file_name": self.file_name,
            "media_type": self.media_type,
            "captured_at": self.captured_at,
            "file_size": self.file_size,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "sha256": self.sha256,
            "iphone_local_identifier": self.iphone_local_identifier,
        }


def build_manifest(items: list[MediaItem]) -> dict:
    manifest_items = [
        ManifestItem(
            media_id=str(item.id),
            file_name=item.file_name,
            media_type=item.media_type,
            captured_at=item.captured_at,
            file_size=item.file_size,
            width=item.width,
            height=item.height,
            duration=item.duration_seconds,
            sha256=item.sha256,
            iphone_local_identifier=None,  # Phase1ではPC側で取得手段が無いため常にnull
        ).to_dict()
        for item in items
    ]
    return {
        "version": MANIFEST_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": manifest_items,
    }


def write_manifest(items: list[MediaItem], output_path: Path) -> Path:
    manifest = build_manifest(items)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return output_path
