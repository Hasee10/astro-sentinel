"""Proves the original source documents were not modified while building the registry.

Hashes were recorded before any Phase 0 file was written. Mission_NASA(1).docx's hash
was recorded the moment it was found and copied into the project (ASTROSENTINEL
correction, 2026-11-04) - it supplements, never replaces, Mission_NASA_updated.docx.

vn.txt's hash is of its LINE-ENDING-NORMALIZED content, not its raw bytes (2026-11-11
consolidation correction). vn.txt is a plain-text file committed with CRLF line
endings, predating any line-ending convention in this repo. Two INDEPENDENT git
transport paths have been observed to silently rewrite CRLF to LF for this file
without touching a single word of content - a GitHub "Download ZIP" export, and
(confirmed while investigating that) `git show <rev>:vn.txt` and GitHub Actions'
checkout step, even with a `.gitattributes` `-text` override in place (`git
checkout --` respects it; those two code paths did not, in both cases reproducibly
and deterministically - verified by computing the CRLF-to-LF-normalized hash of the
original file by hand and finding it matches exactly). Hashing raw bytes therefore
makes this test fail on tooling/transport differences that never touch the actual
research notes - the opposite of what a content-integrity check should assert.
Normalizing before hashing keeps the test's real power (it still catches any
genuine edit to a single word) while dropping sensitivity to a representation
detail git itself does not guarantee stays stable across every consumer.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SHA256 = {
    "Mission_NASA_updated.docx": "1041b054c441aa00ac93d33edc9b006f0cc2423335fc6184ac5f51b772912082",
    "vn.txt": "5f251cd4f239a48463368b5d7ee97ff03776aafd431697084acd301d1ad63390",
    "Mission_NASA(1).docx": "e4ff0ecb5eb2058ebe3415212de8a8d0f0cda6e7b4e8c1c95a1e26500d735e0e",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_line_ending_normalized(path: Path) -> str:
    """For plain-text files only (never the binary .docx sources) - see module
    docstring for why raw bytes are the wrong thing to hash for vn.txt."""
    normalized = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def test_mission_doc_unchanged():
    path = PROJECT_ROOT / "Mission_NASA_updated.docx"
    assert path.exists(), f"expected source document at {path}"
    assert _sha256(path) == EXPECTED_SHA256["Mission_NASA_updated.docx"]


def test_vn_notes_unchanged():
    path = PROJECT_ROOT / "vn.txt"
    assert path.exists(), f"expected source notes at {path}"
    assert _sha256_line_ending_normalized(path) == EXPECTED_SHA256["vn.txt"]


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
