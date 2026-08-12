# ProofNav M1 接口、paired 数据与离线评测合同

> 冻结日期：2026-08-12（UTC）
>
> 状态：**M1-A / M1-B 最小 vertical slice 已实现并由 CPU 单元测试验证**
>
> 适用范围：接口与数据合同；不是 ProofNav 方法实现或 benchmark 结果

## 1. 边界与状态标记

本文使用以下标记：

- `[实测]`：当前代码及测试实际通过；
- `[合同冻结]`：字段和语义已固定，但真实 M2+ producer 尚未实现；
- `[M2+]`：本轮明确未实现。

M1 只提供纯 JSON 数据合同、严格 validator、微型 reference checker、paired
validator 和独立离线 evaluator。代码位于 `proofnav/`，只依赖 Python 标准库，
没有接入 DUET rollout、修改模型、创建 runtime certificate、读取 checkpoint、下载数据、
使用 GPU、训练或生成正式 paired REVERIE 数据。

微型 fixtures 只是合同测试输入，不是实验样本，不得汇报为方法效果、benchmark 结果或
校准有效性证据。

## 2. 版本目录与兼容策略

`proofnav/contracts.py::SCHEMA_VERSIONS` 是本轮版本的单一代码目录：

| 合同 | 版本 |
|---|---|
| observation | `proofnav.observation.v1` |
| action | `proofnav.action.v1` |
| evidence | `proofnav.evidence.v1` |
| scope | `proofnav.scope.v1` |
| obligation | `proofnav.obligation.v1` |
| certificate | `proofnav.certificate.v1` |
| result | `proofnav.result.v1` |
| paired data | `proofnav.paired.v1` |
| M1 reference check | `proofnav.reference-check.v1` |
| offline evaluation | `proofnav.evaluation.v1` |

`[实测]` v1 agent-visible 合同按严格 allowlist 校验，未知字段和错误版本均失败。
版本升级必须更换版本字符串并提供显式 adapter，不能静默放宽 v1。

原 DUET prediction `instr_id/trajectory/pred_objid` 保持原样可读。离线 evaluator 将其
识别为 `duet_legacy`，只验证结构并明确要求继续使用冻结的 REVERIE evaluator 计算
SR/SPL/RGS/RGSPL；不会凭空补造 ProofNav verdict 或 certificate。

## 3. Online / offline 单向边界

```text
DUET raw observation
  -> strict copying adapter
  -> AgentObservation / Action / Scope / Evidence / Obligation
  -> M1 reference checker (online-only serialized context)

paired evaluator_only truth
  -------------------------------------> offline evaluator comparison
                                             ^
versioned result + checker report -----------+
```

`[实测]` `proofnav.validation.assert_agent_visible` 递归拒绝 `gt_*`、`obj2vps`、完整图/
shortest path、paired truth 和 evaluator truth 字段。每个 agent-visible v1 validator 还
拒绝 allowlist 外字段，防止将同一真值改名后作为任意扩展字段写入。

`[实测]` offline evaluator 在调用 M1 reference checker 时只传入 scope、obligations、
evidence 和 observations；truth 在 checker 返回后才用于离线比较。在线 context 只允许
这四个顶层键。输出中明确记录此边界。

`[实测]` runtime trace 只接受 M0 的六类事件：`observation/model_scores/action/
termination/execution/prediction`，拒绝 evaluator/metrics/GT 字段与未知顶层 payload。
mandatory regression 使用从真实 M0 trace 投影并脱敏的固定 6-event slice；完整 66-event 本机
artifact 只在显式 opt-in integration test 中检查，不再影响 clean checkout。

## 4. Agent observation 与动作合同

### 4.1 Observation allowlist

`AgentObservation` 只复制：

- episode/event ID、event sequence、step；
- scan、当前 viewpoint、view index、heading/elevation/position；
- panorama/object tensor 的 shape 与 dtype；
- instruction 与 token 长度；
- 当前 candidate 的 ID、point ID、方向、位置、simulator index 和 feature schema；
- 当前 object proposal IDs；
- producer/source schema audit trail。

不会复制 tensor 值、原 dict 引用、simulator/environment/evaluator 引用、GT path/object、
GT-derived distance 或完整 connectivity。candidate 固定标为
`unobserved_navigation_proposal`。

`[源码事实，M0 实测]` 首次 candidate 的 `distance` 是代表视角的角距离且 cache 后不存在。
因此 v1 observation 没有 candidate distance 字段；正式路线成本只能进入 cost ledger，
以后来自已发现 GraphMap path/distance，而不是 candidate cache。

### 4.2 Branch-aware action

Action 同时保存 `local/global/fused` 三个分支的 `action_ids` 与 `valid_mask`，再保存：

- `selected_branch`；
- 该分支内部的 `selected_index`；
- 映射后的 `selected_action_id`；
- `STOP` 或 `VIEWPOINT` action kind；
- `uncalibrated_duet_task_score` score semantics；
- 来源 trace event audit。

`[实测]` validator 检查三分支都存在、index 0 映射到 `null/STOP`、ID/mask 等长、
selected index 未被 mask、selected ID 与选中分支对应。raw logit index 不是跨分支的
统一动作 ID。

## 5. Evidence、scope 与 obligation

### 5.1 Evidence provenance

每条 evidence 必须包含：

- `evidence_id/episode_id`；
- `source=observation` 与 `source_event_id`；
- event sequence、step、scan、viewpoint、view index；
- `viewpoint_view` 或 `object_slot` 离散证据单元；
- scope/obligation/predicate ID；
- `SUPPORTS` 或 `REFUTES` claim；
- adapter version、dependency group、audit trail。

`[实测]` evidence 引用存在的 observation 后，episode、event sequence、step、scan、
viewpoint 和 view index 必须逐项一致。`proposal` 和 `travel_only` source 都被拒绝。

`[源码事实，M0 实测]` global 多跳路径的 `expanded_path[:-1]` 只计 travel；只有
`observation_endpoint` 随后的 `_get_obs` event 能成为 evidence provenance。

### 5.2 Scope

v1 scope 使用：

- scan/start；
- `candidate_reachable_component` 内涵式域规则；
- M0 adjacency interface audit 引用；
- `intensional_rule_only` disclosure；
- 明确的 in-scope hypothesis IDs；
- observation/predicate/calibration 版本；
- false-FOUND / false-NOT-FOUND 风险预算；
- step/observation/query 资源上限；
- provenance 与 change log。

scope 不把完整 connectivity 表交给 online contract。M1 只校验合同结构；如何在 runtime
安全构造 hypothesis index 和如何结算闭包属于 M2。

### 5.3 Proof obligation

每条 obligation 绑定 episode、scope、hypothesis、predicate，声明是否 necessary，并使用
`OPEN/SUPPORTED/REFUTED` 状态。closed obligation 必须引用 evidence；OPEN 不得伪造关闭
evidence。

## 6. 三状态结果与终止语义

内部总状态由两个兼容字段表达：

| 总状态 | `semantic_decision` | `decision_status` |
|---|---|---|
| FOUND | `FOUND` | `VERIFIED` |
| NOT_FOUND | `NOT_FOUND` | `VERIFIED` |
| UNRESOLVED | `null` | `UNRESOLVED` |

`termination.cause` 独立记录 `verifier_accept/duet_stop/no_frontier/max_step/budget/
verifier_reject/error`。只有 `verifier_accept` 可以伴随 VERIFIED 决策；其余原因可结束执行，
但不能单独产生 NOT_FOUND。

结果还必须带：原 DUET trajectory/pred_objid、scope ID、certificate、online verifier
状态、risk claim、budget status、完整 cost ledger 和 source/event audit trail。

### 6.1 FOUND reference rule

`[合同冻结，微型 checker 实测]` FOUND 需要：

1. positive certificate；
2. entity binding 引用真实 observation，且与 `pred_objid` 一致；
3. true path 覆盖全部 necessary obligation；
4. 每项 obligation 为 SUPPORTED，证据 polarity 为 SUPPORTS；
5. unresolved obligation 为空；
6. risk upper bound 不超过 result 与 scope budget，calibration version 一致；
7. verifier accepted、termination 为 verifier_accept、资源仍在预算内。

### 6.2 NOT_FOUND reference rule

`[合同冻结，微型 checker 实测]` NOT_FOUND 需要：

1. refutation-cover certificate；
2. certificate hypothesis index 与 scope index 一致；
3. cover 完整覆盖每个 in-scope hypothesis；
4. 每项对应 REFUTED obligation 和 REFUTES observation evidence；
5. uncovered hypotheses 与 frontier/unresolved 均为空；
6. risk、verifier、termination 和 budget 条件同样成立。

### 6.3 UNRESOLVED

`[实测]` UNRESOLVED 的 decision、certificate 和 risk claim 必须为 null，verifier 不得
accepted，且 termination 不得是 verifier_accept。证据不足、开放义务、DUET STOP、
no frontier、max step、budget 或 error 都可以结束为 UNRESOLVED。

M1 checker 只验证 fixture/serialized contract，不是 M2 independent verifier。尤其没有
runtime rejection→remaining obligations→continue navigation 闭环。

## 7. Strict paired false-premise 合同

四类固定为：

- `entity_absent`；
- `attribute_mismatch`；
- `relation_mismatch`；
- `room_anchor_mismatch`。

每个 pair 含 pair ID、split、premise class、instruction template、clean/false 两个成员、
changed-premise audit、dedup fingerprint 和 audit trail。每个成员分为：

- `agent_visible`：episode、scene/start、渲染后的 instruction、template/slots、结构化
  predicates、scope ID；
- `evaluator_only`：semantic truth、split、GT provenance、reachability audit 和 matched
  non-target conditions。

`[实测]` validator 强制：

- clean=FOUND、false=NOT_FOUND；
- scene/start/template/scope 一致；
- template 只能改变一个 slot，predicate 集只能改变一个 predicate；
- change audit 的 class/predicate/slot/before/after 与实际差异一致；
- premise class 与 predicate kind 一致；
- navigation opportunity 与 non-target context hash 一致；
- truth source 含 artifact/record/field paths/content SHA-256；
- audit 已 reviewed；
- canonical fingerprint 正确；
- pair/member ID 与内容不重复；
- 同一 scene 不跨 split。

M1 fixtures 每类只有一个合成样例，只用于验证上述检查；没有生成正式 REVERIE 数据。

## 8. 独立离线 evaluator

`proofnav.evaluator.evaluate_predictions` 输出 versioned summary，包括：

- 三类 verdict count 与 unresolved rate；
- termination cause count；
- FOUND/NOT_FOUND per-class、balanced、overall 与 resolved accuracy；
- false-FOUND / false-NOT-FOUND count；
- certificate check/acceptance；
- risk/budget/cost per-record 信息与完整 cost totals；
- offline truth 和 checker 的单向边界说明。

evaluator 可用 `python -m proofnav.evaluator --predictions ... --truth ... --contexts ...
--output ...`。paired 集合可用 `python -m proofnav.paired --input ... [--output ...]`。
正式 REVERIE 原指标仍由原 evaluator 负责，M1 没有改写其语义。

## 9. 测试覆盖与实际结果

从仓库根目录运行：

```bash
python -m unittest discover -s tests/m1 -v
```

覆盖：版本/allowlist、三状态、FOUND/NOT_FOUND reference rule、termination/verdict 分离、
GT 注入、proposal/travel-only、provenance、branch mapping、四类 pair、multi-change、scope、
missing provenance、dedup、split leakage、legacy DUET output、offline truth boundary、微型 M0
trace，以及固定、脱敏、可追踪的真实 M0 trace slice。未跟踪的完整本机 trace 已移到
`tests/integration/`，需显式环境变量和路径启用，不属于 mandatory suite。

测试是 CPU 合同验证，不加载模型或 HDF5，不构成正式实验。

## 10. 明确留到 M2+

- `[M2，后续已完成]` runtime certificate constructor、完整 online verifier、offline certificate
  truth auditor、拒绝反馈和 standalone terminal controller；详见 `M2_ARCHITECTURE.md`。M1
  reference checker 本身仍保持不变，不冒充 M2 verifier；
- `[M3]` 自动 predicate evidence、真实 attribute/relation/room adapter、校准 artifact、
  dependency-aware risk composition；
- `[M4]` proof-obligation re-ranking、GraphMap route-cost 接线和 verifier-gated rollout；
- `[M5]` 正式 paired generation、benchmark、消融、matched-risk 与完整成本实验。

M1 没有证明方法有效、风险真实校准或 NOT_FOUND 可在真实数据上可靠成立。

## 11. 不超过两个的 future refinement

1. `[M2，依附 scope + dual verifier]` 把 observation/evidence/certificate event IDs 升级为
   append-only canonical hash chain，使离线 auditor 可检测删改或时序重排；先用小型 tamper
   test 决定是否值得保留。
2. `[M4，依附 proof-obligation re-ranking]` action audit 同时保存 frozen DUET proposal
   branch/rank 与 reranker 后的 branch/rank/utility decomposition；先以 action legality 和
   default-off 等价测试作为 cheapest killer。

二者都不是新的第四项贡献，本轮没有实现。
