import json

from app.manifest import build_manifest, write_manifest
from app.models import MediaItem


def make_item(**kwargs) -> MediaItem:
    defaults = dict(
        id=1, file_name="IMG_0001.jpg", absolute_path="/tmp/IMG_0001.jpg", relative_path="IMG_0001.jpg",
        root_folder="/tmp", media_type="photo", extension=".jpg", file_size=1234567,
        sha256="abc123", captured_at="2026-01-01T10:00:00", width=4032, height=3024,
    )
    defaults.update(kwargs)
    return MediaItem(**defaults)


def test_build_manifest_has_expected_top_level_structure():
    manifest = build_manifest([make_item()])
    assert manifest["version"] == 1
    assert "created_at" in manifest
    assert len(manifest["items"]) == 1


def test_build_manifest_item_fields_match_spec():
    manifest = build_manifest([make_item()])
    item = manifest["items"][0]
    assert item["media_id"] == "1"
    assert item["file_name"] == "IMG_0001.jpg"
    assert item["media_type"] == "photo"
    assert item["file_size"] == 1234567
    assert item["width"] == 4032
    assert item["height"] == 3024
    assert item["duration"] is None
    assert item["sha256"] == "abc123"
    assert item["iphone_local_identifier"] is None


def test_build_manifest_video_item_has_duration():
    video = make_item(id=2, media_type="video", extension=".mov", duration_seconds=12.5, width=1920, height=1080)
    manifest = build_manifest([video])
    assert manifest["items"][0]["duration"] == 12.5


def test_build_manifest_empty_list_produces_empty_items():
    manifest = build_manifest([])
    assert manifest["items"] == []


def test_write_manifest_produces_valid_json_file(tmp_path):
    output = tmp_path / "delete_manifest.json"
    write_manifest([make_item()], output)
    assert output.exists()
    with open(output, encoding="utf-8") as f:
        data = json.load(f)
    assert data["version"] == 1
    assert len(data["items"]) == 1
