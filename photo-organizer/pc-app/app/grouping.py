"""重複・類似写真/動画のグルーピング(Union-Find)。"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .hashing import hamming_distance
from .models import MediaItem


class UnionFind:
    def __init__(self, keys):
        self._parent = {k: k for k in keys}

    def find(self, x):
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra

    def groups(self) -> list[list]:
        result: dict = defaultdict(list)
        for k in self._parent:
            result[self.find(k)].append(k)
        return list(result.values())


def group_exact_duplicates(items: list[MediaItem]) -> list[list[MediaItem]]:
    """SHA-256が一致するアイテムをグループ化する(2件以上のみ)。写真・動画共通。"""
    buckets: dict[str, list[MediaItem]] = defaultdict(list)
    for item in items:
        if item.sha256:
            buckets[item.sha256].append(item)
    return [group for group in buckets.values() if len(group) > 1]


def _date_bucket_key(item: MediaItem) -> str:
    if item.captured_at:
        return item.captured_at[:10]  # YYYY-MM-DD
    return f"unknown::{item.media_type}"


def group_similar_photos(items: list[MediaItem], max_distance: int) -> list[list[MediaItem]]:
    """pHashのハミング距離が近い写真をグループ化する。

    パフォーマンス上の設計判断: まず撮影日(同日)でバケット分割し、バケット内のみで
    総当たり比較する。連写・同一シーン複数枚撮影はほぼ同日に集中するため、
    数万枚規模でも1バケットあたりの件数は現実的な範囲に収まる。
    captured_atが無い場合はmedia_typeごとの別バケットに入れる
    (このバケットが極端に大きい場合は比較件数が増える点は既知の限界とし、
    将来的にはハッシュのLSHバケット分割等でさらに高速化できる)。
    """
    hashed_items = [i for i in items if i.phash]
    buckets: dict[str, list[MediaItem]] = defaultdict(list)
    for item in hashed_items:
        buckets[_date_bucket_key(item)].append(item)

    all_groups: list[list[MediaItem]] = []
    for bucket_items in buckets.values():
        if len(bucket_items) < 2:
            continue
        uf = UnionFind([i.id for i in bucket_items])
        for idx_a in range(len(bucket_items)):
            for idx_b in range(idx_a + 1, len(bucket_items)):
                a, b = bucket_items[idx_a], bucket_items[idx_b]
                if hamming_distance(a.phash, b.phash) <= max_distance:
                    uf.union(a.id, b.id)

        id_to_item = {i.id: i for i in bucket_items}
        for group_ids in uf.groups():
            if len(group_ids) > 1:
                all_groups.append([id_to_item[i] for i in group_ids])

    return all_groups


def group_similar_videos(
    items: list[MediaItem],
    duration_tolerance_seconds: float = 2.0,
    size_ratio_tolerance: float = 0.25,
) -> list[list[MediaItem]]:
    """代表フレームを比較せず、時間・解像度・容量・撮影日から類似動画を推定する(仕様16)。

    同日・同解像度でバケット分割し、バケット内で動画時間とファイルサイズが
    近いものをグループ化する。
    """
    buckets: dict[str, list[MediaItem]] = defaultdict(list)
    for item in items:
        if item.duration_seconds is None:
            continue
        resolution_key = f"{item.width}x{item.height}"
        buckets[f"{_date_bucket_key(item)}::{resolution_key}"].append(item)

    all_groups: list[list[MediaItem]] = []
    for bucket_items in buckets.values():
        if len(bucket_items) < 2:
            continue
        uf = UnionFind([i.id for i in bucket_items])
        for idx_a in range(len(bucket_items)):
            for idx_b in range(idx_a + 1, len(bucket_items)):
                a, b = bucket_items[idx_a], bucket_items[idx_b]
                duration_close = abs(a.duration_seconds - b.duration_seconds) <= duration_tolerance_seconds
                size_close = (
                    min(a.file_size, b.file_size) / max(a.file_size, b.file_size, 1)
                    >= (1 - size_ratio_tolerance)
                )
                if duration_close and size_close:
                    uf.union(a.id, b.id)

        id_to_item = {i.id: i for i in bucket_items}
        for group_ids in uf.groups():
            if len(group_ids) > 1:
                all_groups.append([id_to_item[i] for i in group_ids])

    return all_groups


@dataclass
class KeepRecommendation:
    keep_media_id: int
    reason: str


def recommend_keep_photo(group: list[MediaItem]) -> KeepRecommendation:
    """類似写真グループの中から「残す推奨」の1枚を選ぶ(仕様9)。

    判断材料: ブレの少なさ・明るさ・解像度・破損の有無。
    あくまで推奨でありユーザーが変更可能(UI側でチェックボックス提供、仕様26)。
    """

    def score(item: MediaItem) -> float:
        if item.is_corrupt:
            return float("-inf")
        s = 0.0
        if item.width and item.height:
            s += (item.width * item.height) / 1_000_000.0
        if item.blur_variance is not None:
            s += min(item.blur_variance, 500.0) / 10.0
        if item.brightness_mean is not None:
            s -= abs(item.brightness_mean - 128.0) / 20.0
        return s

    best = max(group, key=score)
    return KeepRecommendation(keep_media_id=best.id, reason="解像度・鮮明さ・明るさが最も良好")


def recommend_keep_video(group: list[MediaItem]) -> KeepRecommendation:
    """類似動画グループの中から「残す推奨」の1本を選ぶ。解像度・ビットレート優先。"""

    def score(item: MediaItem) -> float:
        s = 0.0
        if item.width and item.height:
            s += (item.width * item.height) / 1_000_000.0
        if item.bitrate:
            s += item.bitrate / 1_000_000.0
        return s

    best = max(group, key=score)
    return KeepRecommendation(keep_media_id=best.id, reason="解像度・ビットレートが最も良好")
