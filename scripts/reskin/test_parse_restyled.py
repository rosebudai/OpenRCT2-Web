"""Tests for parse_restyled.py."""

import json
import os
import tempfile
import numpy as np
from PIL import Image

from parse_restyled import (
    restore_alpha,
    blend_tile_edges,
    validate_sprite,
    extract_sprites_from_grid,
)


def _make_sprite(w, h, color=(255, 0, 0, 200)):
    return Image.new("RGBA", (w, h), color)


def test_restore_alpha():
    """RGB from restyled, alpha from original."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 128))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        result = restore_alpha(restyled, orig_path)

        arr = np.array(result)
        assert arr[0, 0, 0] == 255  # red from restyled
        assert arr[0, 0, 3] == 128  # alpha from original


def test_restore_alpha_transparent_original():
    """Fully transparent original stays transparent."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        result = restore_alpha(restyled, orig_path)

        arr = np.array(result)
        assert (arr[:, :, 3] == 0).all()


def test_blend_tile_edges():
    """Edges should blend toward original."""
    restyled = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
    original = Image.new("RGBA", (20, 20), (0, 0, 255, 255))
    result = blend_tile_edges(restyled, original, edge_pixels=4)
    arr = np.array(result)
    # Corner (0,0) should be close to original (blue)
    assert arr[0, 0, 2] > arr[0, 0, 0]  # more blue than red
    # Center should be close to restyled (red)
    assert arr[10, 10, 0] > arr[10, 10, 2]  # more red than blue


def test_blend_tile_edges_tiny_sprite():
    """Tiny sprites shouldn't crash."""
    restyled = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    original = Image.new("RGBA", (4, 4), (0, 0, 255, 255))
    result = blend_tile_edges(restyled, original, edge_pixels=6)
    assert result.size == (4, 4)


def test_validate_sprite_different():
    """Sufficiently different sprite passes validation."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 255))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        ok, msg = validate_sprite(restyled, orig_path)
        assert ok
        assert "OK" in msg


def test_validate_sprite_too_similar():
    """Nearly identical sprite fails validation."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (100, 100, 100, 255))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (101, 100, 100, 255))
        ok, msg = validate_sprite(restyled, orig_path)
        assert not ok
        assert "Too similar" in msg


def test_validate_sprite_transparent():
    """Fully transparent sprite passes."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
        ok, msg = validate_sprite(restyled, orig_path)
        assert ok
