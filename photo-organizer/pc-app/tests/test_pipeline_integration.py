"""パイプライン全体(スキャン→解析→重複/類似判定→スコア)の結合テスト。"""
import shutil
from pathlib import Path

from app import db
from app.config import Settings, load_scoring_rules
from app.pipeline import run_grouping_and_scoring, scan_and_analyze
from conftest import make_pattern_image


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "db" / "test.db",
        thumbnail_cache_dir=tmp_path / "thumbs",
        scoring_rules_path=Path(__file__).resolve().parent.parent / "config" / "scoring_rules.yaml",
        worker_count=1,
        batch_size=50,
        max_video_frames=3,
    )


def test_scan_and_analyze_detects_exact_duplicates(tmp_path):
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    original = make_pattern_image(photos_dir / "IMG_0001.jpg", seed=1)
    shutil.copyfile(original, photos_dir / "IMG_0001_copy.jpg")  # 完全に同じ内容
    make_pattern_image(photos_dir / "IMG_0002.jpg", seed=2)  # 別内容

    settings = build_settings(tmp_path)
    conn = db.get_connection(settings.database_path)
    try:
        summary = scan_and_analyze(conn, settings, photos_dir)
        assert summary["total_files"] == 3
        assert summary["processed"] == 3
        assert summary["errors"] == 0

        rules = load_scoring_rules(settings)
        grouping_summary = run_grouping_and_scoring(conn, settings, rules)
        assert grouping_summary["exact_duplicate_groups"] == 1

        dup_rows = conn.execute("SELECT * FROM duplicate_groups").fetchall()
        assert len(dup_rows) == 1
        assert dup_rows[0]["item_count"] == 2

        # 完全重複の非推奨側にのみ delete_candidates が作られていること
        candidates = conn.execute(
            "SELECT media_id FROM delete_candidates WHERE deletion_candidate_score >= 90"
        ).fetchall()
        assert len(candidates) == 1
    finally:
        conn.close()


def test_incremental_scan_skips_unchanged_files(tmp_path):
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    make_pattern_image(photos_dir / "IMG_0001.jpg", seed=1)

    settings = build_settings(tmp_path)
    conn = db.get_connection(settings.database_path)
    try:
        first = scan_and_analyze(conn, settings, photos_dir)
        assert first["processed"] == 1
        assert first["skipped_unchanged"] == 0

        second = scan_and_analyze(conn, settings, photos_dir)
        assert second["processed"] == 0
        assert second["skipped_unchanged"] == 1
    finally:
        conn.close()


def test_scan_and_analyze_continues_after_unreadable_file(tmp_path):
    """1件が壊れたファイルでも、スキャン全体は止まらないこと(仕様6)。"""
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    make_pattern_image(photos_dir / "good.jpg", seed=1)
    (photos_dir / "broken.jpg").write_bytes(b"this is not a real jpeg file")

    settings = build_settings(tmp_path)
    conn = db.get_connection(settings.database_path)
    try:
        summary = scan_and_analyze(conn, settings, photos_dir)
        assert summary["total_files"] == 2
        assert summary["processed"] == 2  # 壊れたファイルも「解析失敗」として記録されるが処理は継続する

        broken_row = conn.execute(
            "SELECT is_corrupt FROM media_items WHERE file_name = 'broken.jpg'"
        ).fetchone()
        assert broken_row["is_corrupt"] == 1
    finally:
        conn.close()
