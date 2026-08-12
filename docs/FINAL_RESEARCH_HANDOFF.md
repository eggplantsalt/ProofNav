# ProofNav final research handoff

> State at 2026-08-13. This file is sufficient to resume without chat logs.

## Current decision

The outer problem remains false-premise VLN on VLN-DUET. M0/M1 are frozen and
M2.1 is the valid event-sourced successor; the old bulk-snapshot M2 claim is
retired.

M3-A is structurally complete but statistically non-authoritative. Its opaque
signal, registered artifact and complete-prefix replay are reproducible, but
the artifact has descriptive error `2/6`, `confidence=null`. Budgets 1.0 and
0.05 both produce `UNRESOLVED` with `M3_NO_STATISTICAL_GUARANTEE`.

M3-B implemented and one-shot tested explicit terminal-cut eligibility. It
reduced confirmatory seen-domain error scans `3/6→1/6` with observed episode
coverage unchanged at `21/21`; retain it as a mechanism primitive. It does not
pass the strict risk gate and does not solve typed identity.

## Strongest honest center claim

> Frozen DUET object logits are strong conditional rankers when the annotated
> target slot is visible, but raw high scores are not proof of target presence
> or identity. Treating navigation-time scores as evidence creates rare,
> high-confidence false SUPPORTs. A causal terminal-cut gate materially reduces
> these errors without losing observed episode coverage, while a verifier that
> distinguishes empirical compatibility from statistical risk correctly
> refuses to certify the remaining typed-grounding error.

This is an empirical/mechanism finding, not yet a complete method paper. The
potential paper contribution is a future active proof policy with typed
null-aware grounding and whole-certificate scan-level risk control. Generic
selective/conformal calibration and the false-premise task are prior art.

## Exact assets

- M3-A signal: `.m3-results/signals/val_train_seen_opaque.jsonl`, SHA
  `43874168338d349e90c4111a21829552f68cfe4c33ba28240a832054b42c03bd`.
- registered artifact: `proofnav/calibration/artifacts/m3a_seen_micro.json`,
  digest `11caf45003b2d3f7fb5d3624f75e8b3ca964a5757a72728235e0f19d3bd58370`.
- M3-A report: `.m3-results/m3a_micro_slice_opaque/m3a_micro_slice_report.json`,
  SHA `1ac018c5c33c1ab5df414a773d401407b65b3375fe95850f3d77a9acd651c891`.
- M3-B precommit: `docs/M3B_SCIENTIFIC_PRECOMMIT.md`, execution SHA
  `8f7ba1b7adafe9575a66ed3f17ee93cca0b1cd47ed83a99a03fb119bade3cbdc`.
- M3-B signal: `.m3-results/signals/val_train_seen_terminal_confirm.jsonl`,
  SHA `56af9957b6db740a397457e32291b9b873afae452407018e42ac8df3bdf465dc`.
- M3-B report: `.m3-results/m3b_terminal_confirm/m3b_terminal_experiment_report.json`,
  canonical digest `68412fc3d5a24299bd545dc17079332cbefa72c07409c63783478069b5f9aaa6`,
  file SHA `7b9da1bbdcde48d366ed3eb44f43822e3ee3c9bdc693d10ec1eff769ceb9d9c0`.

Large `.m3-results` files must not be added to Git. Only source, tests, small
registry resources/manifests and documentation belong in version control.

## Key source files

- `proofnav/perception/terminal_signal.py`: explicit action-cut successor.
- `proofnav/perception/grounding_scope.py`: entity-only firewall.
- `proofnav/perception/terminal_adapter.py`: timing/template/statistics gates.
- `proofnav/calibration/risk.py`: descriptive certificate rejection.
- `proofnav/offline/structural_audit.py`: independent rejection.
- `proofnav/offline/m3b_terminal_experiment.py`: frozen evaluator.
- `map_nav_src/reverie/agent_obj.py`: real same-forward action/signal hook.

## Invariants

- No raw `instr_id`, target ID, annotation join, future observation or evaluator
  statistic in runtime state/signal/certificate.
- Admit an `(episode,event_seq)` once; seal prefix and selected signal.
- Search proposal, explicit STOP and forced termination have distinct semantics.
- Descriptive rate never becomes `risk_claim.upper_bound`, even at budget 1.
- Calibrate the frozen whole-policy false-certificate event once per independent
  scan, never observation rows as pseudo-replicates.
- REFUTE, residual, NOT_FOUND, SAME_ENTITY and attribute/relation/room evidence
  stay sealed until code-owned runtime and independent offline adapters exist.
- M3 stays default-off and frozen M1/M2.1 tests remain green.

## One next research line

Build a **null-aware typed grounding head followed by obligation-guided
continuation**, not another scalar threshold.

Before training: obtain legal scan-disjoint development/calibration/evaluation
units; freeze a typed compiler; collect actual frozen `vp_embeds`/slot values
with code-derived identities; train the smallest target-present/null plus typed
slot head; freeze the continuation policy; then calibrate its complete terminal
false-FOUND event at scan level. Cheapest killers are the purse multi-instance
case, the three target-absent high-confidence cases, nonzero matched-risk
coverage and feasibility of at least 59 independent zero-error units.

If frozen embeddings fail, request the smallest auditable image-language
augmentation. Do not jump directly to a large VLM or ordinary M4 reranking.

## Next-stage permission boundary

Maintenance, CPU falsification and documentation checks are safe. New training,
large model/data download, a `val_unseen` one-shot, paired-data generation or a
formal benchmark needs explicit authorization and a new precommit. Do not rerun
M0, reinstall the environment, reset the worktree, commit, push or add large
artifacts unless the user explicitly asks.
