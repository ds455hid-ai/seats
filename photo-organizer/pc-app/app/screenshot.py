"""スクリーンショット・画面録画の推定判定。

クラウドAIを使わず、以下のヒューリスティックのみで判定する。
精度は完全ではないため、UI側では必ず「推定」として表示すること(仕様12)。

判定材料:
  - ファイル名パターン (Screenshot, スクリーンショット, IMG_ vs スクショ命名規則等)
  - カメラEXIF情報の欠如(スクショはカメラのMake/Modelを持たない)
  - PNG形式(iOSスクショの既定形式)
  - 画面録画: 動画の解像度がデバイス画面比に近い(例: 9:19.5, 3:4, 1:1に近いなど)かつ
    ファイル名パターンに一致
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SCREENSHOT_NAME_PATTERN = re.compile(
    r"(screenshot|screen shot|screen_shot|スクリーンショット|スクショ)", re.IGNORECASE
)
_SCREEN_RECORDING_NAME_PATTERN = re.compile(
    r"(screen recording|screen_recording|画面収録|画面録画)", re.IGNORECASE
)

# 一般的なスマートフォン/PC画面のアスペクト比(縦横どちらでも許容するため両方の比を保持)
_COMMON_SCREEN_ASPECT_RATIOS = [
    9 / 16, 9 / 19.5, 9 / 20, 3 / 4, 2 / 3, 1 / 1, 9 / 21,
]
_ASPECT_TOLERANCE = 0.03


@dataclass
class ScreenshotEstimate:
    is_screenshot: bool
    confidence: float  # 0.0-1.0


@dataclass
class ScreenRecordingEstimate:
    is_screen_recording: bool
    confidence: float


def _aspect_matches_screen(width: int, height: int) -> bool:
    if not width or not height:
        return False
    ratio = min(width, height) / max(width, height)
    return any(abs(ratio - common) < _ASPECT_TOLERANCE for common in _COMMON_SCREEN_ASPECT_RATIOS)


def estimate_screenshot(
    file_name: str,
    extension: str,
    width: int | None,
    height: int | None,
    camera_make: str | None,
    camera_model: str | None,
) -> ScreenshotEstimate:
    score = 0.0

    if _SCREENSHOT_NAME_PATTERN.search(file_name):
        score += 0.6

    has_no_camera_info = not camera_make and not camera_model
    if has_no_camera_info:
        score += 0.15

    if extension.lower() == ".png":
        score += 0.15

    if width and height and _aspect_matches_screen(width, height):
        score += 0.1

    confidence = min(score, 1.0)
    return ScreenshotEstimate(is_screenshot=confidence >= 0.5, confidence=confidence)


def estimate_screen_recording(
    file_name: str,
    width: int | None,
    height: int | None,
    fps: float | None,
) -> ScreenRecordingEstimate:
    score = 0.0

    if _SCREEN_RECORDING_NAME_PATTERN.search(file_name):
        score += 0.7

    if width and height and _aspect_matches_screen(width, height):
        score += 0.2

    # 画面録画は30fpsや60fpsぴったりのことが多く、カメラ動画特有の29.97/23.976等の
    # 分数フレームレートになりにくい傾向がある(あくまで弱いシグナル)
    if fps and abs(fps - round(fps)) < 0.01:
        score += 0.1

    confidence = min(score, 1.0)
    return ScreenRecordingEstimate(is_screen_recording=confidence >= 0.6, confidence=confidence)
