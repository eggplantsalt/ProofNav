# M3 failure atlas

Source: the frozen opaque 193-record M3-A signal.  This is exploratory
autopsy, not held-out confirmation.

## Aggregate taxonomy

| Partition | rows | scans | threshold TP | threshold FP | empty |
|---|---:|---:|---:|---:|---:|
| P0 development | 67 | 7 | 13 | 0 | 24 |
| P1 exposed calibration | 54 | 6 | 11 | 2 | 10 |
| P2 exposed diagnostic | 72 | 8 | 11 | 1 | 23 |
| total | 193 | 21 | 35 | 3 | 57 |

All 41 target-present records rank the target slot first, but only 35 exceed
the frozen absolute-logit threshold.  All three false SUPPORTs occur when the
true target slot is absent from the current proposal inventory.  They occur at
trajectory phases `0`, `0.4`, `0.5`; all 35 true threshold supports occur at
phase at least `0.714`.

## Minimal counterexamples

1. **Context proxy:** plant 452 is absent, decoration 376 scores `4.635` with
   margin `11.339`; six steps later the true plant scores `4.592`.
2. **Same-class instance:** chair 195 is absent, chair 286 scores `3.455`;
   “wicker” and “nearest kitchen entrance” are not represented in the generic
   entity obligation.
3. **Part--whole:** bed 178 is absent, bed/comforter 275 scores `6.345` with
   margin `14.666`; the true bed appears two steps later.

The remaining confirmatory terminal error is different: at explicit STOP, the
target purse 304 is present among 25 slots, but purse 311 scores `5.560` while
the target scores `0.714`.  The instruction requires bathroom, first-floor,
hook and wall grounding.  This falsifies terminal timing as a complete identity
solution and exposes the entity-only compiler's information loss.

## What was killed

- Raising a scalar score, margin, entropy, depth or box-area threshold is not a
  sufficient repair.  Two false supports are more confident than most true
  cases; post-hoc zero-error score/margin/entropy cuts retain only
  `16/35`, `14/35`, `16/35` true supports.
- Prefix maximum is killed by the plant/decoration case: the early wrong score
  remains larger than the later correct score.
- Two-distinct-view confirmation had zero observed errors but only `7/32`
  episode coverage in exposed data; it is a backup atom, not champion.
- A strict one-token entity-only grammar correctly abstains but covers `0/123`
  `val_train_seen` and `0/1423` `val_seen` instructions.  It is a firewall,
  not a viable method.

## What was not killed

- Target-present conditional slot ranking is strong, but presence/null and
  typed identity are not.
- Explicit terminal-cut eligibility reduces premature bindings and passed its
  frozen directional gate; it does not alone establish low risk.
- A null-aware, typed instruction/slot grounding head remains plausible and is
  the only representation-level backup worth new labels/training.
- Proof-obligation-guided continuation may turn terminal timing into a real
  active policy contribution, but it requires paired false-premise data and a
  new whole-policy calibration.
