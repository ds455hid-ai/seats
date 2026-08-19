from app.hashing import compute_photo_hashes, compute_sha256, hamming_distance
from conftest import make_pattern_image, make_test_image


def test_sha256_identical_files_match(tmp_path):
    make_test_image(tmp_path / "a.png", color=(10, 20, 30))
    make_test_image(tmp_path / "b.png", color=(10, 20, 30))
    assert compute_sha256(tmp_path / "a.png") == compute_sha256(tmp_path / "b.png")


def test_sha256_different_content_differs(tmp_path):
    make_test_image(tmp_path / "a.png", color=(10, 20, 30))
    make_test_image(tmp_path / "b.png", color=(200, 20, 30))
    assert compute_sha256(tmp_path / "a.png") != compute_sha256(tmp_path / "b.png")


def test_sha256_known_value(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello world")
    import hashlib

    assert compute_sha256(f) == hashlib.sha256(b"hello world").hexdigest()


def test_phash_identical_images_have_zero_distance(tmp_path):
    make_pattern_image(tmp_path / "a.jpg", seed=1)
    make_pattern_image(tmp_path / "b.jpg", seed=1)  # 同じシード=同じ画像
    phash_a, _ = compute_photo_hashes(tmp_path / "a.jpg")
    phash_b, _ = compute_photo_hashes(tmp_path / "b.jpg")
    assert phash_a == phash_b


def test_phash_resaved_image_is_closer_than_unrelated_image(tmp_path):
    """再圧縮(画質変更)した同一写真は、全く別の写真より距離が近いこと。

    類似写真検出はJPEG再圧縮程度の差では別グループにならないことを保証する。
    """
    make_pattern_image(tmp_path / "original.jpg", seed=42, quality=95)
    make_pattern_image(tmp_path / "resaved.jpg", seed=42, quality=60)  # 同じ内容・低画質再保存
    make_pattern_image(tmp_path / "unrelated.jpg", seed=999, quality=95)  # 全く別内容

    phash_orig, _ = compute_photo_hashes(tmp_path / "original.jpg")
    phash_resaved, _ = compute_photo_hashes(tmp_path / "resaved.jpg")
    phash_unrelated, _ = compute_photo_hashes(tmp_path / "unrelated.jpg")

    distance_to_resaved = hamming_distance(phash_orig, phash_resaved)
    distance_to_unrelated = hamming_distance(phash_orig, phash_unrelated)

    assert distance_to_resaved < distance_to_unrelated


def test_hamming_distance_identical_hashes_is_zero():
    assert hamming_distance("ffab", "ffab") == 0


def test_hamming_distance_counts_differing_bits():
    # 0x0 vs 0xF -> 4ビット差
    assert hamming_distance("0", "f") == 4


def test_compute_photo_hashes_returns_none_on_missing_file(tmp_path):
    phash, dhash = compute_photo_hashes(tmp_path / "does_not_exist.png")
    assert phash is None
    assert dhash is None
