from app.grouping import (
    UnionFind,
    group_exact_duplicates,
    group_similar_photos,
    group_similar_videos,
    recommend_keep_photo,
    recommend_keep_video,
)
from app.models import MediaItem


def make_item(
    id_,
    sha256=None,
    phash=None,
    captured_at="2026-01-01T10:00:00",
    media_type="photo",
    width=1000,
    height=1000,
    blur_variance=200.0,
    brightness_mean=128.0,
    is_corrupt=False,
    file_size=1_000_000,
    duration_seconds=None,
    bitrate=None,
) -> MediaItem:
    return MediaItem(
        id=id_,
        file_name=f"IMG_{id_}.jpg",
        absolute_path=f"/tmp/IMG_{id_}.jpg",
        relative_path=f"IMG_{id_}.jpg",
        root_folder="/tmp",
        media_type=media_type,
        extension=".jpg",
        file_size=file_size,
        sha256=sha256,
        phash=phash,
        captured_at=captured_at,
        width=width,
        height=height,
        blur_variance=blur_variance,
        brightness_mean=brightness_mean,
        is_corrupt=is_corrupt,
        duration_seconds=duration_seconds,
        bitrate=bitrate,
    )


def test_union_find_groups_transitively():
    uf = UnionFind([1, 2, 3, 4])
    uf.union(1, 2)
    uf.union(2, 3)
    groups = uf.groups()
    group_sizes = sorted(len(g) for g in groups)
    assert group_sizes == [1, 3]


def test_group_exact_duplicates_groups_same_sha256():
    items = [
        make_item(1, sha256="AAA"),
        make_item(2, sha256="AAA"),
        make_item(3, sha256="BBB"),
    ]
    groups = group_exact_duplicates(items)
    assert len(groups) == 1
    assert {i.id for i in groups[0]} == {1, 2}


def test_group_exact_duplicates_ignores_items_without_hash():
    items = [make_item(1, sha256=None), make_item(2, sha256=None)]
    assert group_exact_duplicates(items) == []


def test_group_similar_photos_merges_close_hashes_same_day():
    items = [
        make_item(1, phash="0000000000000000", captured_at="2026-01-01T10:00:00"),
        make_item(2, phash="0000000000000001", captured_at="2026-01-01T10:00:05"),  # 1ビット違い
    ]
    groups = group_similar_photos(items, max_distance=10)
    assert len(groups) == 1
    assert {i.id for i in groups[0]} == {1, 2}


def test_group_similar_photos_does_not_merge_far_hashes():
    """誤削除防止(仕様49): 明確に異なる写真は絶対にグループ化しない。"""
    items = [
        make_item(1, phash="0000000000000000", captured_at="2026-01-01T10:00:00"),
        make_item(2, phash="ffffffffffffffff", captured_at="2026-01-01T10:00:05"),  # 全ビット違い
    ]
    groups = group_similar_photos(items, max_distance=10)
    assert groups == []


def test_group_similar_photos_does_not_merge_across_different_days():
    """同じハッシュでも撮影日が別なら現行のバケット分割では別グループになりうる
    (誤って過去の別イベントの写真と混同しないための設計)。"""
    items = [
        make_item(1, phash="0000000000000000", captured_at="2026-01-01T10:00:00"),
        make_item(2, phash="0000000000000000", captured_at="2025-06-15T10:00:00"),
    ]
    groups = group_similar_photos(items, max_distance=10)
    assert len(groups) == 0


def test_recommend_keep_photo_prefers_sharper_and_less_corrupt():
    sharp = make_item(1, blur_variance=500.0, brightness_mean=128.0)
    blurry = make_item(2, blur_variance=5.0, brightness_mean=128.0)
    result = recommend_keep_photo([sharp, blurry])
    assert result.keep_media_id == 1


def test_recommend_keep_photo_never_recommends_corrupt_file():
    corrupt = make_item(1, is_corrupt=True, blur_variance=999.0)
    normal = make_item(2, is_corrupt=False, blur_variance=1.0)
    result = recommend_keep_photo([corrupt, normal])
    assert result.keep_media_id == 2


def test_group_similar_videos_merges_close_duration_and_size():
    items = [
        make_item(1, media_type="video", width=1920, height=1080, duration_seconds=10.0, file_size=50_000_000),
        make_item(2, media_type="video", width=1920, height=1080, duration_seconds=10.5, file_size=51_000_000),
    ]
    groups = group_similar_videos(items)
    assert len(groups) == 1


def test_group_similar_videos_does_not_merge_different_duration():
    items = [
        make_item(1, media_type="video", width=1920, height=1080, duration_seconds=5.0, file_size=50_000_000),
        make_item(2, media_type="video", width=1920, height=1080, duration_seconds=60.0, file_size=50_000_000),
    ]
    groups = group_similar_videos(items)
    assert groups == []


def test_recommend_keep_video_prefers_higher_resolution():
    hd = make_item(1, media_type="video", width=1920, height=1080, bitrate=8_000_000, duration_seconds=10)
    sd = make_item(2, media_type="video", width=640, height=480, bitrate=1_000_000, duration_seconds=10)
    result = recommend_keep_video([hd, sd])
    assert result.keep_media_id == 1
