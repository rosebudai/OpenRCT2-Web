"""Tests for parse_restyled.py."""

import json
import os
import tempfile
import numpy as np
from PIL import Image

from parse_restyled import (
    restore_alpha,
    cleanup_black_artifacts,
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


def test_cleanup_black_artifacts():
    """Dark artifact pixels where original was bright should be replaced."""
    with tempfile.TemporaryDirectory() as d:
        # Original: bright orange opaque sprite
        orig = Image.new("RGBA", (10, 10), (200, 100, 50, 255))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        # Restyled: mostly silver (180) but rows 4-5 are a dark band (40)
        rest_arr = np.full((10, 10, 4), (180, 180, 180, 255), dtype=np.uint8)
        rest_arr[4:6, :, :3] = 40  # dark grey band
        restyled = Image.fromarray(rest_arr)

        result = cleanup_black_artifacts(restyled, orig_path)
        result_arr = np.array(result)
        # Dark band rows should now be bright (filled from neighbors)
        assert result_arr[5, 0, :3].max() > 100


def test_cleanup_black_no_artifacts():
    """When there are no artifacts, image is unchanged."""
    with tempfile.TemporaryDirectory() as d:
        orig = Image.new("RGBA", (10, 10), (200, 100, 50, 255))
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        restyled = Image.new("RGBA", (10, 10), (180, 180, 180, 255))
        result = cleanup_black_artifacts(restyled, orig_path)
        result_arr = np.array(result)
        assert (result_arr[:, :, 0] == 180).all()


def test_cleanup_black_preserves_intentional_dark():
    """Pixels that were dark in the original should stay dark."""
    with tempfile.TemporaryDirectory() as d:
        # Original has a dark outline at row 5
        orig_arr = np.full((10, 10, 4), (200, 100, 50, 255), dtype=np.uint8)
        orig_arr[5, :, :3] = 10  # dark outline in original
        orig = Image.fromarray(orig_arr)
        orig_path = os.path.join(d, "orig.png")
        orig.save(orig_path)

        # Restyled also has dark at row 5 (matching the original)
        rest_arr = np.full((10, 10, 4), (180, 180, 180, 255), dtype=np.uint8)
        rest_arr[5, :, :3] = 10
        restyled = Image.fromarray(rest_arr)

        result = cleanup_black_artifacts(restyled, orig_path)
        result_arr = np.array(result)
        # Row 5 should STAY dark since original was also dark
        assert result_arr[5, 0, :3].max() < 30


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
