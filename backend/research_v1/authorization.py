"""A user relay is provenance, never an independent research sign-off."""
import hashlib
import json
from pathlib import Path

SPEC_PATH = Path(__file__).with_name("spec.json")
SPEC = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
# Canonical JSON fingerprints survive Git's Windows/Linux line-ending
# normalization and harmless indentation changes. All values remain pinned.
SPEC_SHA256 = hashlib.sha256(json.dumps(SPEC, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def authorize(*, engineering_fixture=False):
    # Activation requires a separately recorded approval of the exact version,
    # all listed interpretations, and a future integration review. No CLI switch
    # can misrepresent the current user-relayed source as signed approval.
    if not engineering_fixture:
        raise PermissionError(
            f"Research execution blocked: {SPEC['version']} ({SPEC_SHA256}) requires "
            "independent written confirmation of the model and unresolved interpretations. "
            "--engineering-fixture verifies implementation only; it cannot produce validated experiment results."
        )
    return SPEC["label"]
