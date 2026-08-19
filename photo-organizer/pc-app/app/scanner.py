"""フォルダ再帰スキャンと、インクリメンタル解析(変更なしファイルのスキップ)。

Windows対応を見据え、パス操作はすべて pathlib.Path で行い、
OS固有のAPI(macOSのみのライブラリ等)には依存しない。
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ScanEntry:
    absolute_path: Path
    relative_path: str
    root_folder: str
    file_name: str
    extension: str
    media_type: str  # 'photo' | 'video'
    file_size: int
    mtime: float


def classify_extension(extension: str, settings: Settings) -> Optional[str]:
    ext = extension.lower()
    if ext in settings.photo_extensions:
        return "photo"
    if ext in settings.video_extensions:
        return "video"
    return None


def scan_folder(root: Path, settings: Settings) -> Iterator[ScanEntry]:
    """root以下を再帰的にスキャンし、対応拡張子のファイルのみ返す。

    1ファイルの読み取りエラー(権限エラー等)があっても、スキャン全体は継続する。
    """
    root = root.resolve()
    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
            media_type = classify_extension(path.suffix, settings)
            if media_type is None:
                continue
            stat = path.stat()
            yield ScanEntry(
                absolute_path=path,
                relative_path=str(path.relative_to(root)),
                root_folder=str(root),
                file_name=path.name,
                extension=path.suffix.lower(),
                media_type=media_type,
                file_size=stat.st_size,
                mtime=stat.st_mtime,
            )
        except (OSError, PermissionError) as exc:
            logger.warning("ファイルへのアクセスに失敗しました: %s (%s)", path, exc)
            continue


def needs_analysis(conn: sqlite3.Connection, entry: ScanEntry) -> tuple[bool, Optional[int]]:
    """DBに既存レコードがあり、サイズ・更新日時が変わっていなければ再解析不要。

    戻り値: (再解析が必要か, 既存media_idまたはNone)
    """
    row = conn.execute(
        "SELECT id, scan_size, scan_mtime, analysis_status FROM media_items WHERE absolute_path = ?",
        (str(entry.absolute_path),),
    ).fetchone()

    if row is None:
        return True, None

    unchanged = (
        row["scan_size"] == entry.file_size
        and abs(row["scan_mtime"] - entry.mtime) < 1.0  # ファイルシステムの誤差を許容
        and row["analysis_status"] == "analyzed"
    )
    return (not unchanged), row["id"]
