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
- M2.1 Semantic Repair and Adversarial Falsification is frozen complete under the conditional claims in `docs/M2_ARCHITECTURE.md`. M3-A now has a default-off real DUET signal hook, an entity-SUPPORT-only calibrated successor, a code-owned artifact registry, and one bounded real compatibility slice. Its frozen absolute-logit artifact has descriptive scan-familywise risk `2/6`, so it is mechanically complete but failed the precommitted useful-risk (`alpha_F=0.05`) scientific gate. The project is at the M3-A→M3-B boundary: maintenance and CPU-only regression/audit work are allowed, but M0 reruns, M3-B head/data/calibration work, perception/coverage/identity expansion, M4 DUET rollout/re-ranking integration, M5 benchmark work, model training, formal paired-data generation, further GPU work, and formal experiments require explicit user authorization.
- When related work, equivalence, interface limits, or implementation risks are found, report them and prefer the smallest traceable adjustment inside the fixed ProofNav line.
- Report before any large data/model download, training or formal experiment, paid external API use, GPU-intensive work, destructive action, or push to a remote.
