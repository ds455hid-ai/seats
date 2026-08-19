from app.config import load_scoring_rules, load_settings
from app.models import MediaItem
from app.scoring import compute_deletion_score, determine_quality_flags

SETTINGS = load_settings()
RULES = load_scoring_rules(SETTINGS)
THRESHOLDS = RULES["thresholds"]


def make_photo(**kwargs) -> MediaItem:
    defaults = dict(
        id=1, file_name="a.jpg", absolute_path="/tmp/a.jpg", relative_path="a.jpg",
        root_folder="/tmp", media_type="photo", extension=".jpg", file_size=1000,
    )
    defaults.update(kwargs)
    return MediaItem(**defaults)


def make_video(**kwargs) -> MediaItem:
    defaults = dict(
        id=1, file_name="a.mov", absolute_path="/tmp/a.mov", relative_path="a.mov",
        root_folder="/tmp", media_type="video", extension=".mov", file_size=1000,
    )
    defaults.update(kwargs)
    return MediaItem(**defaults)


def test_scoring_rules_file_loads_with_expected_keys():
    assert "rules" in RULES
    assert "thresholds" in RULES
    assert RULES["rules"]["exact_duplicate_non_keep"] == 90


def test_determine_quality_flags_detects_blurry_photo():
    item = make_photo(blur_variance=10.0, brightness_mean=128.0, width=2000, height=2000)
    flags = determine_quality_flags(item, THRESHOLDS)
    assert flags.get("blurry") is True
    assert "too_dark" not in flags or flags["too_dark"] is False


def test_determine_quality_flags_detects_dark_photo():
    item = make_photo(blur_variance=300.0, brightness_mean=5.0, width=2000, height=2000)
    flags = determine_quality_flags(item, THRESHOLDS)
    assert flags.get("too_dark") is True
    assert flags.get("near_black") is True


def test_determine_quality_flags_corrupt_short_circuits_other_checks():
    item = make_photo(is_corrupt=True, blur_variance=1.0, brightness_mean=1.0)
    flags = determine_quality_flags(item, THRESHOLDS)
    assert flags == {"corrupt_or_unreadable": True}


def test_determine_quality_flags_normal_photo_has_no_flags():
    item = make_photo(blur_variance=300.0, brightness_mean=128.0, width=4000, height=3000)
    flags = determine_quality_flags(item, THRESHOLDS)
    assert flags == {}


def test_determine_quality_flags_large_video():
    item = make_video(file_size=THRESHOLDS["large_video_bytes"] + 1, duration_seconds=60.0, width=1920, height=1080)
    flags = determine_quality_flags(item, THRESHOLDS)
    assert flags.get("large_video") is True


def test_determine_quality_flags_too_short_video():
    item = make_video(file_size=1000, duration_seconds=0.5, width=1920, height=1080)
    flags = determine_quality_flags(item, THRESHOLDS)
    assert flags.get("too_short_video") is True


def test_compute_deletion_score_sums_multiple_reasons():
    flags = {"blurry": True, "too_dark": True}
    result = compute_deletion_score(flags, RULES)
    expected = RULES["rules"]["blurry"] + RULES["rules"]["too_dark"]
    assert result.score == expected
    assert set(result.reasons) == {"blurry", "too_dark"}


def test_compute_deletion_score_clips_at_100():
    flags = {"corrupt_or_unreadable": True, "blurry": True, "too_dark": True, "low_resolution": True}
    result = compute_deletion_score(flags, RULES)
    assert result.score <= 100


def test_compute_deletion_score_zero_when_no_flags():
    result = compute_deletion_score({}, RULES)
    assert result.score == 0
    assert result.reasons == []


def test_compute_deletion_score_never_exceeds_100_even_with_duplicate_flags():
    flags = {"corrupt_or_unreadable": True}
    result = compute_deletion_score(
        flags, RULES, is_exact_duplicate_non_keep=True, is_similarity_non_keep=True
    )
    assert 0 <= result.score <= 100
