# M3-B champion report: explicit terminal-cut eligibility

## Precommit and implementation

The hypothesis, six confirmation scans, threshold `3.0`, four methods, unit and
continue rule were frozen in [M3B_SCIENTIFIC_PRECOMMIT.md](M3B_SCIENTIFIC_PRECOMMIT.md)
before collection (precommit file SHA at execution:
`8f7ba1b7adafe9575a66ed3f17ee93cca0b1cd47ed83a99a03fb119bade3cbdc`).

Implemented vertical slice:

- `proofnav/perception/terminal_signal.py`: exact self-sealed action-cut
  envelope; only explicit DUET STOP is `TERMINAL_SUPPORT`; normal moves are
  `SEARCH_PROPOSAL`; no-frontier/max-step are `FORCED_END_ABSTAIN`.
- `map_nav_src/reverie/agent_obj.py`: emits the envelope after the actual
  navigation action is selected, using the same forward pass and active mask;
  the sink rejects teacher/sample modes because their stop decision can use
  training supervision.
- `proofnav/offline/m3b_terminal_experiment.py`: filters the six frozen scans
  before loading annotation truth, evaluates the four frozen policies and
  computes exact binomial endpoints without making them runtime authority.
- `proofnav/perception/grounding_scope.py` and `terminal_adapter.py`: seal
  non-terminal, unsupported typed instructions and descriptive statistical
  artifacts as ABSTAIN.

All paths are default-off.  No M0 trace or legacy signal file is reused.

## Real collection

One forward collection was run with frozen DUET checkpoint, seed 0, batch size
8, `val_train_seen`, no training and no download.  Forward wall time was 8.24s.
No `val_unseen` or test split was accessed.

```text
signal file  .m3-results/signals/val_train_seen_terminal_confirm.jsonl
SHA-256      56af9957b6db740a397457e32291b9b873afae452407018e42ac8df3bdf465dc
rows         786 source rows
episodes     123 unique
interface    17bc1898b459e035b432ca057d880114d29a9dec2a73ebd0c572d865b762b8a4
```

The 16th batch padded the 123-example iterator with five earlier episodes.
This was caught before annotations were opened.  None belongs to the six
confirmation scans.  The report rejects any duplicate inside the confirmation
slice; the final sink is now idempotent on `(episode_id,event_seq)`.  The 134
confirmation records form 21 exact contiguous episode prefixes over six scans.

## Frozen result

| Method, same threshold 3.0 | error scans / 6 | false / true accepts | accepted episodes / 21 | hypothetical i.i.d. 95% upper |
|---|---:|---:|---:|---:|
| all-step M3-A | 3 | 5 / 21 | 21 | 0.8468 |
| episode maximum | 1 | 1 / 20 | 21 | 0.5818 |
| **explicit terminal cut** | **1** | **1 / 20** | **21** | **0.5818** |
| last active diagnostic | 1 | 1 / 20 | 21 | 0.5818 |

The champion passed the precommitted directional gate: fewer error scans and
at least half baseline episode coverage.  Here it preserved all observed
episode coverage.  This is seen-domain, scan-disjoint-from-discovery evidence,
not unseen-domain validation: the checkpoint trained on these environments.

Exact report:
`.m3-results/m3b_terminal_confirm/m3b_terminal_experiment_report.json`,
report digest `68412fc3d5a24299bd545dc17079332cbefa72c07409c63783478069b5f9aaa6`,
file SHA-256 `7b9da1bbdcde48d366ed3eb44f43822e3ee3c9bdc693d10ec1eff769ceb9d9c0`.

## Failure-to-design round 2

The remaining false claim is “purse in bathroom on first floor from hook on
wall.”  At STOP, target slot 304 is present but scores `0.714`; purse 311 scores
`5.560`.  Terminal timing therefore repairs premature binding but not
multi-instance typed identity.

Idea 2 is a null-aware, instruction-conditioned typed grounding head plus an
obligation-preserving compiler.  A conservative single-token grammar was
implemented as a safety firewall; its zero coverage on both 123
`val_train_seen` and 1423 `val_seen` instructions kills it as a method.  No
post-hoc rule was tuned on the six confirmation scans.  The learned typed head
was not trained because no legal scan-disjoint calibration labels exist in the
current resources and current signals retain only embedding digests, not the
values needed for the probe.

## Scientific verdict

**Directional mechanism success, strict-risk failure.**  Terminal-cut
eligibility is retained as a necessary primitive.  It does not authorize a
certificate: one error in six gives no 5% guarantee, exchangeability is not
established, and a descriptive artifact always yields UNRESOLVED.  The next
stage must jointly solve typed/null grounding and acquire enough independent
whole-policy calibration units before any production FOUND is reopened.
