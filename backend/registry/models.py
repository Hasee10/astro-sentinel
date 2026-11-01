"""Typed schema for the Scientific Parameter Registry and Experimental Assumption Registry.

Phase 0 / 0.1 only: data modeling and validation. No monitoring, scheduling, or
probability logic lives here or anywhere else yet.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from registry.validation import validate_structured_value

ParameterValue = Union[float, int, str, dict, list, None]


class EvidenceClassification(str, Enum):
    """The document's own evidence label for a parameter, as written."""

    ESTABLISHED = "established"
    HYPOTHESIS = "hypothesis"
    ASSUMPTION = "assumption"
    DESIGN = "design"
    MODEL = "model"


class VerificationStatus(str, Enum):
    """Whether the primary source behind a parameter has actually been opened and checked.

    A value being ``ESTABLISHED`` above does not imply ``VERIFIED`` here — the source
    document itself flags almost every "Established" row as still needing that check.
    """

    OPEN_PAPER = "open_paper"
    CONFIRM = "confirm"
    NOT_SOURCED = "not_sourced"
    FIND_PRIMARY_SOURCE = "find_primary_source"
    UNSPECIFIED = "unspecified"
    VERIFIED = "verified"


class TargetMeasurement(str, Enum):
    """Which monitoring endpoint this project applies a parameter to.

    This is the APPLICATION domain (SANS / venous / not clinical) - not necessarily
    what the original cited study measured. See ``original_study_endpoint`` for that;
    the two are often different on purpose (e.g. an ICU/ICP study applied to SANS).
    """

    SANS = "sans"
    VENOUS = "venous"
    NOT_CLINICAL = "not_clinical"


class AuthorizedOperation(str, Enum):
    """What a future module may do with a parameter's value.

    A parameter's own ``authorized_operations`` may only ever list REFERENCE_DISPLAY
    and/or PROBABILITY_INPUT. TREATMENT_DECISION exists only so a caller can *request*
    it (and be refused) - no parameter may ever carry it as an authorization, and the
    usage validator (registry/usage.py) rejects it unconditionally regardless of data.
    """

    REFERENCE_DISPLAY = "reference_display"
    PROBABILITY_INPUT = "probability_input"
    TREATMENT_DECISION = "treatment_decision"


class ScientificParameter(BaseModel):
    """One traceable entry from the Mission_NASA_updated.docx parameter sheet (Table 4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_id: str
    name: str
    value: ParameterValue = None
    unit: Optional[str] = None
    source_name: str
    source_document: str
    source_location: str
    original_study_context: str
    original_study_endpoint: str
    target_measurement: TargetMeasurement
    evidence_classification: EvidenceClassification
    verification_status: VerificationStatus
    permitted_use: str
    authorized_operations: list[AuthorizedOperation] = []
    limitations: str

    @field_validator("parameter_id")
    @classmethod
    def _id_is_snake_case(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("parameter_id must be non-empty")
        if v != v.strip() or " " in v or v.lower() != v:
            raise ValueError(f"parameter_id must be lowercase snake_case: {v!r}")
        return v

    @field_validator(
        "name",
        "source_name",
        "source_document",
        "source_location",
        "original_study_context",
        "original_study_endpoint",
        "permitted_use",
        "limitations",
    )
    @classmethod
    def _non_empty_text(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be non-empty")
        return v

    @field_validator("authorized_operations")
    @classmethod
    def _no_treatment_authorization_in_data(cls, v: list) -> list:
        if AuthorizedOperation.TREATMENT_DECISION in v:
            raise ValueError(
                "authorized_operations may never include TREATMENT_DECISION - this "
                "system never authorizes treatment, unconditionally, by design"
            )
        return v

    @model_validator(mode="after")
    def _numeric_unit_and_range(self) -> "ScientificParameter":
        if isinstance(self.value, (int, float)) and not isinstance(self.value, bool):
            if not self.unit or not self.unit.strip():
                raise ValueError(
                    f"{self.parameter_id}: a numeric value requires a non-empty unit"
                )
            numeric_value = float(self.value)
            if self.unit == "%" and not (0.0 <= numeric_value <= 100.0):
                raise ValueError(
                    f"{self.parameter_id}: percentage value {self.value} is outside [0, 100]"
                )
            if self.unit in {"mm", "mm2", "min", "count", "um", "cm2"} and numeric_value < 0:
                raise ValueError(
                    f"{self.parameter_id}: a {self.unit} measurement cannot be negative"
                )
        return self

    @model_validator(mode="after")
    def _nested_structured_values(self) -> "ScientificParameter":
        errors = validate_structured_value(self.parameter_id, self.value, top_level_unit=self.unit)
        if errors:
            raise ValueError(f"{self.parameter_id}: " + "; ".join(errors))
        return self


class ApprovalStatus(str, Enum):
    UNAPPROVED = "unapproved"
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class AssumptionKind(str, Enum):
    """Whether an assumption, once approved, is meaningless without an assigned number.

    NUMERICAL assumptions (an SD, a threshold, a swept accuracy range) cannot be
    activated with a null value - that was the exact gap the review demonstrated.
    SCOPE_DECISION assumptions (may a cutoff be reused, at what confidence) don't need
    a number, but still need a recorded decision: on approval, ``value_or_range`` must
    hold the decision text itself.
    """

    NUMERICAL = "numerical"
    SCOPE_DECISION = "scope_decision"


class ExperimentalAssumption(BaseModel):
    """A simulation-only assumption slot. Phase 0/0.1 seeds the slot; it does not fill it.

    Approval metadata (``approved_by``) records that a human signed off. It is not an
    authentication mechanism and does not verify the approver's identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assumption_id: str
    description: str
    value_or_range: Optional[Union[float, str, dict, list]] = None
    scientific_purpose: str
    assumption_kind: AssumptionKind
    related_parameters: list[str] = []
    approval_status: ApprovalStatus
    approved_by: Optional[str] = None
    limitations: str

    @field_validator("assumption_id")
    @classmethod
    def _id_is_snake_case(cls, v: str) -> str:
        if not v or not v.strip() or v != v.strip() or " " in v or v.lower() != v:
            raise ValueError(f"assumption_id must be non-empty lowercase snake_case: {v!r}")
        return v

    @field_validator("description", "scientific_purpose", "limitations")
    @classmethod
    def _non_empty_text(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be non-empty")
        return v

    @model_validator(mode="after")
    def _approval_consistency(self) -> "ExperimentalAssumption":
        approved_by_set = bool(self.approved_by and self.approved_by.strip())

        if self.approval_status != ApprovalStatus.APPROVED and approved_by_set:
            raise ValueError(
                f"{self.assumption_id}: approved_by must be empty unless status is APPROVED"
            )

        if self.approval_status == ApprovalStatus.UNAPPROVED and self.value_or_range is not None:
            raise ValueError(
                f"{self.assumption_id}: value_or_range must be null while status is UNAPPROVED "
                f"- no numerical or decision value may be assigned before human approval"
            )

        if self.approval_status == ApprovalStatus.APPROVED:
            if not approved_by_set:
                raise ValueError(
                    f"{self.assumption_id}: APPROVED status requires a non-empty approved_by"
                )
            if self.assumption_kind == AssumptionKind.NUMERICAL:
                if self.value_or_range is None or isinstance(self.value_or_range, str):
                    raise ValueError(
                        f"{self.assumption_id}: a NUMERICAL assumption cannot be APPROVED "
                        f"without an assigned numeric/range value_or_range (a bare string "
                        f"is not a usable value for a numerical assumption)"
                    )
            else:  # SCOPE_DECISION
                if not (isinstance(self.value_or_range, str) and self.value_or_range.strip()):
                    raise ValueError(
                        f"{self.assumption_id}: a SCOPE_DECISION assumption cannot be "
                        f"APPROVED without a recorded decision - value_or_range must be a "
                        f"non-empty string stating exactly what was approved"
                    )
        return self

    def is_active(self) -> bool:
        """An assumption may only be treated as active by a future module if this is True."""
        if self.approval_status != ApprovalStatus.APPROVED:
            return False
        if not (self.approved_by and self.approved_by.strip()):
            return False
        if self.assumption_kind == AssumptionKind.NUMERICAL:
            return self.value_or_range is not None and not isinstance(self.value_or_range, str)
        return isinstance(self.value_or_range, str) and bool(self.value_or_range.strip())
