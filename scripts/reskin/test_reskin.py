"""Tests for reskin.py orchestrator."""

import os
import sys
import tempfile
from unittest.mock import patch
from PIL import Image
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reskin import resolve_dirs, resolve_style, resolve_tiling


def test_resolve_dirs_workspace():
    with tempfile.TemporaryDirectory() as d:
        sprites = os.path.join(d, "sprites")
        os.makedirs(sprites)
        args = SimpleNamespace(
            workspace=d, sprites_dir=None,
            batch_dir=None, restyled_dir=None, output_dir=None,
        )
        s, b, r, o = resolve_dirs(args)
        assert s == sprites
        assert b == os.path.join(d, "batches")
        assert r == os.path.join(d, "restyled")
        assert o == sprites  # overwrites originals


def test_resolve_dirs_standalone():
    args = SimpleNamespace(
        workspace=None, sprites_dir="/tmp/my-sprites",
        batch_dir=None, restyled_dir=None, output_dir=None,
    )
    s, b, r, o = resolve_dirs(args)
    assert s == "/tmp/my-sprites"
    assert b == "/tmp/batches"
    assert r == "/tmp/restyled"
    assert o == "/tmp/my-sprites"


def test_resolve_style_explicit():
    args = SimpleNamespace(style="pixel art", category=None)
    assert resolve_style(args) == "pixel art"


def test_resolve_style_from_category():
    args = SimpleNamespace(style=None, category="scenery_small")
    style = resolve_style(args)
    assert "fantasy" in style.lower() or "cartoony" in style.lower()


def test_resolve_tiling_explicit():
    args = SimpleNamespace(tiling=True, no_tiling=False, category=None)
    assert resolve_tiling(args) is True


def test_resolve_tiling_from_category():
    args = SimpleNamespace(tiling=False, no_tiling=False, category="terrain")
    assert resolve_tiling(args) is True

    args = SimpleNamespace(tiling=False, no_tiling=False, category="scenery_small")
    assert resolve_tiling(args) is False
