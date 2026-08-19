"""誤削除防止テスト(仕様49): 「違う写真・動画」を誤って重複/類似と判定しないこと。

ここではPC側の重複・類似判定ロジックを対象にする。
iPhone側のPHAsset照合(MATCHED/AMBIGUOUS/NOT_FOUND)についてはSwift側のXCTestで検証する
(iphone-app/PhotoOrganizerTests/AssetMatcherTests.swift)。
"""
from app.grouping import group_exact_duplicates, group_similar_photos, group_similar_videos
from app.models import MediaItem
from tests.test_grouping import make_item


def test_same_captured_at_but_different_content_is_not_exact_duplicate():
    """撮影日時が同じでも、ファイル内容(sha256)が違えば完全重複にしない。"""
    items = [
        make_item(1, sha256="AAA", captured_at="2026-01-01T10:00:00"),
        make_item(2, sha256="BBB", captured_at="2026-01-01T10:00:00"),
    ]
    assert group_exact_duplicates(items) == []


def test_same_filename_different_content_is_not_exact_duplicate():
    """ファイル名が同じでも中身が違えば重複にしない(IMG_0001.jpgが複数フォルダにある等)。"""
    item_a = make_item(1, sha256="AAA")
    item_b = make_item(2, sha256="BBB")
    item_a.file_name = item_b.file_name = "IMG_0001.jpg"
    assert group_exact_duplicates([item_a, item_b]) == []


def test_similar_file_size_alone_does_not_trigger_similarity_grouping():
    """ファイルサイズが近いだけで、pHashが大きく異なる写真は類似グループにしない。"""
    items = [
        make_item(1, phash="0000000000000000", file_size=1_000_000, captured_at="2026-01-01T10:00:00"),
        make_item(2, phash="ffffffffffffffff", file_size=1_010_000, captured_at="2026-01-01T10:00:00"),
    ]
    groups = group_similar_photos(items, max_distance=10)
    assert groups == []


def test_items_without_phash_are_excluded_from_similarity_grouping():
    """知覚ハッシュが取得できなかった(=不確実な)写真は類似判定の対象に含めない。"""
    items = [
        make_item(1, phash=None, captured_at="2026-01-01T10:00:00"),
        make_item(2, phash=None, captured_at="2026-01-01T10:00:00"),
    ]
    assert group_similar_photos(items, max_distance=10) == []


def test_same_video_duration_but_different_resolution_is_not_grouped():
    """動画時間が同じでも解像度が違えば別動画として扱う(誤って結合しない)。"""
    items = [
        make_item(1, media_type="video", width=1920, height=1080, duration_seconds=30.0, file_size=50_000_000),
        make_item(2, media_type="video", width=640, height=480, duration_seconds=30.0, file_size=50_000_000),
    ]
    assert group_similar_videos(items) == []


def test_same_duration_but_very_different_file_size_is_not_grouped():
    """動画時間が同じでもファイルサイズが大きく異なれば別動画として扱う。"""
    items = [
        make_item(1, media_type="video", width=1920, height=1080, duration_seconds=30.0, file_size=10_000_000),
        make_item(2, media_type="video", width=1920, height=1080, duration_seconds=30.1, file_size=200_000_000),
    ]
    assert group_similar_videos(items) == []


def test_missing_metadata_photo_falls_back_to_unknown_bucket_not_merged_with_dated_photos():
    """撮影日時が欠損した写真は、撮影日時が判明している写真と誤って同じグループにしない。"""
    items = [
        make_item(1, phash="0000000000000000", captured_at=None),
        make_item(2, phash="0000000000000000", captured_at="2026-01-01T10:00:00"),
    ]
    groups = group_similar_photos(items, max_distance=10)
    assert groups == []  # 別バケットになるため統合されない


def test_exact_duplicate_grouping_requires_sha256_not_just_size_match():
    """ファイルサイズが完全一致していても、sha256が無い/異なる場合は重複としない。"""
    a = make_item(1, sha256=None, file_size=5_000_000)
    b = make_item(2, sha256=None, file_size=5_000_000)
    assert group_exact_duplicates([a, b]) == []
