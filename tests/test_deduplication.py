"""Unit tests for grievance deduplication, similarity scoring, and merge workflows."""

import pytest
from app.services.deduplication_service import calculate_similarity, extract_block_name


def test_extract_block_name():
    assert extract_block_name("C Block, first floor") == "c block"
    assert extract_block_name("Science Block, laboratory corridor") == "science block"
    assert extract_block_name("A-105") == "a 105"
    assert extract_block_name("Library 2nd Floor") == "library"


def test_calculate_similarity_high_match():
    """Identical complaints in the same block should score high similarity (>0.70)."""
    score = calculate_similarity(
        title1="WiFi not working in C Block",
        desc1="Students cannot connect to the campus WiFi in C Block since morning.",
        loc1="C Block, first floor",
        cat1="IT / Network",
        title2="Internet not working in C Block",
        desc2="WiFi connection is down in C block rooms, students cannot access portal.",
        loc2="C Block, second floor",
        cat2="IT / Network",
    )
    assert score >= 0.65, f"Expected high similarity, got {score}"


def test_calculate_similarity_different_issues():
    """Unrelated complaints in different locations should score low similarity (<0.30)."""
    score = calculate_similarity(
        title1="WiFi not working in C Block",
        desc1="Students cannot connect to the campus WiFi in C Block since morning.",
        loc1="C Block, first floor",
        cat1="IT / Network",
        title2="Water leakage near laboratory",
        desc2="Water is leaking from a pipe near the laboratory entrance corridor.",
        loc2="Science Block, laboratory corridor",
        cat2="Water / Plumbing",
    )
    assert score <= 0.30, f"Expected low similarity, got {score}"
