"""Tests for generate_restyled.py (non-API functions only)."""

from generate_restyled import build_prompt, load_descriptions

import json
import os
import tempfile


def test_build_prompt_no_descriptions():
    batch_meta = {
        "batch_id": "batch_001",
        "cols": 2,
        "rows": 1,
        "sprites": [
            {"cell_row": 0, "cell_col": 0, "cell_label": "A1",
             "original_file": "a.png", "original_w": 64, "original_h": 64},
            {"cell_row": 0, "cell_col": 1, "cell_label": "A2",
             "original_file": "b.png", "original_w": 64, "original_h": 64},
        ],
    }
    prompt = build_prompt(batch_meta, "fantasy style")
    assert "2x1 grid" in prompt
    assert "fantasy style" in prompt
    assert "Row A Col 1: game sprite" in prompt
    assert "Row A Col 2: game sprite" in prompt


def test_build_prompt_with_descriptions():
    batch_meta = {
        "batch_id": "batch_001",
        "cols": 1,
        "rows": 1,
        "sprites": [
            {"cell_row": 0, "cell_col": 0, "cell_label": "A1",
             "original_file": "a.png", "original_w": 64, "original_h": 64},
        ],
    }
    with tempfile.TemporaryDirectory() as d:
        desc_path = os.path.join(d, "batch_001.json")
        with open(desc_path, "w") as f:
            json.dump({"A1": "a wooden bench"}, f)

        prompt = build_prompt(batch_meta, "fantasy style", descriptions_dir=d)
        assert "a wooden bench" in prompt


def test_load_descriptions_missing_dir():
    result = load_descriptions(None, "batch_001")
    assert result == {}


def test_load_descriptions_missing_file():
    with tempfile.TemporaryDirectory() as d:
        result = load_descriptions(d, "batch_999")
        assert result == {}
