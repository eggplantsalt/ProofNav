"""Offline-only M2 oracle/replay and hidden-truth audit utilities."""

from .oracle_evidence import (
    ControlledProofState,
    OracleEvidenceProvider,
    ReplayOnlineVerifier,
    ReplayTerminalController,
    seal_controlled_artifact,
    validate_controlled_script,
    validate_controlled_truth,
)
from .oracle_verifier import OracleOfflineVerifier
from .calibration_builder import build_scan_familywise_artifact


def run_m3_micro_slice(signal_file, annotation_file, output_dir):
    """Lazily run the offline-only real-signal M3-A diagnostic."""

    from .m3_micro_slice import run  # pylint: disable=import-outside-toplevel
    return run(signal_file, annotation_file, output_dir)

__all__ = [
    "ControlledProofState",
    "OracleEvidenceProvider",
    "OracleOfflineVerifier",
    "ReplayOnlineVerifier",
    "ReplayTerminalController",
    "seal_controlled_artifact",
    "validate_controlled_script",
    "validate_controlled_truth",
    "build_scan_familywise_artifact",
    "run_m3_micro_slice",
]
