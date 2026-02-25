"""Smoke tests for batch_sprites.py."""

import json
import os
import tempfile
from PIL import Image

from batch_sprites import load_sprites, create_batches, batch_sprites


def _make_sprite(dir_path, name, w, h):
    """Create a test sprite PNG."""
    img = Image.new("RGBA", (w, h), (255, 0, 0, 200))
    img.save(os.path.join(dir_path, name))


def test_load_sprites():
    with tempfile.TemporaryDirectory() as d:
        _make_sprite(d, "a.png", 64, 64)
        _make_sprite(d, "b.png", 128, 128)
        sprites = load_sprites(d)
        assert len(sprites) == 2
        assert sprites[0]["file"] == "a.png"
        assert sprites[0]["w"] == 64
        assert sprites[1]["file"] == "b.png"


def test_load_sprites_ignores_non_png():
    with tempfile.TemporaryDirectory() as d:
        _make_sprite(d, "a.png", 64, 64)
        with open(os.path.join(d, "readme.txt"), "w") as f:
            f.write("not a sprite")
        sprites = load_sprites(d)
        assert len(sprites) == 1


def test_create_batches_single_bucket():
    sprites = [{"file": f"s{i}.png", "w": 64, "h": 64} for i in range(4)]
    batches = create_batches(sprites)
    assert len(batches) == 1
    assert len(batches[0]["sprites"]) == 4


def test_create_batches_splits_at_16():
    sprites = [{"file": f"s{i}.png", "w": 64, "h": 64} for i in range(20)]
    batches = create_batches(sprites)
    assert len(batches) == 2
    assert len(batches[0]["sprites"]) == 16
    assert len(batches[1]["sprites"]) == 4


def test_create_batches_separates_sizes():
    sprites = [
        {"file": "small.png", "w": 32, "h": 32},
        {"file": "big.png", "w": 256, "h": 256},
    ]
    batches = create_batches(sprites)
    assert len(batches) == 2


def test_batch_sprites_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        sprites_dir = os.path.join(d, "sprites")
        batch_dir = os.path.join(d, "batches")
        os.makedirs(sprites_dir)

        for i in range(5):
            _make_sprite(sprites_dir, f"sprite_{i:03d}.png", 100, 80)

        manifest = batch_sprites(
            sprites_dir=sprites_dir,
            batch_dir=batch_dir,
            style_prompt="test style",
            tiling=True,
        )

        assert manifest is not None
        assert manifest["tiling"] is True
        assert manifest["style_prompt"] == "test style"
        assert len(manifest["batches"]) == 1
        assert len(manifest["batches"][0]["sprites"]) == 5

        # Grid image exists
        grid_path = manifest["batches"][0]["grid_file"]
        assert os.path.exists(grid_path)
        grid = Image.open(grid_path)
        assert grid.size == (2048, 2048)

        # Manifest JSON written
        manifest_path = os.path.join(batch_dir, "manifest.json")
        assert os.path.exists(manifest_path)
        with open(manifest_path) as f:
            loaded = json.load(f)
        assert loaded["version"] == 1
