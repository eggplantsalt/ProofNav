# ProofNav M3-A code-driven changelog

> **Final P0R supersession (2026-08-13):** Earlier active-only identities below (`61eec…`,
> `d254…`, raw `2401_51_0`) are retained only as red-team history. The final hook replaces
> target-bearing REVERIE `instr_id` with `runtime-episode-<SHA256(scan,start,instruction)>`,
> and the registry seals the five-observation demo prefix in addition to its signal.
> Final identities: signal JSONL `43874168338d349e90c4111a21829552f68cfe4c33ba28240a832054b42c03bd`,
> artifact `11caf45003b2d3f7fb5d3624f75e8b3ca964a5757a72728235e0f19d3bd58370`,
> demo signal `5730b8a877cbff8ff14d3a59c0257b620b9414be8d60d53955800d03f848a441`,
> opaque episode `runtime-episode-3e91a522140d42cf2330e1be2e530f5d`.
> A forged-prefix regression now returns `M3_OBSERVATION_NOT_REGISTERED` online and
> `OFFLINE_M3_OBSERVATION_NOT_REGISTERED` independently. Counts and scientific verdict
> remain 193 active signals, 6/54/2 calibration, descriptive `1/3`, strict `.05 UNRESOLVED`.

> 冻结时间：2026-08-13（UTC）  
> 范围：M3-A contracts、default-off DUET signal seam、aggregate calibration、entity SUPPORT/ABSTAIN、
> derived certificate risk、显式 runtime successor、独立 offline audit 与真实 micro diagnostic  
> 非目标：没有实现 M3-B 新模型、没有开放 NOT_FOUND/REFUTE/residual/identity、没有正式 benchmark

本文只记录已经落到源码或真实输出中的事实。工程测试通过不作为 novelty 或统计 validity 证据；科学 gate
见 `docs/M3_FALSIFICATION_REPORT.md`。

## 1. Frozen outcome

- M3-A 使用独立 schema/profile，不修改冻结的 M1 wire fields，也不改变 M2 production-zero 默认行为。
- DUET signal 功能开关默认关闭，M0 trace、offline metrics 与 M3 signal 文件必须分离。
- 终审发现第一版 hook 会把同一 batch 中较早已经结束的 episode 在后续 model calls 里再次写成 signal。
  这些不是新的 policy-visible events，因而违反 event-sourced causal admission。旧 signal JSONL、由它派生的
  counts、artifact、allowlist、bound、demo 和 budget outcomes 全部撤销，不能作为 frozen authority 或科学结果。
- hook 已改为显式接收 model call 前的 `active_mask`：当前 stop step 仍是合法 observation，先前 step 已结束的
  rows 不再发射。active-only 重跑得到 193 signals / 32 episodes，并与 prediction trajectory 精确对应、没有
  repeated suffix；新的 aggregate artifact、72-signal replay manifest 与 registry seal 已机械重建。
- entity adapter 只有 `SUPPORTS/ABSTAIN`；caller 不能注入 risk、artifact authority、dependency dedup 或
  REFUTE。
- corrected P1 descriptive aggregate 是 6 scans / 54 examples（含 10 null）/ 2 error scans，bound `1/3`；
  它没有 confidence guarantee，不能宣称 usable risk。
- independent red-team 随后发现 `episode_id=pathId_objId_instrIdx`，所以 32/32 records 都在复合 ID 中暴露
  target object ID，canonical demo ordering 也读取该字段。registry/hash 只封存了这项 semantic leak，不能把
  d254 artifact 或其 runtime outcome 称作 no-GT authority。必须 pseudonymize/reseal 后再冻结 production。
- 同一 audit 证明 manifest 只认证 wrapper 内的 selected evidence signal，不认证此前写入 state 的
  `OBSERVATION` transitions。caller 可伪造 prefix pose/event ID，再复用 allowlisted final signal，仍机械
  CERTIFICATE/ACCEPT。当前只能称为 exact selected-signal membership with caller-supplied prefix，不能称为
  exact fixed replay。
- `model/interface/config` 等 identity digests 仍是 CLI 提供的字符串，没有 code-checked derivation；tensor hashes
  也不足以从 checkpoint 重算 logits。registry 防止 freeze 后替换 signal，不等于生成过程 attestation。
- contract/adversarial 60/60 只证明 exact contracts；它们没有发现上述 semantic alias，不能替代 data-semantic
  audit。

## 2. Code and artifact inventory

### 2.1 Contracts and schemas

| File | Actual change |
|---|---|
| `proofnav/contracts.py` | 新增 `duet_model_signal`、`calibration_artifact`、`adapter_decision`、`risk_atom`、`m3_bound_evidence` 五个显式 schema versions；M1/M2 versions 未改 |

M3 versions：

```text
proofnav.duet-model-signal.v1
proofnav.calibration-artifact.v1
proofnav.adapter-decision.v1
proofnav.risk-atom.v1
proofnav.bound-evidence.v3
```

### 2.2 Perception boundary

| File | Actual change |
|---|---|
| `proofnav/perception/duet_signal.py` | 构造 deterministic nested signal；finite/type/shape/mask 检查；post-cast content digests；JSONL sink |
| `proofnav/perception/entity_template.py` | instruction-specific、code-owned entity proof template；template digest 不再由 CLI 调用方声明 |
| `proofnav/perception/evidence_adapter.py` | exact signal/decision validators；registered artifact + selected-signal membership gate；entity-only SUPPORT/ABSTAIN；v3 wrapper + risk atom builder |
| `proofnav/perception/__init__.py` | 只导出冻结 public perception APIs |

Signal top-level exact fields：

```text
schema_version, producer, source_schema, signal_semantics, evidence_authority,
observation, observation_digest, object_scores, content_digests,
instruction_digest, template_digest, model_identity, signal_digest
```

`object_scores` 保存 ordered proposal IDs、boolean valid mask、完整 finite logits，以及 deterministic
selected index/proposal/statistic；没有 valid proposal 时三个 selection fields 必须全为 null。`content_digests`
精确绑定 panorama/object/angle/box `float32` 和 instruction encoding `int64` 的 dtype、shape、C-order bytes。
`model_identity` 精确绑定 model/checkpoint/feature/interface/config/tokenizer 六个 SHA-256。

### 2.3 Calibration and authority

| File | Actual change |
|---|---|
| `proofnav/calibration/artifact.py` | exact aggregate artifact schema、canonical seal、model/domain/split/count/bound validation；structural validation 与 production registration 分离 |
| `proofnav/calibration/registry.py` | code-owned manifest seal；tracked artifact/resource validation；artifact-bound exact signal manifest；生产 authority 查询/拒绝 APIs |
| `proofnav/calibration/risk.py` | self-sealed false-support atom；selected wrapper full recomputation；canonical familywise dedup；strict union；caller bound ignored |
| `proofnav/calibration/registered_artifacts.json` | code-owned artifact/resource registry 与 signal-manifest binding；active-only resources 已原子替换，但 semantic no-GT authority 因 composite-ID leak 被阻断 |
| `proofnav/calibration/artifacts/m3a_seen_micro.json` | tracked active-only aggregate artifact；机械内容与 generated artifact exact match；仅作 revoked diagnostic，待 pseudonymized replacement |
| `proofnav/calibration/artifacts/m3a_seen_micro_signals.json` | 8 applicability scans / 72 sorted unique selected-signal digests；不覆盖 prior observation prefix，且 signal 含 target-ID alias，不能授予 no-GT/full-replay authority |
| `proofnav/calibration/__init__.py` | 导出 artifact、registry、signal-authority 与 risk APIs |

Artifact validity domain 从单一 scan list 修正为：

```text
domain_id
calibration_scan_ids
applicability_scan_ids
shift_policy = exact_match_or_abstain
```

两组 scan 必须非空、排序、唯一且不相交。Runtime signal 只允许命中 `applicability_scan_ids`；offline labels
只定义 `calibration_scan_ids`。selected evidence 又增加 exact signal-digest allowlist，阻止调用方用 public builder
构造一个同 domain、自洽重签但从未记录的 signal；但 membership 不是 semantic sanitation，当前 allowlist
仍含可解码 target object ID 的 `episode_id`，也不认证 signal 之前的 observation transition prefix。

这不是通用 live-inference attestation。即使 selected signal 由 source-controlled artifact + manifest 收紧，
也必须先完成 composite-ID pseudonymization 与 prefix binding；未来 live inference 还需要可信 producer
boundary、签名/attestation 或等价机制。

### 2.4 Offline builder and real micro runner

| File | Actual change |
|---|---|
| `proofnav/offline/calibration_builder.py` | 按 scan 聚合“至少一个 selected false support”的 familywise label；保留 null selections；输出只含 aggregates |
| `proofnav/offline/m3_micro_slice.py` | deterministic scan partition、signal-only demo selection、runtime chain、terminal 后 hidden truth/oracle audit、结果落盘 |
| `proofnav/offline/structural_audit.py` | 不调用 online validator 的独立 M3 signal/artifact/decision/atom/wrapper 重算；certificate/terminal audit |
| `proofnav/offline/__init__.py` | 导出 builder；lazy `run_m3_micro_slice` 避免 import-time runner side effects |

Offline-only label schema 精确为：

```text
sample_id, scan_id, split_name, score, target_matches_slot
```

`score=null` 是 empty/all-masked 的真实 no-SUPPORT opportunity，保留在 examples/scans denominator 中，
不能删除。`val_unseen`/test labels、scan split overlap、calibration/application overlap、非 finite score、未知字段
全部 fail closed。Runtime artifact 不含 sample ID、GT slot truth、path、BBoxes、object inventory 或 lookup table；
然而 signal 的复合 `episode_id` 语义等价地暴露了 target object ID，所以“artifact aggregate-only”不能推出整条
runtime chain 无 GT。

### 2.5 Explicit M3 runtime successor

| File | Actual change |
|---|---|
| `proofnav/runtime/semantics.py` | 注册 `proofnav.admission.m3-entity-support.v1`；M3 wrapper exact validation；默认 `allow_m3=False` |
| `proofnav/runtime/state.py` | 新增 `M3ProofState(scope, template)`；没有 caller `risk_claims` 参数 |
| `proofnav/runtime/certificate.py` | M3 FOUND 从证书实际选择的 wrappers 调 composer 重算 risk；NOT_FOUND sealed |
| `proofnav/runtime/verifier.py` | 新增 `M3OnlineVerifier()`；普通 `OnlineVerifier()` 不接受 M3 profile |
| `proofnav/runtime/terminal.py` | 新增 `M3TerminalController()`；terminal acceptance 仍经显式 M3 verifier |
| `proofnav/runtime/__init__.py` | 导出三个 M3 successor classes；不导入 offline oracle provider |

M3 wrapper 保持 M2 query/binding 核心，并新增 exact nested authority：

```text
schema_version,
query_id, hypothesis_id, obligation_id, predicate_id, predicate_kind, binding,
source_observation_digest, evidence,
signal, calibration_artifact, adapter_decision, risk_atom
```

M3 profile 下 topology closure 仍不等于 semantic residual closure。没有 REFUTE/residual/identity atoms 时，
certificate builder、online verifier、terminal controller 与 independent offline auditor 都拒绝 NOT_FOUND。

### 2.6 Default-off DUET hook

| File | Actual change |
|---|---|
| `map_nav_src/reverie/parser.py` | 新增 default-null signal path 与六个 identity digest flags；没有 template-digest flag |
| `map_nav_src/reverie/agent_obj.py` | 在真实 `nav_outs['obj_logits']` 形成后、action 前发 signal；先 sanitize observation；开关关闭时不 import ProofNav seam |
| `map_nav_src/reverie/main_nav_obj.py` | split-aware signal path；与 M0 trace/offline metrics 路径冲突时拒绝；validation 后关闭 sink |

Signal hook 绑定实际 candidate-first、padding/truncation 后的 model inputs。原 observation 中的
`gt_path/gt_end_vps/gt_obj_id` 等 evaluator truth 在 seam 前由 allowlist sanitizer 去掉，递归 forbidden-key
检查作为第二层防线。这只是 syntactic filter：REVERIE `episode_id=pathId_objId_instrIdx` 绕过字段名检查。
因此本文明确撤回“sanitized observation 在语义上 GT-free”，并要求在 seam 前使用 code-owned opaque episode
pseudonym，同时把 evaluator mapping 隔离到 offline-only join。

### 2.7 Tests and documents

Focused tests 位于：

```text
tests/m3/test_duet_signal_hook.py
tests/m3/test_artifact_api.py
tests/m3/test_artifact_attacks.py
tests/m3/test_adapter_attacks.py
tests/m3/test_risk_metamorphic.py
tests/m3/test_runtime_boundaries.py
tests/m3/test_m3_integration.py
```

Frozen design/evidence documents：

```text
docs/M3_SCIENTIFIC_PRECOMMIT.md
docs/M3_DATA_LABEL_BOUNDARY.md
docs/M3_EVIDENCE_CAPABILITY_AUDIT.md
docs/M3_CALIBRATION_AND_RISK_SEMANTICS.md
docs/M3_FAILURE_TO_DESIGN.md
docs/M3_FALSIFICATION_REPORT.md
docs/M3_CODE_DRIVEN_CHANGELOG.md
```

## 3. Public API freeze

| Import | Signature / construction | Semantics |
|---|---|---|
| `proofnav.perception.build_duet_signal` | keyword-only `observation, template_digest, object_logits, object_valid_mask, panorama_features, object_features, object_angle_features, object_box_features, instruction_encoding, model_identity` | uncalibrated signal；`evidence_authority=False` |
| `proofnav.perception.DuetSignalSink` | `DuetSignalSink(path, model_identity)`；`emit(**signal_inputs)`；`close()` | separate flushed JSONL sink |
| `proofnav.perception.build_entity_proof_template` | `(instruction)` | deterministic code-owned M3 entity template |
| `proofnav.perception.validate_duet_signal` | `(signal, observation=None, template=None, expected_model_identity=None)` | exact nested finite signal validation；不授予 evidence authority |
| `proofnav.perception.validate_adapter_decision` | `(value)` | canonical decision ID + self-seal validation |
| `proofnav.perception.adapt_entity_signal` | `(query, signal, artifact=None)` | exact registered slice 内 SUPPORTS，否则 ABSTAIN/reject |
| `proofnav.perception.build_calibrated_bound_evidence` | `(query, signal, artifact, scope_contract_id)` | 返回 v3 wrapper，或返回 ABSTAIN decision |
| `proofnav.calibration.build_calibration_artifact` | `(spec)` | offline structural candidate builder；本身不授予 production authority |
| `proofnav.calibration.validate_calibration_artifact` | `(artifact, signal=None)` | structural/domain validation |
| `proofnav.calibration.validate_registered_calibration_artifact` | `(artifact, signal=None)` | structural validation + exact registry authority |
| `proofnav.calibration.registered_calibration_artifacts` | `()` | 返回 review metadata copy |
| `proofnav.calibration.load_registered_calibration_artifact` | `(digest)` | 返回 exact tracked artifact copy |
| `proofnav.calibration.require_registered_calibration_artifact_digest` | `(digest, location=...)` | 未注册 artifact fail closed |
| `proofnav.calibration.is_registered_signal_digest` | `(artifact_digest, signal_digest)` | 查询 selected-evidence signal membership；不认证 event prefix |
| `proofnav.calibration.require_registered_signal_digest` | `(artifact_digest, signal_digest, location=...)` | fabricated/live unregistered signal fail closed |
| `proofnav.calibration.validate_risk_atom` | `(atom, wrapper=None, location='$.risk_atom')` | exact self-sealed false-support atom |
| `proofnav.calibration.compose_certificate_risk` | `(wrappers, verdict, scope)` | full wrapper rebuild、family-key dedup、strict union、FOUND only |
| `proofnav.offline.build_scan_familywise_artifact` | `(labeled_samples, artifact_spec)` | offline aggregate-only reduction |
| `proofnav.offline.run_m3_micro_slice` | `(signal_file, annotation_file, output_dir)` | lazy offline diagnostic runner |
| `proofnav.runtime.M3ProofState` | `(scope, template)` | explicit entity-SUPPORT successor state |
| `proofnav.runtime.M3OnlineVerifier` | `()`；`verify(state_or_bundle, certificate)` | explicit M3 online verifier |
| `proofnav.runtime.M3TerminalController` | `()`；`decide(state_or_bundle, proposed_verdict, certificate, execution)` | verifier-gated M3 terminal controller |

## 4. Attack-driven fixes

| Discovered attack / bug | Fix now frozen | Regression coverage |
|---|---|---|
| nested signal 的 scan 曾从 top-level 读取 | artifact validation 改为 exact `signal['observation']['scan']` | applicability-vs-calibration domain tests |
| calibration scans 被误当 runtime domain | 分离且强制不相交的 calibration/applicability scan IDs | overlap、wrong-domain、offline-builder attacks |
| caller 可构造自洽 aggregate 并重签更小 bound | structural validator 与 production registry 分离；manifest 由 source constant seal | unregistered/resealed smaller artifact 在 adapter/state/online/offline 全链拒绝 |
| public signal builder 可在同 domain 构造自洽伪 signal | artifact-bound exact source-controlled signal manifest；adapter 与 offline auditor 检查 membership | fabricated/unregistered signal attack |
| risk atom 生成了 digest 但 validator field set 未包含 | `atom_digest` 纳入 exact schema并重算 | missing/tampered atom tests |
| caller 同时篡改 wrapper 内多层值使局部校验互相一致 | composer 从 query+signal+artifact+scope 完整重建 wrapper | caller risk、nested authority、state admission attacks |
| adapter decision ID/digest 可非 canonical | validator 重算 canonical decision ID 和 decision seal | decision/risk-atom resealing attacks |
| 调用方传 template digest | template 由 code-owned instruction parser构造；去掉 CLI template flag | instruction/template staleness tests |
| GT alias 或 NaN/Inf 进入 signal | allowlist sanitizer + recursive forbidden keys + post-cast finite checks | GT/nonfinite/bad-mask/length tests |
| empty/all-masked proposal 被误作 absence | signal 保留 null selection；adapter ABSTAIN；residual OPEN | empty signal、runtime residual tests |
| 任意相同 dependency string 获得 risk dedup | 只按 canonical `artifact + source_event` family key 去重；冲突 bound 拒绝 | permutation/revisit/arbitrary-group metamorphic tests |
| caller 提供较小 terminal risk | `M3ProofState` 无 risk 参数；builder/composer从selected atoms重算 | caller-bound certificate tamper tests |
| object ID equality 被误作跨视角 identity | M3 identity zero-admission；同 ID 跨 viewpoint 不链接 | runtime identity boundary test |
| REFUTE/NOT_FOUND 可能复用 SUPPORT atom | polarity exact；M3-A NOT_FOUND、residual、relation anchor 全部 sealed | polarity swap、NOT_FOUND/residual/integration tests |
| revocation/duplicate/stale certificate 绕过 history | active authority、cost/history、semantic dedup、transition tip 分离并重算 | revocation、duplicate、repeated build、staleness tests |
| M3 seam 影响 frozen DUET/M2 默认路径 | parser default null、optional import guarded、explicit M3 classes/profile | hook default-off 与 M3-off=M2 production-zero tests |
| ended batch row 在后续 model call 被重复写成新 signal | emitter 显式接收 call 前 `active_mask`，只遍历 active rows；当前 stop step 保留，先前已结束 rows 跳过 | active-mask AST/seam regression + real trajectory exact match / 0 repeated suffix |
| composite `episode_id` 编码 target object ID | **尚未修复**：必须生成 runtime 不可解析的 code-owned pseudonym，canonical ordering 不得读取 evaluator ID，并重建 interface/signal/artifact/manifest/registry | 32/32 active records semantic-ID audit 已命中；修复前 no-GT authority fail closed |
| manifest 只绑定 selected signal、不绑定 preceding observation prefix | **尚未修复**：认证完整 relevant event prefix，或证明 terminal semantics 与 prefix 独立，并由 online/offline verifier 重算 | forged pose/event-ID prefix + exact allowlisted final signal 仍 CERTIFICATE/ACCEPT |
| model/interface identities 由 CLI 声明，logit 不可从保存内容复算 | **尚未修复**：code-derived identities、可复算 checkpoint→tensor→logit 链或可信签名/attestation | registry 只证明 frozen membership，不证明 producer provenance |

## 5. Real execution record and P0 invalidation

### 5.1 Signal extraction

第一版真实 extraction 的输出因为 ended-row admission bug 失效。修复后以相同 bounded 配置写入独立的
`.m3-results/micro_real_signal_active/` 与 `.m3-results/signals/val_train_seen_active.jsonl`：

```text
split              val_train_seen
seed               0
batch_size         8
m0_eval_iters      4
proofnav signal    enabled to ../.m3-results/signals/val_train_seen_active.jsonl
runtime trace      disabled
offline metrics    disabled
```

旧输出中的重复 ended rows 污染了 sample opportunities 和 exact signal manifest。所有旧数量、文件哈希和
派生统计永久撤销。corrected active-only output 为：

```text
signals             193
episodes            32
signal file bytes   814618
signal SHA-256      61eec2760687ff0b6691e01ce4929fee9abdf265add4037b9c497ada145ef747
trajectory match    exact signal-to-pred per episode
repeated suffixes   0
episode lengths     {4: 2, 5: 10, 6: 8, 7: 9, 8: 3}
partition records   P0=67, P1=54, P2=72
```

长度 histogram 的计数和为 32、加权长度和为 193，和 JSONL/episode audit 一致。该修复不是 M0 baseline
复现，也没有训练新模型。

### 5.2 Offline micro command

active-only rerun 仍应使用同一个正式 runner 接口：

```bash
python -m proofnav.offline.m3_micro_slice \
  --signal-file .m3-results/signals/val_train_seen_active.jsonl \
  --annotation-file datasets/REVERIE/annotations/REVERIE_val_train_seen_enc.json \
  --output-dir .m3-results/m3a_micro_slice_active
```

active-only builder 已冻结以下 aggregate facts：

| Item | Corrected result |
|---|---|
| hash partition records | development P0=67 / calibration P1=54 / demonstration P2=72 |
| calibration | 6 scans / 54 examples / 10 null selections / 2 error scans |
| descriptive upper bound | `2/6 = 1/3`；`confidence=null` |
| artifact digest | `d2548e03e38c24423f846c372d66ed0abd1dc78b672bf9f6c965566d699f830f` |
| artifact file SHA-256 | `80f745393054e75a6850d49b8a2764b5b74cc52e48b2ec06cca2c0d7c15b38bb` |
| canonical demo | `1LXtFkjw3qL / 2401_51_0 / event_seq 4 / slot 51 / score 5.40303897857666` |
| demo signal digest | `4b41f5f79d866ec0b0367580484f2aa08ab9a9586dcc37d200caed20a1e1efe9` |
| mechanical budget 1 | builder CERTIFICATE；derived risk `1/3`；online ACCEPT；terminal ACCEPT_FOUND；formal offline `TRUE_ACCEPT` |
| mechanical budget `.05` | builder `UNRESOLVED/RISK_BUDGET_EXCEEDED`；terminal `FINALIZE_UNRESOLVED`；formal Oracle `UNRESOLVED` |

strict run 的 runner safety interpretation 是 `CORRECT_ABSTAIN`，但 formal `OracleOfflineVerifier` taxonomy
outcome 是 `UNRESOLVED`。更重要的是，两组结果都基于含 target-ID alias、caller-supplied prefix 的
selected-signal replay，只能记录 software chain mechanics，不能作为有效 no-GT outcome。canonical demo 的
`episode_id` 中间 token 和 selected slot
恰好同为 `51`，是本次 semantic leak 的直接可见证据。

### 5.3 Authority refreeze checklist

active-only run 完成后必须在同一审阅单元执行：

```bash
sha256sum \
  .m3-results/signals/val_train_seen_active.jsonl \
  .m3-results/m3a_micro_slice_active/m3a_calibration_artifact.json \
  proofnav/calibration/artifacts/m3a_seen_micro.json \
  proofnav/calibration/artifacts/m3a_seen_micro_signals.json \
  proofnav/calibration/registered_artifacts.json
```

当前 generated active-only inputs 的 frozen hashes 是：

```text
61eec2760687ff0b6691e01ce4929fee9abdf265add4037b9c497ada145ef747  active-only signal JSONL
80f745393054e75a6850d49b8a2764b5b74cc52e48b2ec06cca2c0d7c15b38bb  generated active-only artifact file
```

mechanical registry refreeze 的完整结果是：

```text
artifact digest      d2548e03e38c24423f846c372d66ed0abd1dc78b672bf9f6c965566d699f830f
artifact file SHA    80f745393054e75a6850d49b8a2764b5b74cc52e48b2ec06cca2c0d7c15b38bb
manifest count       72 signals / 8 applicability scans
manifest seal        f918091f8aec58bff8ba566bae0fe9d8b21f8333ff96f24bb65a957e6de81d2e
manifest file SHA    45a26a285d049f8de38e069f2caf942daf2d1292be70c4524e3e180a001b9134
registry seal        897058ac5cd0a4caa648d6ebef73d9d7e10397aa6dc8e6a6761a87f388120837
registry file SHA    991c43c319699984b04c5d47603fad7fcfc1dff5289d8b2cfb69f65c50c4fa8c
```

Generated 与 tracked artifact file hashes 精确相等，manifest 的 72 个 selected signals 都来自 active events，
registry seal 绑定 artifact 与 manifest，真实 wrapper→state→certificate→M3 verifier→terminal→offline audit
链机械可运行。manifest 并没有绑定同一 state 的完整 observation prefix，不能由此声称 exact full replay。
这些完整性事实不抵消 semantic-ID leak：pseudonymized rebuild 必须产生全新的 interface/signal/artifact/
manifest/registry identities。pre-fix hashes 不再记录在本文。

## 6. Verification record

active-only registry 更新后的 exact CPU command：

```bash
python -m unittest discover -s tests/m3 -p 'test_*.py' -v
```

实际结果：`Ran 60 tests in 3.120s`，`OK`。其中覆盖 forged/resealed signal、manifest membership、active-mask
emission、artifact tamper、adapter/risk/runtime/integration attacks。紧接着 independent data audit 仍发现
`episode_id` semantic leak；这正是“60/60 不等于 GT-free、统计 validity 或 novelty”的实证反例。

一次性 M1/M2/M2.1 回归已在 M3 integration 完成时记录为 27/27、52/52、4/4；本 changelog 阶段按要求
没有重复运行这些已通过 suites，也没有重跑 M0/GPU。

## 7. Known limitations and explicit non-claims

- 当前 artifact 是 `descriptive_seen_scan_micro`，不是 held-out、unseen、finite-confidence 或 conformal
  guarantee。
- checkpoint 已见过全部 train scans；现有非 test 资源没有 checkpoint-unseen calibration scans。
- active-only descriptive bound 是 `1/3` 且 `confidence=null`，高于 strict false-FOUND target `.05`；当前没有
  usable-risk 结果。
- 当前 selected-signal replay 因 composite `episode_id` target-ID leak、preceding observation prefix 未认证，
  不能作为 no-GT/full-replay production authority；pseudonymization、prefix binding 与 reseal 是前置 blockers。
  public live signal inference 另尚无外部 attestation。
- Annotated slots 来自 benchmark object inventory；它们不是独立 detector proposals，也不证明开放世界
  discovery 或 proposal completeness。
- entity low score、empty proposals、STOP、frontier exhaustion 或 topology closure 都不是 entity absence。
- entity REFUTE、residual coverage、SAME_ENTITY、attribute、relation 与 room-anchor 仍无合法 adapter/artifact。
- identity 没有 RGB-D/mask/3D 或 calibrated false-link head；保持 zero-admission。
- strict union 是保守 baseline；没有 independence/product/Sidák、重复观察折扣或 anytime-valid claim。
- source-controlled hashes/registry 是软件 trust anchor，不是硬件/remote attestation。
- 当前 identity CLI digests 未由代码从实际 checkpoint/interface 派生，signal tensors/hashes 也不足以离线复算
  logits；因此 software registry 不能升级成生成过程证明。
- tests 证明 exact contracts 与 fail-closed behavior，不证明论文 novelty、统计正确性或正式 benchmark 性能。

## 8. Handoff boundary

M3-A mechanical surface 可作为回归基础，但 no-GT authority 未冻结。下一步只能先完成 code-owned episode
pseudonym、offline join isolation、canonical-order audit、event-prefix authority、code-derived/attested producer
identity 与全量 authority rebuild；然后才按
`docs/M3_FALSIFICATION_REPORT.md` 的 cheapest-killer 顺序 audit 合法 scan split/labels、scan-familywise
risk--coverage 与 adaptive/repeat counterexample。在这些 gate 通过前，不训练新模型、不运行正式 benchmark、
不开放 NOT_FOUND/residual/identity，也不进入 M4 planner。
