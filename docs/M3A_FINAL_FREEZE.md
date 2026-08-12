# M3-A final freeze

> Frozen 2026-08-13.  This document supersedes earlier M3-A success wording.

## Verdict

M3-A is **engineering-complete and scientifically REVISE**.  The default-off
DUET hook, opaque runtime episode lineage, exact signal/prefix registry,
event-sourced M2.1 admission, runtime verifier and independently implemented
offline auditor form a reproducible structural chain.  The registered
calibration summary is descriptive, not a population-risk guarantee, so it
cannot authorize FOUND at any risk budget.

The only honest capability is:

> Given the official annotated candidate-slot interface, emit a non-target-
> oracle DUET entity-score proposal, preserve it as diagnostic SUPPORT
> evidence, and abstain at certificate composition unless a future exact
> statistical artifact and supported instruction template both validate.

This is not a detector, open-world discovery, residual coverage, or complete
false-premise resolver.

## Current identities

| Item | Frozen identity |
|---|---|
| opaque signal JSONL | `.m3-results/signals/val_train_seen_opaque.jsonl`, SHA-256 `43874168338d349e90c4111a21829552f68cfe4c33ba28240a832054b42c03bd` |
| records | 193 active records, 32 episodes, 21 scans; no repeated ended suffix |
| artifact | `proofnav/calibration/artifacts/m3a_seen_micro.json`, digest `11caf45003b2d3f7fb5d3624f75e8b3ca964a5757a72728235e0f19d3bd58370` |
| aggregate | 6 scans / 54 observations including 10 null / 2 error scans; empirical `1/3`; `confidence=null` |
| registered replay | five-observation exact prefix ending in signal `5730b8a877cbff8ff14d3a59c0257b620b9414be8d60d53955800d03f848a441` |
| final CPU report | `.m3-results/m3a_micro_slice_opaque/m3a_micro_slice_report.json`, file SHA-256 `1ac018c5c33c1ab5df414a773d401407b65b3375fe95850f3d77a9acd651c891` |

The old raw-target-ID, ended-row and final-signal-only artifacts are revoked.
They remain only as `.m3-results` diagnostics and have no registry entry.
Production registry contains only the current `11caf...` resource and its exact
opaque signal/prefix manifests.

## Closed P0/P1 items

- Runtime episode/event/scope IDs are derived from the agent-visible
  `(scan,start_viewpoint,instruction)` tuple, not raw REVERIE `instr_id`; the
  annotation join exists only in the offline evaluator.
- Every relevant observation in the fixed replay is registry-sealed.  A changed
  pose/event prefix plus the exact final signal fails runtime and independent
  offline audit.
- Ended batch rows are not emitted as fresh events.  The M3-B successor also
  makes its JSONL sink idempotent on `(episode_id,event_seq)` to reject final-
  batch iterator wrap as a new statistical sample.
- Caller-provided risk, lower resealed aggregate, fabricated signal, wrong
  model/template/interface identity, stale evidence and unregistered artifact
  fail closed.
- A descriptive empirical rate can still be stored in a diagnostic atom, but
  `compose_certificate_risk` raises `M3_NO_STATISTICAL_GUARANTEE`; the offline
  certificate audit independently returns
  `OFFLINE_M3_NO_STATISTICAL_GUARANTEE`.

The old budget-1 mechanical `TRUE_ACCEPT` is therefore revoked.  Re-running the
CPU runner on the same frozen signal gives `UNRESOLVED` for both budgets `1.0`
and `0.05`, with reason `M3_NO_STATISTICAL_GUARANTEE`.

## Truth and capability firewall

Runtime signal/state/certificate code contains no target object ID, annotation
join, future observation, evaluator label or per-example error statistic.
Hidden truth is opened only after terminal output is immutable.  REFUTE,
residual coverage, NOT_FOUND, attribute, relation, room and SAME_ENTITY remain
sealed.  The BBoxes-backed slots condition the grounding claim: the system
does not claim proposal discovery or detector completeness.

The remaining provenance limit is explicit: model identity hashes supplied to
the historical extraction CLI are not cryptographic process attestation.  The
fixed allowlist authenticates this replay, not arbitrary future live signals.
A live successor requires code-derived resource identity or a process-bound
capability and a new independent auditor.

## Reproduction

```bash
cd /root/autodl-tmp/ProofNav
PYTHONPATH=. /root/autodl-tmp/vlnduet-m0/bin/python \
  -m proofnav.offline.m3_micro_slice \
  --signal-file .m3-results/signals/val_train_seen_opaque.jsonl \
  --annotation-file datasets/REVERIE/annotations/REVERIE_val_train_seen_enc.json \
  --output-dir .m3-results/m3a_micro_slice_opaque
```

No GPU collection is required to reproduce this final M3-A decision.
