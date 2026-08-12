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
from .terminal_signal import (
    TERMINAL_SIGNAL_PRODUCER,
    TERMINAL_SIGNAL_SCHEMA_VERSION,
    DuetTerminalSignalSink,
    build_terminal_signal,
    validate_terminal_signal,
)
from .grounding_scope import (
    GROUNDING_SCOPE_VERSION,
    classify_entity_only_instruction,
)
from .terminal_adapter import (
    TERMINAL_ADMISSION_SCHEMA_VERSION,
    adapt_terminal_entity_signal,
    validate_terminal_admission,
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
    "TERMINAL_SIGNAL_PRODUCER",
    "TERMINAL_SIGNAL_SCHEMA_VERSION",
    "DuetTerminalSignalSink",
    "build_terminal_signal",
    "validate_terminal_signal",
    "GROUNDING_SCOPE_VERSION",
    "classify_entity_only_instruction",
    "TERMINAL_ADMISSION_SCHEMA_VERSION",
    "adapt_terminal_entity_signal",
    "validate_terminal_admission",
]
