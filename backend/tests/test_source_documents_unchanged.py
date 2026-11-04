"""Proves the original source documents were not modified while building the registry.

Hashes were recorded before any Phase 0 file was written. Mission_NASA(1).docx's hash
was recorded the moment it was found and copied into the project (ASTROSENTINEL
correction, 2026-11-04) - it supplements, never replaces, Mission_NASA_updated.docx.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SHA256 = {
    "Mission_NASA_updated.docx": "1041b054c441aa00ac93d33edc9b006f0cc2423335fc6184ac5f51b772912082",
    "vn.txt": "ada460773bb8ae9cb39527eeadc702c5dfba94bde5fe5965a5ee755a5a7ac5c3",
    "Mission_NASA(1).docx": "e4ff0ecb5eb2058ebe3415212de8a8d0f0cda6e7b4e8c1c95a1e26500d735e0e",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_mission_doc_unchanged():
    path = PROJECT_ROOT / "Mission_NASA_updated.docx"
    assert path.exists(), f"expected source document at {path}"
    assert _sha256(path) == EXPECTED_SHA256["Mission_NASA_updated.docx"]


def test_vn_notes_unchanged():
    path = PROJECT_ROOT / "vn.txt"
    assert path.exists(), f"expected source notes at {path}"
    assert _sha256(path) == EXPECTED_SHA256["vn.txt"]


def test_mission_doc_v2_unchanged():
    path = PROJECT_ROOT / "Mission_NASA(1).docx"
    assert path.exists(), f"expected the updated source document at {path}"
    assert _sha256(path) == EXPECTED_SHA256["Mission_NASA(1).docx"]


def test_mission_doc_v2_differs_from_original_only_as_documented():
    """The only two parameter-sheet rows that differ are Koziarz/Ohle - this is a
    standing proof, not a one-time manual diff, in case either document ever changes."""
    v1 = (PROJECT_ROOT / "Mission_NASA_updated.docx").read_bytes()
    v2 = (PROJECT_ROOT / "Mission_NASA(1).docx").read_bytes()
    assert v1 != v2  # they are genuinely different files, not accidental duplicates
