"""Tests for describe_grid.py."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from describe_grid import parse_descriptions


def test_parse_descriptions_standard():
    output = "A1: A wooden park bench with armrests\nA2: A metal lamp post with round light"
    result = parse_descriptions(output, ["A1", "A2"])
    assert result["A1"] == "A wooden park bench with armrests"
    assert result["A2"] == "A metal lamp post with round light"


def test_parse_descriptions_markdown():
    output = "**A1:** A wooden park bench\n**A2:** A lamp post"
    result = parse_descriptions(output, ["A1", "A2"])
    assert "bench" in result["A1"]
    assert "lamp" in result["A2"]


def test_parse_descriptions_with_bullets():
    output = "- A1: A wooden bench\n- A2: A lamp post"
    result = parse_descriptions(output, ["A1", "A2"])
    assert "bench" in result["A1"]
    assert "lamp" in result["A2"]


def test_parse_descriptions_missing_label():
    output = "A1: A bench"
    result = parse_descriptions(output, ["A1", "A2"])
    assert "A1" in result
    assert "A2" not in result


def test_parse_descriptions_empty():
    result = parse_descriptions("", ["A1"])
    assert result == {}


def test_parse_descriptions_none():
    result = parse_descriptions(None, ["A1"])
    assert result == {}
