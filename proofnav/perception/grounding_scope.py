"""Conservative instruction-domain gate for the entity-only M3 slice.

This is deliberately a firewall, not a semantic parser.  The current DUET
entity head cannot certify attributes, relations, rooms, ordinals, or
multi-instance descriptions.  Only a minimal single-token entity imperative
is admitted as representable; everything richer requires a typed successor.
"""

import re

from proofnav.contracts import canonical_sha256


GROUNDING_SCOPE_VERSION = "proofnav.entity-only-instruction-scope.v1"
_MINIMAL = re.compile(
    r"^(?:find|locate|grab|take)\s+(?:(?:the|a|an)\s+)?"
    r"(?P<entity>[a-z][a-z-]*)[.!]?$",
    re.IGNORECASE,
)


def classify_entity_only_instruction(instruction):
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("instruction must be a non-empty string")
    normalized = " ".join(instruction.strip().split())
    match = _MINIMAL.fullmatch(normalized)
    result = {
        "schema_version": GROUNDING_SCOPE_VERSION,
        "instruction_digest": canonical_sha256(instruction),
        "entity_only_eligible": bool(match),
        "reason_code": (
            "MINIMAL_ENTITY_ONLY_GRAMMAR" if match
            else "UNSUPPORTED_TYPED_GROUNDING"
        ),
        "entity_token": match.group("entity").lower() if match else None,
    }
    result["scope_digest"] = canonical_sha256(result)
    return result


__all__ = ["GROUNDING_SCOPE_VERSION", "classify_entity_only_instruction"]
