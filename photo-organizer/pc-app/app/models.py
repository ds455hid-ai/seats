"""ドメインモデル(データクラス)。DB行とアプリロジックの橋渡し役。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MediaItem:
    id: Optional[int]
    file_name: str
    absolute_path: str
    relative_path: str
    root_folder: str
    media_type: str  # 'photo' | 'video'
    extension: str
    file_size: int
    fs_created_at: Optional[str] = None
    fs_modified_at: Optional[str] = None
    captured_at: Optional[str] = None
    sha256: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    orientation: Optional[int] = None
    exif_json: Optional[str] = None
    is_screenshot: Optional[bool] = None
    screenshot_confidence: Optional[float] = None
    category_guess: Optional[str] = None
    category_confidence: Optional[float] = None
    blur_variance: Optional[float] = None
    brightness_mean: Optional[float] = None
    is_corrupt: bool = False
    is_screen_recording: Optional[bool] = None
    screen_recording_confidence: Optional[float] = None
    phash: Optional[str] = None
    dhash: Optional[str] = None
    quality_flags: list[str] = field(default_factory=list)
    metadata_errors: list[str] = field(default_factory=list)
    analysis_status: str = "pending"
    analysis_error: Optional[str] = None
    scan_mtime: float = 0.0
    scan_size: int = 0
    scanned_at: Optional[str] = None
    analyzed_at: Optional[str] = None


@dataclass
class DeleteCandidate:
    media_id: int
    deletion_candidate_score: int
    reasons: list[str]
    user_status: str = "candidate"  # candidate | excluded | confirmed


@dataclass
class DuplicateGroup:
    id: Optional[int]
    sha256: str
    media_ids: list[int]
    keep_media_id: Optional[int] = None


@dataclass
class SimilarityGroup:
    id: Optional[int]
    group_type: str
    method: str
    media_ids: list[int]
    representative_media_id: Optional[int] = None
    distances: dict[int, float] = field(default_factory=dict)
