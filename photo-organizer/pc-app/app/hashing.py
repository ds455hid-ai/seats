"""完全一致検出用SHA-256と、類似検出用の知覚ハッシュ(pHash/dHash)。"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024  # 1MB単位で読み込み、大容量動画でもメモリを圧迫しない


def compute_sha256(file_path: Path) -> str:
    """ファイル全体のSHA-256を計算する。大きな動画でも一括読み込みしない。"""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_photo_hashes(file_path: Path) -> tuple[Optional[str], Optional[str]]:
    """pHashとdHashを計算する。失敗時は(None, None)を返し、呼び出し元は処理を継続する。"""
    try:
        import imagehash
        from PIL import Image

        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError:
            pass  # HEICはPillowのみでは読めないが、pillow-heif未導入でも他形式は処理を続ける

        with Image.open(file_path) as img:
            img = img.convert("RGB")
            phash = str(imagehash.phash(img))
            dhash = str(imagehash.dhash(img))
            return phash, dhash
    except Exception as exc:  # noqa: BLE001 - 解析全体を止めないため意図的に広く捕捉
        logger.warning("知覚ハッシュ計算に失敗しました: %s (%s)", file_path, exc)
        return None, None


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """16進文字列で表現されたハッシュ同士のハミング距離を計算する。"""
    int_a = int(hash_a, 16)
    int_b = int(hash_b, 16)
    return bin(int_a ^ int_b).count("1")
