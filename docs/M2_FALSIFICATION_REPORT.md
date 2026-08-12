# ProofNav M2.1 Semantic Repair and Adversarial Falsification Report

> 日期：2026-08-12（UTC）  
> 性质：CPU-only contract/logic falsification；不是形式化证明、模型实验或 benchmark
> 边界：本轮没有显式运行 M0 integration，没有下载、GPU、训练、正式 paired 数据或 M3/M4 接线

## 1. 旧实现的四个反例

本轮先把用户指定反例写入 `tests/m21/test_old_counterexamples.py`，在旧 bulk-snapshot M2 上实际运行。
结果是 4 tests / 4 failures，证明旧 `M2-A complete / M2-B complete` 不能成立：

| 旧反例 | 修复前实际结果 | 共同根因 |
|---|---|---|
| `vp0` candidates 含未访问 `vp1`，caller 传 `frontier=[]/scope_closed=True` | NOT_FOUND certificate 被 online ACCEPT | caller-owned topology/closure |
| 同一 hypothesis 两个 necessary SUPPORTS 分属 object A/B | FOUND certificate 被 online ACCEPT | opaque hypothesis ID 与 untyped binding |
| 唯一 observation/evidence 为 step/event 99，budget/cost 只报 step 1 | FOUND certificate 被 online ACCEPT | bulk preload 与 caller-owned counters 无共同 cut |
| 事实方向正确但 digest 损坏的 certificate 被 online REJECT | offline 错报 `FALSE_REJECT` | offline 只比 verdict 方向，不独立审结构 |

修复后同一文件为 4/4 OK。反例没有通过删除 candidate、删除断言或改成无矛盾 fixture 消失：旧 bulk
constructor authority 被删除，mixed certificate 在重新计算合法 digest 后仍因 typed path 不一致被拒绝，
future event 在事务提交前失败，digest damage 分类为 `CORRECT_REJECT`。

## 2. Failure-to-design loop

| 候选 | 优点 | Cheapest killer / 淘汰原因 |
|---|---|---|
| A. 保留静态 hypothesis IDs，只从 candidates 派生 frontier，并强制 evidence 同 unit | 改动小 | caller 仍可漏 hypothesis；跨 viewpoint 同实体和 relation anchor 无法表达 |
| B. 每个 visible object proposal 一个 flat hypothesis | GT-free、贴近 DUET slots | 零 proposal/proposal miss 令 NOT vacuous；无法结算未枚举 target/anchor |
| C. 直接用 DUET GraphMap visited/unvisited 作 closure authority | 复用已有图 | certificate/offline 无 raw 输入可独立重算；travel-only 节点与 observation 语义混淆 |
| D. causal event log + location/slot/residual universe + typed binding | closure、universe、binding、time/cost 可重算且不暴露完整图 | 采用；代价是 successor schema 与保守 coverage obligations |

更强的 lazy CSP/UNSAT proof 可表达通用 existential join，但需要 solver、proof format 与更大基础设施，
不是解决本轮四个反例的最小充分修改。最终选择 D，并在后续 red-team 中加入 relation
`anchor_residual` 与 typed identity witness；否则 B 的 proposal-miss 漏洞会在 relation 上重新出现。

## 3. 修复后的可机检定义

- **Closure：** 对 cut 前 admitted observations，`visited=observation endpoints`，
  `discovered={start}∪all candidate endpoints`，`frontier=discovered−visited`。只有 exact code-owned
  interface profile 且 frontier 为空时生成 witness；witness 绑定完整 observation content、scope、cut、
  visited/edge/frontier/universe/binding digests。GraphMap 与 `no_vp_left` 无证明 authority。
- **Universe：** visible slots 派生 subject alternatives；每个 visited location 强制有
  `location_residual`；relation 还为每个 visible subject×location 派生 `anchor_residual`。多 room、
  relation+room 或 optional anchored template fail closed。M1 `hypothesis_ids` 不决定 M2 universe。
- **Binding：** bound evidence 精确绑定 hypothesis/obligation/predicate、subject/anchor/location/spatial
  substitution、query 与 source observation。Typed identity witness 才能跨 viewpoint 合并 units；禁止
  direct/transitive same-view slot merge，link 后旧 evidence 不迁移。
- **State：** append-only hash-chain transitions 为唯一 authority；observation、identity、query、evidence、
  revoke 与 CONTINUE 均事务 fold。Decision cut、budget/cost、ledger 与 certificate freshness从 raw log
  推导。CONTINUE exact 重验 terminal/report/feedback/prior state 与 execution signal。
- **Offline：** 独立实现重算 bundle/certificate/terminal，再读 hidden truth。它不 import/call runtime
  verifier，也不相信 online 自报的 policy reason code。

## 4. Cheapest killers 与结果

| Killer | 修复后结果 |
|---|---|
| forged closure / external frontier mutation | 无法构造 NOT；cached-state forge 被 bundle/state mismatch 拒绝 |
| 完整 2/3-node closure | 内部产生绑定 exact observations/cut/digests 的合法 witness |
| 同 event ID 改 candidate / 新 candidate | state digest 改变，旧 NOT certificate stale |
| mixed subject、wrong anchor、wrong hypothesis refutation | 即使 certificate 重新 seal 也因 typed coverage 拒绝 |
| 任意/same-view/transitive identity merge | typed witness provenance、跨-view 与 component injectivity 拒绝 |
| relation 只有 visible subject、没有 anchor slot | `anchor_residual` 保持 unresolved；generic location coverage 不足以 NOT |
| multi-room / relation+room / optional anchor | template admission fail closed |
| future observation/evidence、broken transition parent | admission 或 verifier 重算拒绝 |
| forged evidence scope/producer/dependency group | runtime admission 与 independent offline audit 一致拒绝 |
| object ID 缺失/重复或 feature row/schema 不一致 | observation 事务拒绝，不能缩小 universe |
| instruction/template、panorama/candidate schema mismatch | exact audited interface 拒绝 |
| caller budget/cost/query snapshot 篡改 | verifier 与 fold-derived snapshots 不一致，拒绝 |
| reject→CONTINUE→next observation→rebuild | 真实顺序 state 演化；final online ACCEPT 且 offline TRUE_ACCEPT |
| tampered CONTINUE/online accepted flag/GT extra field | exact prefix structural audit 拒绝 |
| digest/provenance/stale certificate rejection | `CORRECT_REJECT`，不再误报 `FALSE_REJECT` |
| 合法真证书被 test-only verifier 拒绝 | `FALSE_REJECT`；伪造 policy reason 仍不能豁免 |
| equivalent replay | audit bundle 与 certificate/full digest 完全相同 |
| support/refute/conflict × closure × time cartesian checks | 不会同时接受 FOUND 与 NOT_FOUND |

额外 smoke：12 次连续 valid CONTINUE 的 state mutation 用时约 0.85 s，独立 offline fold 约 0.06 s；
此前 prefix 递归的指数增长已移除。该数字仅是本机 micro smoke，不是性能 claim。

## 5. 实际验证命令

```bash
python -m py_compile proofnav/*.py proofnav/runtime/*.py proofnav/offline/*.py \
  tests/m1/*.py tests/m2/*.py tests/m21/*.py tests/integration/*.py
# exit 0

python -m unittest discover -s tests/m1 -p 'test_*.py' -v
# Ran 27 tests ... OK

python -m unittest discover -s tests/m2 -p 'test_*.py' -v
# Ran 52 tests ... OK

python -m unittest discover -s tests/m21 -p 'test_*.py' -v
# Ran 4 tests ... OK

python -m unittest discover -s tests -p 'test_*.py' -v
# Ran 84 tests ... OK (skipped=1; local M0 integration remains default-off)
```

本轮没有设置 `PROOFNAV_RUN_LOCAL_M0_INTEGRATION=1`，因此没有重跑 M0。默认 discover 只确认该
integration 仍按约定 opt-in。

## 6. Verdict 与未验证项

旧 bulk-snapshot M2 与“online acceptance 无条件等于事实正确”永久撤回。M2.1 successor 在以下
条件化 claim 下通过 gate，M2-A/M2-B 可恢复 complete：给定 exact audited observation interface、
完整 validated proof template、合法 admitted identity witnesses 和 factual-correct typed evidence，
closure、causality、binding、coverage、accounting 与 terminal legality可由事件重算并 fail closed。

尚未验证、也未冒充完成：

- predicate、coverage 与 SAME_ENTITY output 的世界事实正确性；
- 自动 instruction compiler、online room/anchor 可获得性、risk calibration；
- producer/profile 字符串之外的跨进程 cryptographic attestation；
- 正式 DUET ACTION/path cost、rollout/re-ranking 接线；
- 正式 paired REVERIE、训练、GPU、benchmark 指标或性能提升。

前四项中的感知/identity/calibration 属于获授权后的 M3；真实 ACTION trace 与 DUET closed loop 属于
M4。本轮无代码结构阻塞，但这些阶段边界仍是明确的研究阻塞，不能由 controlled tests 代替。
