"""Versioned contracts plus the isolated ProofNav M2 proof runtime.

The package deliberately contains no DUET model/policy integration, real
predicate perception, re-ranker, training, or benchmark runner.  Production
and controlled replay entry points remain separated in ``runtime`` and
``offline`` respectively.
"""

from .contracts import SCHEMA_VERSIONS, ContractViolation, semantic_verdict

__all__ = ["SCHEMA_VERSIONS", "ContractViolation", "semantic_verdict"]
