"""Load and cross-validate the Scientific Parameter Registry and Experimental
Assumption Registry from their JSON data files.

Phase 0 scope only: this module reads and validates data. It performs no
monitoring, scheduling, or probability computation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from registry.models import ExperimentalAssumption, ScientificParameter

DATA_DIR = Path(__file__).parent / "data"
PARAMETERS_PATH = DATA_DIR / "parameters.json"
ASSUMPTIONS_PATH = DATA_DIR / "assumptions.json"


class RegistryLoadError(ValueError):
    """Raised when the registry JSON is malformed, duplicated, or fails cross-checks."""


def load_parameters(path: Path = PARAMETERS_PATH) -> dict[str, ScientificParameter]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RegistryLoadError(f"{path}: expected a JSON list of parameter entries")

    parameters: dict[str, ScientificParameter] = {}
    errors: list[str] = []
    for i, entry in enumerate(raw):
        try:
            parameter = ScientificParameter.model_validate(entry)
        except ValidationError as exc:
            errors.append(f"entry #{i} ({entry.get('parameter_id', '?')}): {exc}")
            continue
        if parameter.parameter_id in parameters:
            errors.append(f"duplicate parameter_id: {parameter.parameter_id!r}")
            continue
        parameters[parameter.parameter_id] = parameter

    if errors:
        raise RegistryLoadError(
            "Scientific Parameter Registry failed to load:\n" + "\n".join(errors)
        )
    return parameters


def load_assumptions(
    path: Path = ASSUMPTIONS_PATH,
    known_parameter_ids: frozenset[str] | None = None,
) -> dict[str, ExperimentalAssumption]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RegistryLoadError(f"{path}: expected a JSON list of assumption entries")

    assumptions: dict[str, ExperimentalAssumption] = {}
    errors: list[str] = []
    for i, entry in enumerate(raw):
        try:
            assumption = ExperimentalAssumption.model_validate(entry)
        except ValidationError as exc:
            errors.append(f"entry #{i} ({entry.get('assumption_id', '?')}): {exc}")
            continue
        if assumption.assumption_id in assumptions:
            errors.append(f"duplicate assumption_id: {assumption.assumption_id!r}")
            continue
        if known_parameter_ids is not None:
            unknown = [
                p for p in assumption.related_parameters if p not in known_parameter_ids
            ]
            if unknown:
                errors.append(
                    f"{assumption.assumption_id}: related_parameters not found in "
                    f"the Scientific Parameter Registry: {unknown}"
                )
        assumptions[assumption.assumption_id] = assumption

    if errors:
        raise RegistryLoadError(
            "Experimental Assumption Registry failed to load:\n" + "\n".join(errors)
        )
    return assumptions


@dataclass(frozen=True)
class Registry:
    parameters: dict[str, ScientificParameter]
    assumptions: dict[str, ExperimentalAssumption]


def load_all() -> Registry:
    """Load both registries, with assumption->parameter referential integrity checked."""
    parameters = load_parameters()
    assumptions = load_assumptions(known_parameter_ids=frozenset(parameters))
    return Registry(parameters=parameters, assumptions=assumptions)
