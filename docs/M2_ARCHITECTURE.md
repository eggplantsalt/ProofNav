# ProofNav M2 可执行证明架构与语义

> 冻结日期：2026-08-12（UTC）  
> 状态：**M2-A / M2-B 在 controlled/oracle evidence 假设下完成**  
> 边界：CPU micro logic；不是实际感知、训练、DUET 正式闭环或 benchmark 结果

## 1. 实际闭环

```text
offline ControlledTruth
  -> OracleEvidenceProvider（M1 evidence.v1）
  -> ControlledProofState + append/revoke ledger
  -> CertificateBuilder
  -> ReplayOnlineVerifier
  -> ReplayTerminalController
  -> FOUND / NOT_FOUND / CONTINUE_SEARCH / final UNRESOLVED
  -> OracleOfflineVerifier（只读隐藏 truth）
```

生产入口是另一条封闭路径：

```text
agent-visible observation
  -> ProofState / EvidenceLedger（M2 为 zero-admission）
  -> CertificateBuilder -> OnlineVerifier -> TerminalController
```

M2 没有真实 perception adapter。为避免 oracle fixture 仅改名为
`proofnav.perception.*` 后进入生产，生产 ledger 在 M2 拒绝所有 adapter；M3 必须以代码拥有、
版本升级的 adapter 边界显式开放。这个限制不会影响 offline replay 对证明逻辑的验证，也不能被
配置开关解除。

## 2. M2-A：proof state 与证书构造

`proofnav/runtime/state.py` 复用并严格调用 M1 `scope/observation/obligation/evidence.v1`
validator。M2 没有复制一套宽松 evidence schema；新增的是运行时派生状态：

- scope 中的显式 hypothesis universe；
- 每个 hypothesis 至少一个 necessary obligation；
- ledger 中只接受能逐字段追溯到已验证 observation event 的 evidence；
- obligation 由 active evidence 派生为 `OPEN/SATISFIED/REFUTED/CONFLICTED`；
- evidence append 与 revoke 都进入 SHA-256 链式 audit log；
- 每次 admission 同时绑定当时的 scope ID/version/digest，M1 evidence v1 本身无需被静默扩展；
- active evidence 的 canonical semantic digest 与追加顺序无关；
- scope ID/version/digest、frontier、closure、risk、cost、resource budget 同时进入 snapshot；
- proof-state digest 不依赖 ledger 的到达顺序，ordered audit-chain tip 单独保留。

证书构造器只有两种成功输出：

- `positive`：稳定选择一个 hypothesis，其所有 necessary obligations 都为 `SATISFIED`，保存
  entity/unit binding 和逐 predicate true path；
- `refutation_cover`：scope 已闭合、frontier 为空，且每个 in-scope hypothesis 至少有一个
  necessary obligation 为 `REFUTED`。

冲突、风险超限、预算耗尽、缺失正向义务、未覆盖 hypothesis 或 open frontier 都返回
`UNRESOLVED` construction outcome 和结构化 missing/frontier feedback，不生成半成品证书。

## 3. M2-B：语义 verifier 与 terminal gate

`proofnav/runtime/verifier.py` 不只检查字段。它从当前 proof snapshot 重新计算并核对：

- certificate type/verdict、canonical digest 和 ID；
- episode/scope ID、scope version/digest、proof-state/ledger freshness；
- evidence existence、polarity、observation provenance、重复覆盖和 adapter admission；
- positive 的必要义务与 true-path exact cover；
- negative 的 hypothesis index 与 refutation exact cover；
- frontier/closure、risk claim、budget snapshot 和完整 cost snapshot；
- conflicted evidence、revocation 和 malformed payload。

返回 `ACCEPT/REJECT/DEFER`、reason codes、certificate digest、missing obligations、uncovered
hypotheses、frontier witnesses 和供 M4 使用的 rejection feedback。任何 malformed certificate
都稳定变为 `REJECT`，不会因异常跳过 gate。

`TerminalController` 将 proof verdict 与控制动作分开：

| online 状态 / 执行状态 | directive | 公开语义 |
|---|---|---|
| certificate accepted | `ACCEPT_FOUND` / `ACCEPT_NOT_FOUND` | FOUND / NOT_FOUND |
| rejected/deferred 且仍可行动 | `CONTINUE_SEARCH` | 尚未终止 |
| max-step/budget/error/no executable action | `FINALIZE_UNRESOLVED` | UNRESOLVED |

原始 DUET STOP 只是 execution signal；在仍有预算和可执行 frontier 时不能绕过 verifier。
standalone gate 没有修改 `map_nav_src/`，所以 legacy DUET rollout/prediction 默认行为不变。

## 4. 成立范围与未完成能力

M2 实测的是：**给定满足 M1 provenance contract 且在 controlled harness 中假定正确的 evidence，
证明构造、形式/语义覆盖检查和终止 gate 是否闭环且 fail closed。**

M2 不证明 predicate 的事实正确性。最小反例确认：错误 predicate output 可以形成结构完整、
被 replay online verifier 接受的证书；独立 offline verifier 会将其标为 `FALSE_ACCEPT`，审计
处置降为 `UNRESOLVED`，且不把 truth 回传 controller。真实 predicate validity、calibration 与
风险保证仍是 M3 的硬门槛；M4 re-ranking、DUET 正式接线和 M5 benchmark 均未开始。
