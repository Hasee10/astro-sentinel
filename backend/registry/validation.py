"""Convention-based validation for numeric values nested inside a ScientificParameter's
structured (dict/list) ``value``.

Deliberately small: exact allowlists over the known key vocabulary actually used in
parameters.json, not a general-purpose schema engine. There are 26 parameters with a
fixed, known shape each - that makes allowlists the correct tool, not a shortcut.
"""
from __future__ import annotations

PERCENT_SEGMENT = "pct"
LIKELIHOOD_RATIO_KEYS = {"lr_positive", "lr_negative"}
NONNEGATIVE_UNIT_SEGMENTS = {"mm", "mm2", "cm2", "um", "min", "mmhg", "liters"}
DELTA_SEGMENTS = {"delta", "change", "drift"}
SAMPLE_SIZE_KEYS = {"cohort_n", "n"}
EVENT_COUNT_KEYS = {"stagnant_or_retrograde", "cases"}
NONNEGATIVE_COUNT_KEYS = {
    "cohort_n",
    "n",
    "held_out_scans",
    "studies_pooled",
    "stagnant_or_retrograde",
    "cases",
    "sweeps_averaged",
    "baseline_day_count",
}


def _segments(key: str) -> list[str]:
    return key.lower().split("_")


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _numeric_leaves(value) -> list[tuple[str, float]]:
    """(key, leaf_value) for every numeric leaf anywhere inside a nested dict/list.

    A list item inherits the dict key it was found under (or "" at the very top).
    """
    leaves: list[tuple[str, float]] = []

    def walk(node, key_hint: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key_hint)
        elif _is_number(node):
            leaves.append((key_hint, node))

    walk(value, "")
    return leaves


def validate_structured_value(parameter_id: str, value, top_level_unit: str | None = None) -> list[str]:
    """Return human-readable error strings for a structured (dict/list) value.

    Empty list means clean. Scalars/None/str are out of scope here - the model's own
    field validators already cover those.
    """
    errors: list[str] = []
    if not isinstance(value, (dict, list)):
        return errors

    for key, leaf in _numeric_leaves(value):
        effective_key = key if key else (top_level_unit or "")
        segs = _segments(effective_key)

        if key in LIKELIHOOD_RATIO_KEYS:
            if leaf < 0:
                errors.append(f"{parameter_id}: {key}={leaf} is a negative likelihood ratio")
            continue  # explicitly exempt from the percentage rule

        if PERCENT_SEGMENT in segs:
            if not (0 <= leaf <= 100):
                errors.append(f"{parameter_id}: {key or '(value)'}={leaf} is a percentage outside [0, 100]")
            continue

        if key in NONNEGATIVE_COUNT_KEYS:
            if leaf < 0 or leaf != int(leaf):
                errors.append(f"{parameter_id}: {key}={leaf} is not a valid non-negative count")
            continue

        if set(segs) & NONNEGATIVE_UNIT_SEGMENTS and not (set(segs) & DELTA_SEGMENTS):
            if leaf < 0:
                errors.append(f"{parameter_id}: {key or '(value)'}={leaf} is a negative physical measurement")

    errors.extend(_check_ordered_ranges(parameter_id, value))
    errors.extend(_check_event_counts_within_sample(parameter_id, value))
    return errors


def _check_ordered_ranges(parameter_id: str, value) -> list[str]:
    errors: list[str] = []

    def check_list(lst, key_hint: str) -> None:
        nums = [x for x in lst if _is_number(x)]
        if len(nums) == 2 and nums[0] > nums[1]:
            errors.append(f"{parameter_id}: {key_hint or '(value)'} range is not ordered (low > high): {lst}")

    def walk(node, key_hint: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, list):
                    check_list(v, k)
                walk(v, k)
            for k in node:
                if k.startswith("low_"):
                    suffix = k[len("low_"):]
                    high_key = f"high_{suffix}"
                    if high_key in node and _is_number(node[k]) and _is_number(node[high_key]):
                        if node[k] > node[high_key]:
                            errors.append(
                                f"{parameter_id}: {k}={node[k]} exceeds {high_key}={node[high_key]}"
                            )
        elif isinstance(node, list):
            check_list(node, key_hint)
            for item in node:
                walk(item, key_hint)

    walk(value, "")
    return errors


def _check_event_counts_within_sample(parameter_id: str, value) -> list[str]:
    errors: list[str] = []

    def check_dict(d: dict) -> None:
        sample_key = next((k for k in d if k in SAMPLE_SIZE_KEYS and _is_number(d[k])), None)
        if sample_key is None:
            return
        sample_n = d[sample_key]
        for k, v in d.items():
            if k in EVENT_COUNT_KEYS and _is_number(v) and v > sample_n:
                errors.append(f"{parameter_id}: {k}={v} exceeds sample size {sample_key}={sample_n}")

    def walk(node) -> None:
        if isinstance(node, dict):
            check_dict(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return errors
