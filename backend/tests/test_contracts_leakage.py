"""Defect 1 regression tests: hidden ground-truth information must not be
constructible on any monitoring-visible contract type.

Mission_NASA corrective review, Unified Prompt 4-5 Defect 1: `ObservationMetadata`
(the metadata on every AstronautDayObservation the monitoring engine, scheduler, and
frontend can see) used to carry `scenario_label`. It must not.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.models import (
    AstronautDayObservation,
    GroundTruthRecord,
    ObservationMetadata,
    SCHEMA_VERSION,
    ScenarioLabel,
)


def test_observation_metadata_has_no_scenario_label_field():
    assert "scenario_label" not in ObservationMetadata.model_fields


def test_observation_metadata_rejects_scenario_label_even_if_supplied():
    """extra='forbid' must actively reject the field, not just omit it from the
    schema - proving a caller cannot smuggle it back in."""
    with pytest.raises(ValidationError):
        ObservationMetadata(run_id="run-1", scenario_label="healthy")  # type: ignore[call-arg]


def test_astronaut_day_observation_has_no_onset_or_scenario_fields():
    """The full monitoring-visible record must not expose the hidden answer key
    anywhere, not just on its metadata sub-object."""
    fields = set(AstronautDayObservation.model_fields)
    assert "scenario_label" not in fields
    assert "sans_onset_day" not in fields
    assert "venous_onset_day" not in fields

    obs = AstronautDayObservation(
        astronaut_id="A1",
        day=1,
        metadata=ObservationMetadata(run_id="run-1"),
    )
    dumped = obs.model_dump()
    assert "scenario_label" not in dumped["metadata"]
    assert "scenario_label" not in dumped


def test_ground_truth_record_still_carries_scenario_and_onset_evaluation_only():
    """The hidden information must still exist SOMEWHERE - just confined to the
    evaluation-only ground-truth channel, never the monitoring-visible one."""
    gt = GroundTruthRecord(
        astronaut_id="A1",
        scenario_label=ScenarioLabel.SLOW_SANS,
        sans_onset_day=12,
        venous_onset_day=None,
        run_id="run-1",
    )
    assert gt.scenario_label == ScenarioLabel.SLOW_SANS
    assert gt.sans_onset_day == 12


def test_schema_version_bumped_for_this_breaking_change():
    assert SCHEMA_VERSION == "0.2.0"
