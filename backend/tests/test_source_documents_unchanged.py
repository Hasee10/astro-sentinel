"""Proves the original source documents were not modified while building the registry.

Hashes were recorded before any Phase 0 file was written.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SHA256 = {
    "Mission_NASA_updated.docx": "1041b054c441aa00ac93d33edc9b006f0cc2423335fc6184ac5f51b772912082",
    "vn.txt": "ada460773bb8ae9cb39527eeadc702c5dfba94bde5fe5965a5ee755a5a7ac5c3",
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
