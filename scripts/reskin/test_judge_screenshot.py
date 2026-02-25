"""Tests for judge_screenshot.py — prompt construction and rating parsing."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the reskin package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from judge_screenshot import (  # noqa: E402
    PROMPT_COMPARISON,
    PROMPT_SINGLE,
    build_prompt,
    parse_rating,
)


# ---------------------------------------------------------------------------
# build_prompt tests
# ---------------------------------------------------------------------------


def test_build_prompt_single_image():
    """Prompt for a single screenshot uses the single-image template."""
    prompt = build_prompt("shot.png")
    assert prompt == PROMPT_SINGLE
    assert "rendering correctly" in prompt
    assert "Rate quality" in prompt


def test_build_prompt_with_reference():
    """Prompt with a reference image uses comparison language."""
    prompt = build_prompt("reskinned.png", reference="original.png")
    assert prompt == PROMPT_COMPARISON
    assert "Compare these two screenshots" in prompt
    assert "reskin" in prompt.lower()


def test_build_prompt_with_criteria():
    """Custom criteria is appended to the prompt."""
    extra = "Check if trees look natural"
    prompt = build_prompt("shot.png", criteria=extra)
    assert prompt.startswith(PROMPT_SINGLE)
    assert prompt.endswith(extra)
    assert extra in prompt


def test_build_prompt_with_reference_and_criteria():
    """Comparison prompt with extra criteria appends correctly."""
    extra = "Focus on building rooftops"
    prompt = build_prompt("shot.png", reference="ref.png", criteria=extra)
    assert "Compare these two screenshots" in prompt
    assert extra in prompt


# ---------------------------------------------------------------------------
# parse_rating tests
# ---------------------------------------------------------------------------


def test_parse_rating_valid():
    """Standard X/10 pattern is extracted."""
    assert parse_rating("Overall I'd rate this 7/10.") == 7
    assert parse_rating("Rating: 9/10") == 9
    assert parse_rating("I give it a 10 / 10!") == 10
    assert parse_rating("Quality: 1/10 — very bad") == 1


def test_parse_rating_missing():
    """Returns None when no rating pattern is found."""
    assert parse_rating("Looks fine overall, nice colors.") is None
    assert parse_rating("") is None
    assert parse_rating("Score: excellent") is None


def test_parse_rating_ignores_out_of_range():
    """Ratings outside 1-10 are ignored."""
    # 0/10 is out of our 1-10 range
    assert parse_rating("0/10 terrible") is None


def test_parse_rating_picks_first_match():
    """When multiple ratings appear, the first is returned."""
    text = "Visual quality: 6/10. Technical quality: 8/10."
    assert parse_rating(text) == 6
