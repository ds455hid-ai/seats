"""アプリ設定の読み込み。

すべての可変値(パス・閾値・ワーカー数など)はYAMLファイルから読み込み、
コード内にハードコードしない。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

APP_DIR = Path(__file__).resolve().parent
PC_APP_DIR = APP_DIR.parent
DEFAULT_SETTINGS_PATH = PC_APP_DIR / "config" / "settings.yaml"
EXAMPLE_SETTINGS_PATH = PC_APP_DIR / "config" / "settings.example.yaml"


@dataclass
class Settings:
    database_path: Path
    thumbnail_cache_dir: Path
    scoring_rules_path: Path
    worker_count: int = 4
    batch_size: int = 200
    max_video_frames: int = 5
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    photo_extensions: tuple[str, ...] = field(
        default_factory=lambda: (".jpg", ".jpeg", ".png", ".heic", ".webp")
    )
    video_extensions: tuple[str, ...] = field(
        default_factory=lambda: (".mov", ".mp4", ".m4v")
    )

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.thumbnail_cache_dir.mkdir(parents=True, exist_ok=True)


def _resolve_path(base_dir: Path, value: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def load_settings(path: Path | None = None) -> Settings:
    """settings.yaml (無ければ settings.example.yaml) を読み込む。"""
    settings_path = path or DEFAULT_SETTINGS_PATH
    if not settings_path.exists():
        settings_path = EXAMPLE_SETTINGS_PATH
    base_dir = settings_path.parent.parent  # pc-app/

    with open(settings_path, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    return Settings(
        database_path=_resolve_path(base_dir, raw.get("database_path", "./data/photo_organizer.db")),
        thumbnail_cache_dir=_resolve_path(base_dir, raw.get("thumbnail_cache_dir", "./data/thumbnails")),
        scoring_rules_path=_resolve_path(base_dir, raw.get("scoring_rules_path", "./config/scoring_rules.yaml")),
        worker_count=int(raw.get("worker_count", 4)),
        batch_size=int(raw.get("batch_size", 200)),
        max_video_frames=int(raw.get("max_video_frames", 5)),
        ffmpeg_path=raw.get("ffmpeg_path", "ffmpeg"),
        ffprobe_path=raw.get("ffprobe_path", "ffprobe"),
        photo_extensions=tuple(e.lower() for e in raw.get("photo_extensions", [".jpg", ".jpeg", ".png", ".heic", ".webp"])),
        video_extensions=tuple(e.lower() for e in raw.get("video_extensions", [".mov", ".mp4", ".m4v"])),
    )


def load_scoring_rules(settings: Settings) -> dict[str, Any]:
    with open(settings.scoring_rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
