# M3 statistical semantics audit

## The P0

The M3-A builder observed two error scans among six and stored `2/6` in a field
named `risk_bound.upper_bound`, while the same artifact declared
`confidence=null` and `descriptive_compatibility_not_statistical_guarantee`.
The adapter copied that value into a risk atom and the certificate composer
compared it with the caller's budget.  A budget of one therefore produced a
formal accept even though no finite-sample bound existed.  This was an
execution-semantics bug, not a documentation nuance.

The final code permits the descriptive artifact as a reproducible diagnostic
record but forbids certificate composition with
`M3_NO_STATISTICAL_GUARANTEE`.  Runtime verifier and independent offline audit
both reject any previously serialized descriptive certificate.

## Exact quantity and unit

For a frozen policy and threshold, one unit is one scan:

```text
Z_s = 1 iff any SUPPORT emitted by that frozen policy in scan s is false.
```

The observed quantity is `sum Z_s / n = 2/6 = 0.333333...`.  The 54
observations are correlated records inside six clusters and are not 54
independent trials.  The calibration artifact establishes neither random
sampling from a deployment population nor scan exchangeability; moreover,
the DUET checkpoint was trained on these seen environments.  Thus the legal
claim is descriptive `1/3`, with no confidence level.

For scale only, under an additional i.i.d. Bernoulli scan assumption, the
one-sided exact 95% Clopper--Pearson upper endpoint is:

| errors / scans | hypothetical 95% upper |
|---:|---:|
| 2 / 6 | 0.7286616274802475 |
| 1 / 6 | 0.5818034092520259 |
| 0 / 6 | 0.39303776899708276 |

With zero errors, at least
`ceil(log(0.05)/log(0.95)) = 59` independent units are needed before this
particular 95% upper endpoint can be at most `0.05`.  With one or two errors,
the corresponding minima are 93 and 124 units.  If the underlying error rate
stays near one third, more data cannot make a 5% guarantee true.

## What each layer may claim

| Layer | Valid claim |
|---|---|
| deterministic structural integrity | schema/hash/prefix/binding/cut/registry replay is internally valid |
| observed empirical error | exact familywise errors on the named finite scans |
| finite-sample upper confidence bound | only with method, confidence, unit, frozen selector and sampling assumptions recorded in a new artifact schema |
| distributional guarantee | only within the artifact's stated exchangeability/shift domain |
| certificate guarantee | only the independently recomputed bound of its selected complete policy event; never a caller value or descriptive frequency |

Any statistical successor must be v2 rather than silently changing v1.  At a
minimum it must bind `n`, `k`, loss/event, bound method, confidence/delta,
threshold-selection protocol, policy/horizon digest, unit and applicability
assumptions.  A scan-level bound for the whole terminal policy must be counted
once per scan; summing observation-level pseudo-atoms is the wrong statistical
object.

## Collision audit

The calibration layer is not the method novelty.  High-probability selective
risk control and reject options are covered by
[Geifman & El-Yaniv, NeurIPS 2017](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html);
risk-controlling prediction sets by
[Bates et al., JACM 2021](https://doi.org/10.1145/3478535);
expected monotone-loss control by
[Angelopoulos et al., ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html);
and multiple parameter tests by
[Learn then Test](https://arxiv.org/abs/2110.01052).
ProofNav may use these tools, but cannot claim their generic threshold,
abstention or conformal machinery as new.  Any surviving novelty must come
from the false-premise proof obligations, causal evidence-acquisition policy,
typed grounding and certificate-level terminal event.
