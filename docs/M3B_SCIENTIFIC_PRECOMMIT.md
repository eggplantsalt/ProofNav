# ProofNav M3-B scientific precommit: terminal-cut evidence

> Frozen: 2026-08-13 UTC, before collecting the six confirmatory scans below.
> Status: exploratory mechanism selected; one-shot confirmatory slice not yet read.

## 1. Failure-derived hypothesis

The 193-record M3-A slice is now entirely exploratory.  Its three threshold-3
false SUPPORT events occur before the episode's final active observation; each
episode later exposes the correct target slot.  Raising the absolute-logit
threshold or selecting the episode maximum does not remove the strongest error.
This motivates, but does not confirm, the following hypothesis:

> A DUET object score is eligible for a positive proof atom only at the causal
> terminal cut selected by the navigation policy.  Earlier scores are search
> proposals, regardless of magnitude.

This is not an absence claim: STOP cannot close residual coverage and cannot
produce REFUTE or NOT_FOUND.  Terminal alignment is only an eligibility rule
for positive annotated-slot SUPPORT.

## 2. Frozen candidates and tournament

| Candidate | Layer | Cheapest discriminator | Frozen disposition |
|---|---|---|---|
| Higher/margin/entropy threshold | statistical post-processing | the high-margin, high-logit early false cases | killed as a sufficient repair; retained as baselines |
| Episode/scan familywise calibration | statistical semantics | one-sided scan-level bound and risk--coverage curve | mandatory accounting, not the champion mechanism |
| Terminal-cut eligibility | temporal evidence semantics | compare last active cut with all-step and episode-max at the same score threshold | champion |
| Target-slot + null lightweight head | grounding representation | scan-disjoint binary target/null probe | backup; needs legal training scans and is not trained in this precommit |
| Proof-obligation-guided active view acquisition | active evidence collection | extra-view marginal information per cost | later extension; requires M4 policy integration |

The champion wins the first tournament because it uniquely explains all three
minimal counterexamples without labels at runtime, new weights, an independence
assumption, or a threshold chosen from failures.  It may still be an ordinary
timing baseline rather than paper novelty; novelty remains contingent on a
certificate-level adaptive-control result and a fair comparison to standard
selective prediction and VLN-NF/ROAM.

## 3. One-shot confirmation boundary

Discovery/autopsy used these 21 scans and may not be called held out.  The only
confirmatory units are the six `val_train_seen` scans absent from that set:

```text
B6ByNegPMKs
D7N2EKCX4Sj
S9hNv5qa7GM
ac26ZMwG7aT
p5wJjkQkbXX
ur6pFq6Qu1A
```

They contain 21 instructions.  They are scan-disjoint from discovery, but the
frozen DUET checkpoint was trained on the corresponding train scans; therefore
this is a seen-domain mechanism check, not an unseen-scan population guarantee.
No `val_unseen` or test data may be opened.  The collection command may run the
full 123-example `val_train_seen` iterator once for deterministic access, but
the confirmatory report must filter to the six names above before reading labels.

Frozen methods, with no post-result tuning:

1. `all-step`: accept every valid selected slot with absolute logit `>=3.0`;
2. `episode-max`: accept the maximum-logit observation per episode at `>=3.0`;
3. `terminal-cut` (champion): accept only the policy's explicit DUET-STOP cut at
   `>=3.0`; no-frontier/max-step/environment-error endings abstain;
4. `last-active` diagnostic: last recorded observation at `>=3.0`, reported only
   to expose any difference from explicit DUET STOP.

Primary unit is scan.  A scan is an error if any accepted SUPPORT is false.
Also report accepted episodes / all episodes, true and false accepts, abstention,
observation count, wall time and GPU configuration.  The main comparison is
same-threshold error scans and episode coverage.  Descriptive risk--coverage
curves may be reported but cannot be used to alter the frozen rule.

Continue the champion only if it has fewer false-support scans than all-step and
retains at least half of all-step's accepted-episode coverage.  A tie at zero
errors is only directional evidence.  Any finite-sample claim must use a stated
one-sided scan-level confidence bound; zero observed errors is not zero risk.
At six independent scans, no conventional 95% bound can establish risk `<=.05`.

## 4. Runtime and certificate contract

- Evidence source must be the latest admitted observation at the certificate cut.
- `M3TerminalController` may accept FOUND only when the trusted execution seam
  reports a DUET STOP, not merely max-step/no-frontier.
- The terminal eligibility witness is agent-visible and must be bound to the
  same observation/action cut; caller text or an offline-derived last-row flag
  is not authority.
- Artifact, signal, complete prefix, template, model identity, query, binding,
  risk atom and terminal record remain separately sealed and independently
  audited.
- REFUTE, residual, NOT_FOUND, SAME_ENTITY, attribute, relation and room stay
  sealed.  Terminal alignment cannot manufacture any of them.

## 5. Claim and stop conditions

If confirmed, the strongest claim is limited to: DUET grounding confidence is
phase dependent; treating intermediate navigation scores as proof evidence
causes false SUPPORT, while a verifier-enforced terminal-cut eligibility rule
improves the observed selective risk--coverage trade-off on a bounded,
scan-disjoint seen-domain slice.

If the champion fails, the next and only backup probe is a target-slot + null
head on legally separated train/development/calibration scans.  If that also
fails, freeze the empirical finding that frozen DUET navigation features are
insufficient proof evidence and request the smallest auditable perception
augmentation.  None of these outcomes changes the false-premise VLN problem.
