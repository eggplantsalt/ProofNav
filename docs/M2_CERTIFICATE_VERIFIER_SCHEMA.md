# ProofNav M2 Certificate 与 Verifier Schema

M1 的所有 `*.v1` wire contract 保持原字段集合。M2 通过
`proofnav/contracts.py::SCHEMA_VERSIONS` 新增独立版本，不静默扩展 M1 certificate v1。

## 1. 新增版本

| 名称 | 版本 |
|---|---|
| proof state | `proofnav.proof-state.v1` |
| evidence ledger | `proofnav.evidence-ledger.v1` |
| M2 certificate | `proofnav.certificate.v2` |
| online verification | `proofnav.online-verification.v1` |
| terminal decision | `proofnav.terminal-decision.v1` |
| controlled hidden truth | `proofnav.controlled-truth.v1` |
| offline verification | `proofnav.offline-verification.v1` |

## 2. Proof snapshot

Snapshot 的语义字段为：

```text
schema_version, episode_id,
scope_contract_id, scope_version, scope_digest,
state_version, proof_state_digest,
hypothesis_ids, obligations,
active_evidence, ledger_digest,
scope_closed, frontier_witnesses,
budget_status, cost_ledger, risk_claims,
observation_event_ids, ledger_event_count,
audit_trail
```

每项派生 obligation 包含 ID、hypothesis、predicate、necessary、status、support evidence IDs
和 refutation evidence IDs。`audit_trail` 保存 ledger version/event count/ordered hash-chain tip
和 scope provenance；每个 ledger event 另保存 admission scope version/digest；
`proof_state_digest` 使用 order-invariant semantic snapshot，二者职责分离。

## 3. Certificate v2

公共 exact fields：

```text
schema_version, certificate_id, certificate_digest,
certificate_type, requested_verdict,
episode_id, scope_contract_id, scope_version, scope_digest,
proof_state_version, proof_state_digest, ledger_digest,
budget_snapshot, cost_snapshot, risk_claim,
evidence_ids, obligation_ids, payload, provenance
```

`certificate_digest` 是去除 `certificate_id/certificate_digest` 后的 canonical SHA-256；ID 为
`cert-` 加 digest 前 20 个十六进制字符。

Positive payload：

```text
hypothesis_id
entity_binding {unit_id, binding_event_id}
true_path [{obligation_id, predicate_id, evidence_ids}]
unresolved_obligation_ids=[]
```

Refutation payload：

```text
hypothesis_index
refutation_cover [{hypothesis_id, obligation_id, predicate_id, evidence_ids}]
uncovered_hypothesis_ids=[]
frontier_unresolved=[]
```

Provenance 固定保存 builder version、选中 evidence 的 observation event IDs、adapter versions
和 ledger event count。隐藏 truth、evaluator label、完整图或 GT 字段不属于 certificate。

## 4. Online verification result

Exact output 包含：

```text
schema_version
status = ACCEPT | REJECT | DEFER
accepted, requested_verdict
reason_codes
missing_obligation_ids, uncovered_hypothesis_ids, frontier_witnesses
scope_digest, proof_state_digest, certificate_digest
structured_feedback
```

主要 reason taxonomy：

- identity/freshness：`SCOPE_*_MISMATCH`、`STALE_*`；
- coverage：`TRUE_PATH_INCOMPLETE`、`REFUTATION_COVER_INCOMPLETE`；
- evidence：`EVIDENCE_MISSING_OR_REVOKED`、`DUPLICATE_*`、`CONFLICTED_EVIDENCE`；
- frontier/scope：`SCOPE_NOT_CLOSED`、`FRONTIER_OPEN`；
- accounting：`RISK_*`、`BUDGET_*`、`COST_SNAPSHOT_MISMATCH`；
- firewall：`CONTROLLED_SOURCE_FORBIDDEN`、`EVIDENCE_ADAPTER_NOT_REGISTERED`；
- structure：`CERTIFICATE_*_INVALID`、`CERTIFICATE_VERDICT_MISMATCH`。

## 5. Offline result 与 terminal result

Offline outcome 为 `TRUE_ACCEPT/FALSE_ACCEPT/FALSE_REJECT/WRONG_SCOPE/UNRESOLVED`，同时保存
`online_offline_conflict`、`certificate_accepted_for_audit` 和 `audit_disposition`。发生冲突时
审计证书不被接受、disposition 为 `UNRESOLVED`；`feedback_to_runtime` 永远为 null。

Terminal output 记录 directive、是否 terminal、semantic verdict、真实 cause、certificate
acceptance、完整 online report/feedback 和正交的 DUET execution signal。它不是新的第四种
公开 verdict。
