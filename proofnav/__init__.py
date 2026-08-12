"""M1 contracts and offline tooling for ProofNav.

This package deliberately contains no DUET model, policy, runtime certificate
constructor, or controller integration.  It is the CPU-only interface/data
contract slice used before M2.
"""

from .contracts import SCHEMA_VERSIONS, ContractViolation, semantic_verdict

__all__ = ["SCHEMA_VERSIONS", "ContractViolation", "semantic_verdict"]
