# ProofNav M2.1 Certificate / Verifier Successor Schemas

M1 的 observation/action/evidence/scope/obligation/certificate/result/pair v1 字段集合保持冻结。
M2.1 不把 typed binding 静默塞入这些 v1 对象，而是新增 successor envelope。

## 1. Version registry

| Contract | Version |
|---|---|
| proof state | `proofnav.proof-state.v2` |
| evidence ledger | `proofnav.evidence-ledger.v2` |
| proof template | `proofnav.proof-template.v2` |
| causal transition | `proofnav.proof-transition.v2` |
| controlled identity witness | `proofnav.controlled-identity-witness.v1` |
| bound evidence | `proofnav.bound-evidence.v2` |
| closure witness | `proofnav.closure-witness.v2` |
| decision audit bundle | `proofnav.decision-audit-bundle.v2` |
| M2 certificate | `proofnav.certificate.v3` |
| online report | `proofnav.online-verification.v2` |
| terminal decision | `proofnav.terminal-decision.v2` |
| controlled truth | `proofnav.controlled-truth.v2` |
| controlled evidence script | `proofnav.controlled-evidence-script.v2` |
| offline report | `proofnav.offline-verification.v2` |

旧 proof-state/ledger v1、certificate v2、terminal/report/truth v1 缺少 causal cut、dynamic universe
与 typed binding，不能安全自动迁移。必须从原始 admitted observation/evidence replay 重建。

## 2. Proof template and typed binding

Proof template exact fields：

```text
schema_version, template_id, generator_version, target_role,
predicates[{predicate_id,kind,necessary,anchor_role,spatial_anchor_id}],
audit_trail{producer,source_instruction_digest}
```

`kind = entity | attribute | relation | room_anchor`。relation 必须有 `anchor_role`；room-anchor
必须有 instruction-visible `spatial_anchor_id`。M2.1 最多允许一个 anchored predicate（relation 或
room-anchor），且必须是 necessary；更复杂 template fail closed。Generator 固定为
`proofnav.dynamic-universe.v2`。`audit_trail.source_instruction_digest` 必须等于每个 admitted
observation instruction 的 canonical SHA-256。

Typed binding exact fields：

```text
subject_binding_id, subject_unit_ids,
anchor_binding_id, anchor_unit_ids,
location_binding_id, spatial_anchor_id
```

Binding IDs 是 unit set 的 canonical hash，不是 adapter 自由标签。

## 3. Transition and audit bundle

Transition：

```text
schema_version, transition_seq, event_type,
parent_transition_digest, payload, payload_digest, transition_digest
```

Event type 为 `OBSERVATION/IDENTITY_LINK/QUERY/EVIDENCE/REVOKE/CONTINUE`。OBSERVATION payload
仍是严格 M1 observation v1；EVIDENCE payload 是：

```text
schema_version, query_id, hypothesis_id, obligation_id,
predicate_id, predicate_kind, binding,
source_observation_digest, evidence  # nested strict M1 evidence.v1
```

IDENTITY_LINK payload 是 controlled-only typed witness：

```text
schema_version, witness_id, claim=SAME_ENTITY,
endpoints[2]{unit_id,viewpoint_id,source_event_id,source_observation_digest},
audit_trail{producer,source_schema,observation_producer,
            observation_source_schema,interface_audit_ref}
```

两端必须来自 cut 前已 admitted 的不同 viewpoint；source observation 必须真实枚举该 unit；component
内 viewpoint→slot 保持 injective。Witness ID 是其规范内容的 hash，production admission 为 zero。

Decision audit bundle exact fields：

```text
schema_version, scope, template, admission_profile, risk_claims,
transitions, state, bundle_digest
```

`state` 是 cache/便捷读视图，不是 authority。Verifier 从前六项重算并要求 exact 相等。
`bundle_digest` 是去掉自身后整个 bundle 的 canonical SHA-256。

## 4. Derived proof state

主要 exact semantic fields：

```text
schema_version, episode_id,
scope_contract_id, scope_version, scope_digest,
template_id, template_digest,
state_version, decision_cut, transition_tip, proof_state_digest,
topology, closure_witness,
bindings, binding_digest,
hypotheses, hypothesis_ids, universe_digest,
obligations, queries,
active_bound_evidence, revoked_evidence_ids,
ledger_digest, ledger_event_count,
budget_status, cost_ledger, risk_claims, continue_count,
audit_trail
```

`decision_cut = {transition_seq,transition_digest,max_observation_event_seq,max_step}`。
Topology 保存 visited、discovered edges、frontier、ordered observation IDs 及 observation/visited/
edge/frontier digests。Closure witness 仅在 audited profile + derived empty frontier 时存在，并绑定
上述 digests、cut、scope/interface/generator、universe 与 binding。

Derived obligation 在 generator identity 外增加：

```text
status = OPEN | SATISFIED | REFUTED | CONFLICTED
support_evidence_ids, refutation_evidence_ids
```

Budget fields 为 `steps_used/observation_events/predicate_queries/within_budget/can_continue/
exhausted_resources`；cost fields 保留 travel/actions/edges/observations/queries/compute/storage/offline ref，
但值全部来自 transition fold。Identity witness 同时计入 predicate-query cost、ledger digest 与 ledger
event count。

Dynamic hypothesis kinds 为 `subject/subject_relation/subject_room/location_residual/anchor_residual`。
后两类只有一个 necessary `coverage` obligation，不能用于 FOUND；relation 的 `anchor_residual` 绑定
visible subject 与 location，用于结算未枚举 anchor 的剩余可能性。

## 5. Certificate v3

公共 exact fields：

```text
schema_version, certificate_id, certificate_digest,
certificate_type, requested_verdict,
episode_id, scope_contract_id, scope_version, scope_digest,
template_id, template_digest,
proof_state_version, decision_cut, transition_tip, proof_state_digest,
audit_bundle_digest, universe_digest, binding_digest, closure_witness,
ledger_digest, budget_snapshot, cost_snapshot, risk_claim,
hypothesis_ids, obligation_ids, evidence_ids,
payload, provenance
```

Digest 是去除 `certificate_id/certificate_digest` 后的 canonical SHA-256；ID 是 `cert-` 加 full
digest 的前 20 hex，只作标签。所有 identity 判断同时核对 full digest。

Positive payload：

```text
hypothesis                 # full dynamic hypothesis record
binding                    # exact typed substitution
true_path[coverage_item]
unresolved_obligation_ids=[]
```

Refutation payload：

```text
hypothesis_index           # full ordered dynamic universe
refutation_cover[coverage_item]
uncovered_hypothesis_ids=[]
frontier_unresolved=[]
```

Coverage item exact fields：

```text
hypothesis_id, hypothesis_kind, binding,
obligation_id, predicate_id, predicate_kind, evidence_ids
```

Provenance 保存 builder v2、admission profile ID、selected observation IDs、adapter versions 和
derived ledger event count。Hidden truth 与完整图不进入证书。

## 6. Online report v2

```text
schema_version
status = ACCEPT | REJECT | DEFER
accepted, requested_verdict
reason_codes, missing_obligation_ids, uncovered_hypothesis_ids
frontier_viewpoint_ids
scope_digest, template_digest, universe_digest, binding_digest
decision_cut, transition_tip, proof_state_digest
certificate_id, certificate_digest, calculated_certificate_digest
structured_feedback
```

Reason families：

- causal/bundle：`TRANSITION_*`, `AUDIT_BUNDLE_*`, `AUDIT_STATE_MISMATCH`；
- freshness：`STALE_*`, `*_MISMATCH`, `CLOSURE_WITNESS_MISMATCH`；
- topology/universe：`SCOPE_NOT_CLOSED`, `FRONTIER_OPEN`, `HYPOTHESIS_*`；
- binding/coverage：`POSITIVE_BINDING_INCOHERENT`, `REFUTATION_BINDING_INCOHERENT`,
  `TRUE_PATH_*`, `REFUTATION_COVER_*`；
- time/provenance：`FUTURE_EVIDENCE`, `EVIDENCE_*`, `CERTIFICATE_PROVENANCE_*`；
- accounting/risk：`BUDGET_*`, `COST_*`, `RISK_*`；
- firewall：`CONTROLLED_SOURCE_FORBIDDEN`, `EVIDENCE_ADAPTER_NOT_REGISTERED`；
- artifact identity：`CERTIFICATE_DIGEST_INVALID`, `CERTIFICATE_ID_INVALID`。

Malformed external input稳定返回 REJECT，不通过异常绕过 gate。

## 7. Terminal v2

```text
schema_version, directive, terminal, semantic_verdict, cause,
proposed_verdict,
proposed_certificate_id, proposed_certificate_digest,
accepted_certificate_id, accepted_certificate_digest,
decision_cut, transition_tip, proof_state_digest,
certificate_accepted, online_verification, feedback, duet_signal
```

ACCEPT 时 proposal/certificate/online/accepted identity 必须四方一致；REJECT/DEFER 时 accepted
identity 必须为 null。`CONTINUE_SEARCH` record 可作为下一条 causal transition；forced resource/error
只能产生 `FINALIZE_UNRESOLVED`，不能产生 NOT_FOUND。Recorded CONTINUE 还必须 exact 重验 terminal、
online report、feedback、prior cut/tip/state 和 execution signals；到达资源上限不能继续，但上限内已
形成的合法证书仍可接受。

## 8. Controlled truth, script and offline report

Truth v2 保存 scope/template/universe identity、full dynamic hypothesis/obligation catalogs、每个
obligation 的 typed `SUPPORTS/REFUTES/OPEN` fact evaluation，以及由其重算的 supported/refuted sets
和 semantic truth。Script v2 独立保存 emissions，可故意与 truth polarity 不同，但 query、hypothesis、
predicate、binding、source event 与 cut 必须合法。

Offline v2 outcome：

```text
TRUE_ACCEPT | FALSE_ACCEPT | FALSE_REJECT |
WRONG_SCOPE | CORRECT_REJECT | UNRESOLVED
```

Report 同时公开 structural/certificate/terminal validity、claim truth match、conflict、audit
disposition 与 reason codes；`feedback_to_runtime` 固定 null。
