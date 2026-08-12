"""M3 perception boundaries; all production paths remain default-off."""

from .duet_signal import (
    DUET_SIGNAL_PRODUCER,
    DUET_SIGNAL_SCHEMA_VERSION,
    DuetSignalSink,
    build_duet_signal,
)
from .entity_template import (
    ENTITY_TEMPLATE_PRODUCER,
    build_entity_proof_template,
)
from .evidence_adapter import (
    ADAPTER_PRODUCER,
    ADAPTER_VERSION,
    adapt_entity_signal,
    build_calibrated_bound_evidence,
    validate_adapter_decision,
    validate_duet_signal,
)

__all__ = [
    "DUET_SIGNAL_PRODUCER",
    "DUET_SIGNAL_SCHEMA_VERSION",
    "DuetSignalSink",
    "build_duet_signal",
    "ENTITY_TEMPLATE_PRODUCER",
    "build_entity_proof_template",
    "ADAPTER_PRODUCER",
    "ADAPTER_VERSION",
    "adapt_entity_signal",
    "build_calibrated_bound_evidence",
    "validate_adapter_decision",
    "validate_duet_signal",
]
