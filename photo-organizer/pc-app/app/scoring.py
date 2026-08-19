"""削除候補スコア(deletion_candidate_score)算出エンジン。

重要: このスコアは「ユーザーが確認する順番」を決めるためだけに使う。
スコアがどれだけ高くても、システムが自動的に削除することは絶対にない(仕様19)。
ルールの重み付けは config/scoring_rules.yaml で変更可能(仕様18)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import MediaItem

# 日本語の理由表示(UIで使う)
REASON_LABELS: dict[str, str] = {
    "exact_duplicate_non_keep": "完全重複(残す推奨以外)",
    "similarity_duplicate_rank2plus": "類似写真(残す推奨以外)",
    "blurry": "ピンぼけの可能性",
    "too_dark": "極端に暗い",
    "too_bright": "極端に明るい(白飛び)",
    "near_black": "ほぼ真っ黒",
    "low_resolution": "低解像度",
    "corrupt_or_unreadable": "破損・読み込み不可",
    "screenshot": "スクリーンショット(推定)",
    "screen_recording": "画面録画(推定)",
    "large_video": "大容量動画",
    "too_short_video": "短すぎる動画(誤撮影の可能性)",
    "low_quality_video": "低画質動画",
    "similar_video_rank2plus": "類似動画(残す推奨以外)",
}


@dataclass
class ScoreResult:
    score: int
    reasons: list[str]


def determine_quality_flags(item: MediaItem, thresholds: dict[str, Any]) -> dict[str, bool]:
    """写真・動画の数値メタデータから該当する品質フラグを求める。"""
    flags: dict[str, bool] = {}

    if item.is_corrupt:
        flags["corrupt_or_unreadable"] = True
        return flags  # 破損している場合は他の判定に意味がないため打ち切る

    if item.media_type == "photo":
        if item.blur_variance is not None:
            flags["blurry"] = item.blur_variance < thresholds["blur_laplacian_variance"]
        if item.brightness_mean is not None:
            flags["too_dark"] = item.brightness_mean < thresholds["dark_brightness_mean"]
            flags["near_black"] = item.brightness_mean < thresholds["near_black_brightness_mean"]
            flags["too_bright"] = item.brightness_mean > thresholds["bright_brightness_mean"]
        if item.width and item.height:
            flags["low_resolution"] = (item.width * item.height) < thresholds["low_resolution_pixels"]
        if item.is_screenshot:
            flags["screenshot"] = True

    elif item.media_type == "video":
        if item.file_size:
            flags["large_video"] = item.file_size >= thresholds["large_video_bytes"]
        if item.duration_seconds is not None:
            flags["too_short_video"] = item.duration_seconds < thresholds["too_short_video_seconds"]
        if item.width and item.height:
            flags["low_quality_video"] = (item.width * item.height) < thresholds["low_quality_video_pixels"]
        if item.is_screen_recording:
            flags["screen_recording"] = True

    return {k: v for k, v in flags.items() if v}


def compute_deletion_score(
    quality_flags: dict[str, bool],
    rules_config: dict[str, Any],
    is_exact_duplicate_non_keep: bool = False,
    is_similarity_non_keep: bool = False,
    is_similar_video_non_keep: bool = False,
) -> ScoreResult:
    rules = rules_config.get("rules", {})
    reasons: list[str] = []
    total = 0

    all_flags = dict(quality_flags)
    if is_exact_duplicate_non_keep:
        all_flags["exact_duplicate_non_keep"] = True
    if is_similarity_non_keep:
        all_flags["similarity_duplicate_rank2plus"] = True
    if is_similar_video_non_keep:
        all_flags["similar_video_rank2plus"] = True

    for flag_name, is_active in all_flags.items():
        if is_active and flag_name in rules:
            total += rules[flag_name]
            reasons.append(flag_name)

    total = max(0, min(100, total))
    return ScoreResult(score=total, reasons=reasons)


def reason_labels_ja(reasons: list[str]) -> list[str]:
    return [REASON_LABELS.get(r, r) for r in reasons]
