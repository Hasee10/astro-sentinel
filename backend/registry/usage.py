"""Fail-closed usage gate for the Scientific Parameter Registry.

A future monitoring module must go through ``check_parameter_usage`` before using a
parameter's value for anything beyond reading/displaying it - it is the one place that
decides whether a given (parameter, operation, endpoint) combination is currently
authorized. Nothing else in this codebase grants that authorization implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass

from registry.loader import Registry
from registry.models import AuthorizedOperation, TargetMeasurement


@dataclass(frozen=True)
class UsageDecision:
    permitted: bool
    reason: str


def check_parameter_usage(
    registry: Registry,
    parameter_id: str,
    intended_operation: AuthorizedOperation,
    intended_endpoint: TargetMeasurement,
) -> UsageDecision:
    # Treatment is never authorized, for any parameter, under any assumption, ever.
    # Checked first and unconditionally - no parameter metadata can override this.
    if intended_operation == AuthorizedOperation.TREATMENT_DECISION:
        return UsageDecision(
            False, "treatment-related calculations are never authorized by this system"
        )

    parameter = registry.parameters.get(parameter_id)
    if parameter is None:
        return UsageDecision(False, f"unknown parameter_id: {parameter_id!r}")

    # Scientific reference display must remain possible even when predictive use is
    # prohibited - this is intentionally not gated on the parameter's own metadata.
    if intended_operation == AuthorizedOperation.REFERENCE_DISPLAY:
        return UsageDecision(True, "reference display is always permitted")

    # Everything else (today: PROBABILITY_INPUT) is fail-closed: scoped to the
    # parameter's own application domain, explicitly authorized by the parameter, and
    # backed by at least one approved + active assumption. Right now every parameter's
    # authorized_operations is empty, so this always rejects - correctly, since no
    # probability calculation is authorized anywhere yet.
    if parameter.target_measurement != intended_endpoint:
        return UsageDecision(
            False,
            f"{parameter_id} is scoped to {parameter.target_measurement.value}, "
            f"not {intended_endpoint.value}",
        )
    if intended_operation not in parameter.authorized_operations:
        return UsageDecision(
            False, f"{parameter_id} does not authorize {intended_operation.value}"
        )

    active_backing = [
        a
        for a in registry.assumptions.values()
        if parameter_id in a.related_parameters and a.is_active()
    ]
    if not active_backing:
        return UsageDecision(
            False,
            f"no approved, active assumption authorizes {intended_operation.value} "
            f"using {parameter_id}",
        )
    return UsageDecision(
        True, f"authorized via approved assumption(s): {[a.assumption_id for a in active_backing]}"
    )
