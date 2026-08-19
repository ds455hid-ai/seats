import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_test_image(path: Path, color=(255, 0, 0), size=(64, 64), noise_seed: int | None = None):
    """テスト用のシンプルな画像ファイルを作成する。"""
    from PIL import Image

    img = Image.new("RGB", size, color)
    if noise_seed is not None:
        import random

        rnd = random.Random(noise_seed)
        pixels = img.load()
        for _ in range(50):
            x = rnd.randrange(size[0])
            y = rnd.randrange(size[1])
            pixels[x, y] = (rnd.randrange(255), rnd.randrange(255), rnd.randrange(255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def make_pattern_image(path: Path, seed: int, size=(256, 256), quality: int = 95):
    """低周波のランダムパターンを持つテスト画像を作成する(pHash比較用)。

    単色画像はDCTの性質上pHashの挙動が不自然になりやすいため、
    構造を持つパターン画像を使うことでより現実的な比較ができる。
    """
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, size=(size[1] // 16, size[0] // 16, 3), dtype=np.uint8)
    img = Image.fromarray(small, "RGB").resize(size, Image.BILINEAR)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=quality)
    return path


@pytest.fixture
def tmp_images_dir(tmp_path):
    d = tmp_path / "images"
    d.mkdir()
    return d
