# ProofNav repository rules

Before any work, read:

- [Codebase beginner guide](docs/CODEBASE_BEGINNER_GUIDE.md)
- [Project master plan](docs/PROJECT_MASTER_PLAN.md)
- [Code-grounded design review](docs/CODE_GROUNDED_DESIGN_REVIEW.md)

Long-lived rules:

- Check `git status` first. Preserve user files and existing changes; never overwrite them silently.
- Run version and worktree checks at most once at task start and once at task end; do not repeat branch, commit, remote, or identical status queries unless an external change or version contradiction is detected.
- Locate the real entry point and call chain before editing.
- After an implementation, run the smallest relevant non-destructive validation.
- Distinguish source-confirmed facts, actually run validation, unverified procedures, engineering inference, and research design.
- The fixed research line is false-premise VLN with ProofNav on the VLN-DUET base; the first-stage benchmarks are REVERIE, VLN-NF when its official artifacts are available, and a strictly paired REVERIE extension. An agent must not change the direction, benchmark, or base repository.
- M2.1 is frozen complete under the conditional claims in `docs/M2_ARCHITECTURE.md`. M3-A has a default-off real DUET hook, opaque lineage and an exact signal/prefix registry, but its `2/6` artifact is descriptive-only: every certificate budget now fails closed with `M3_NO_STATISTICAL_GUARANTEE`. M3-B's precommitted terminal-cut probe reduced seen-domain error scans `3/6→1/6` at unchanged observed episode coverage `21/21`, but did not pass strict risk or typed grounding. The unique next line is a null-aware typed grounding head followed by proof-obligation-guided continuation and whole-policy scan calibration. REFUTE/relation/room/coverage/identity, live attestation, M4/M5, training, paired data and any `val_unseen`/test experiment require a new explicit authorization and precommit. See `docs/FINAL_RESEARCH_HANDOFF.md`.
- When related work, equivalence, interface limits, or implementation risks are found, report them and prefer the smallest traceable adjustment inside the fixed ProofNav line.
- Report before any large data/model download, training or formal experiment, paid external API use, GPU-intensive work, destructive action, or push to a remote.
