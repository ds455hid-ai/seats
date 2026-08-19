"""画質判定: ブレ・明るさ・破損検出(OpenCV)。

Laplacian分散が低いほどエッジが少ない=ピンぼけの可能性が高い、という
一般的な手法を使用する。あくまで無料ローカル処理での近似判定であり、
100%の精度を保証するものではない。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_ANALYZE_DIMENSION = 1024  # 解析用に縮小して高速化(結果の縮尺には影響しない)


@dataclass
class QualityResult:
    blur_variance: Optional[float] = None
    brightness_mean: Optional[float] = None
    is_corrupt: bool = False
    errors: list[str] = field(default_factory=list)


def analyze_photo_quality(file_path: Path) -> QualityResult:
    result = QualityResult()
    try:
        import cv2
        import numpy as np

        # HEICはOpenCVが直接読めないことが多いため、Pillow経由でRGB配列にしてから渡す
        image = _load_as_bgr_array(file_path)
        if image is None:
            result.is_corrupt = True
            result.errors.append("画像を読み込めませんでした(破損の可能性)")
            return result

        h, w = image.shape[:2]
        scale = min(1.0, _MAX_ANALYZE_DIMENSION / max(h, w)) if max(h, w) > 0 else 1.0
        if scale < 1.0:
            image = cv2.resize(image, (int(w * scale), int(h * scale)))

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        result.blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        result.brightness_mean = float(np.mean(gray))

    except Exception as exc:  # noqa: BLE001 - 品質判定失敗で全体を止めない(仕様6)
        result.errors.append(f"画質判定に失敗しました: {exc}")
        logger.warning("画質判定に失敗しました: %s (%s)", file_path, exc)

    return result


def _load_as_bgr_array(file_path: Path):
    import cv2
    import numpy as np

    try:
        from PIL import Image

        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError:
            pass

        with Image.open(file_path) as img:
            rgb = img.convert("RGB")
            arr = np.array(rgb)
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pillow経由の画像読み込みに失敗: %s (%s)", file_path, exc)
        return None
