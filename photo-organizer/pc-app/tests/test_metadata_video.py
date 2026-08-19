from pathlib import Path

from app.metadata_video import _parse_fps, _parse_location, extract_video_metadata


def test_parse_fps_from_fraction():
    assert _parse_fps("30000/1001") == 30000 / 1001


def test_parse_fps_from_plain_number():
    assert _parse_fps("25") == 25.0


def test_parse_fps_handles_invalid_input_gracefully():
    assert _parse_fps("not-a-number") is None


def test_parse_location_iso6709():
    lat, lon = _parse_location("+35.6895+139.6917/")
    assert round(lat, 4) == 35.6895
    assert round(lon, 4) == 139.6917


def test_parse_location_invalid_returns_none():
    lat, lon = _parse_location("invalid")
    assert lat is None and lon is None


def test_extract_video_metadata_missing_ffprobe_does_not_raise(tmp_path):
    """ffprobeが無い環境でも例外を投げず、エラー情報を返して処理を継続できること(仕様6)。"""
    dummy_video = tmp_path / "video.mp4"
    dummy_video.write_bytes(b"not a real video")
    meta = extract_video_metadata(dummy_video, ffprobe_path="ffprobe_that_does_not_exist")
    assert meta.errors  # 何らかのエラーメッセージが記録されている
    assert meta.duration_seconds is None


def test_extract_video_metadata_missing_file_does_not_raise(tmp_path):
    meta = extract_video_metadata(tmp_path / "not_found.mp4", ffprobe_path="ffprobe_that_does_not_exist")
    assert meta.errors
