"""Code-owned minimal entity-only proof-template compiler for M3-A.

M3-A intentionally does not pretend to compile attribute, relation, room, or
residual semantics from free text.  This compiler establishes the smallest
registered domain: one necessary entity predicate bound to the exact
instruction digest.  Unsupported semantics remain an adapter ABSTAIN concern.
"""

from proofnav.contracts import SCHEMA_VERSIONS, canonical_sha256
from proofnav.runtime.semantics import validate_template


ENTITY_TEMPLATE_PRODUCER = (
    "proofnav.perception.entity_template.build_entity_proof_template"
)


def build_entity_proof_template(instruction):
    """Return a deterministic M2 proof-template v2 for one instruction."""

    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("instruction must be a non-empty string")
    instruction_digest = canonical_sha256(instruction)
    value = {
        "schema_version": SCHEMA_VERSIONS["proof_template"],
        "template_id": "template-entity-" + instruction_digest[:24],
        "generator_version": "proofnav.dynamic-universe.v2",
        "target_role": "target-object",
        "predicates": [{
            "predicate_id": "pred-entity-" + instruction_digest[:24],
            "kind": "entity",
            "necessary": True,
            "anchor_role": None,
            "spatial_anchor_id": None,
        }],
        "audit_trail": {
            "producer": ENTITY_TEMPLATE_PRODUCER,
            "source_instruction_digest": instruction_digest,
        },
    }
    return validate_template(value)
