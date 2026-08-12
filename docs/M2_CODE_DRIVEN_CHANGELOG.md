# ProofNav M2.1 代码驱动变更记录

> 日期：2026-08-12（UTC）  
> 限制：semantic repair + CPU adversarial falsification；没有进入 M3/M4/M5

## 0. 旧 M2 complete 声明撤回

外部复核提出四个可执行 counterexample。本轮先把它们写成 regression，并在旧实现上实际得到
4/4 failures：伪 closure、mixed-object FOUND、future evidence 和 malformed rejection→
`FALSE_REJECT` 均成立。因问题共同来自 caller-owned snapshot semantics，旧
`M2-A complete / M2-B complete` 状态先撤回，不把 fixture 改空来掩盖。

## R1. 从 bulk snapshot 改为 causal event source

删除的 authority：构造器 `observations/frontier_witnesses/scope_closed/budget_status/cost_ledger`。

新增：`proof-transition.v2` 与事务式 state methods。每项 mutation 先在 candidate transition list
完整 fold，通过才提交。Decision cut、transition tip、observation/query/ledger counters 和 proof digest
由历史唯一导出。CONTINUE 保存完整 terminal record，并先绑定 rejected cut，之后才能 ingest next
observation。

为什么不能只补 `event_seq <= budget.steps`：旧 budget 本身也是调用方输入；局部比较仍会让两份
伪造状态互相“证明”。事件 source 同时解决 causality、counter 和 stale identity。

## R2. 从 caller closure 改为 audited event-derived closure

Visited 只来自 admitted observation endpoints；discovered edge 是所有历史 candidates 的保守 union；
frontier 是 discovered minus visited。首 observation/新 endpoint/episode/scan/producer/source schema 均
检查。Closure witness 仅由 code 产生，绑定 raw observation content（不再只绑定 ID）、scope、exact
interface audit、cut、visited/edge/frontier/universe/binding digests。

Production interface 固定到实际 M0 adjacency artifact SHA-256：
`2d2cf87d402b7d6e7283bf86c5da56cacd49312359d367c8c5d6234dbe9b47b8`。
GraphMap/no-vp-left 不作为 verifier authority，也未向 runtime 暴露完整 connectivity。

## R3. 从静态 ID 集改为 dynamic layered universe

M1 scope v1 的 `hypothesis_ids` 为兼容保留，但 M2.1 不信任它决定 NOT universe。Generator 从
visible object slots 生成 subject alternatives；relation 生成 co-observed typed subject/anchor pairs；
room 生成 subject/location/spatial-anchor alternatives；每个 visited location 另外强制生成 residual
coverage hypothesis，防止零 proposal/proposal miss 导致 vacuous NOT。

未经 witness 的跨 viewpoint slots 分属不同 subject；cut 前 typed identity witness 可合并。测试确认同一
subject 可由 vp0 entity evidence 与 vp1 attribute evidence共同支持，因而没有退化为“全部 unit_id
字面相等”。

## R4. Bound evidence successor 与 exact certificate coverage

M1 evidence v1 未改。外层 bound-evidence v2 明确 query、dynamic hypothesis、obligation、predicate
kind、source observation digest 与 subject/anchor/location/spatial binding。Admission 不再只看
obligation ID：object unit 必须真实存在于来源 observation；relation anchor 必须 co-observed；coverage
只能用 viewpoint unit；room 必须匹配 location/spatial anchor。

Certificate v3 保存完整 dynamic hypothesis/binding/coverage 与 decision bundle identity。Builder 和
online verifier 分别检查：FOUND 全 necessary predicates 在一个 non-residual substitution 下成立；
NOT 要求 topology closure + 每个 subject alternative 的合法 refutation + 每个 residual coverage。

## R5. Accounting 由 fold 导出

Observation、unique query、ledger、step、controlled high-level action、travel、storage fields 不再接受
caller 报告。Budget 拆为 `within_budget (<=)` 与 `can_continue (<)`，允许最后一个预算单位出证书。
Compute 明确为非实测 0.0；M4 global path/action cost 需要新 ACTION successor，不能把 controlled
约定当正式 ledger。

## R6. Terminal identity 与独立 offline structural audit

Terminal v2 同时记录 proposed 与 accepted certificate ID/full digest、decision cut、transition tip 和
proof-state digest。Offline 先用不依赖 runtime 的第二实现重算 raw transitions/topology/universe/
binding/accounting/state，再审 certificate 与 terminal identity，最后才读取 hidden truth。

Taxonomy 新增 `CORRECT_REJECT`：digest/schema/provenance/stale/firewall 等非法 artifact 的拒绝不会再
被标成 `FALSE_REJECT`。真正 FALSE_REJECT 的测试使用 test-only forced-reject verifier 错拒一个结构、
scope、binding、claim、truth 全合法的 certificate。

## R7. Truth 与 predicate output 分离

旧 provider 直接由 truth 生成 evidence，错误 predicate 测试只能先破坏 truth。M2.1
ControlledTruth v2 用逐 obligation typed fact evaluation 重算真值并拒绝 overlap/错误 polarity/
hypothesis/predicate/binding；ControlledEvidenceScript v2 独立描述 replay output，允许它与 truth
相反。由此 `FALSE_ACCEPT` 是真实的“合法但事实错误 output”测试，而不是自相矛盾 fixture。

## R8. Successor red-team 后的补强

完成主重构后又运行了最小反例审计，并把发现合并到正式语义，而非只加 fixture：

- object proposal IDs 必须唯一，且与 object feature 三个 tensor schema 的 N 严格一致；panorama、
  candidate、object dtype/shape 与 instruction digest 也绑定 exact audited interface；
- relation evidence 的 source viewpoint 必须匹配 hypothesis location；nested evidence 的 scope、producer
  与 dependency group 必须匹配 code-owned replay provenance；runtime/offline 两份实现做 differential；
- 任意字符串 identity link 被替换为 source-observation-bound typed identity witness；禁止直接和传递的
  same-view slot merge，link 后旧 evidence 不迁移，并把 witness 计入 query/ledger cost；
- relation 对每个 visible subject×location 增加 `anchor_residual`，避免 anchor proposal miss 造成
  vacuous NOT；多 room、relation+room 与 optional anchored template 均 fail closed；
- CONTINUE prefix 现在 exact 核对 terminal/report/feedback/cut/tip/state/execution，去掉递归指数重算；
  revisit accounting 的 runtime/offline drift 已消除，到达资源上限可出证书但不可继续；
- offline 不再相信 online 自报的 policy reason code；只有独立识别的 production firewall 才是合法
  valid-certificate policy reject。伪造 `VERDICT_TYPE_INVALID` 来拒绝真实合法证书仍分类为
  `FALSE_REJECT`；stale/wrong-provenance/digest damage 为 `CORRECT_REJECT`。

## 保持不变

- M0 未重跑；M1 v1 contracts 与 27 tests 保持；
- production evidence/identity witness 仍 zero-admission；
- runtime 没有 offline/oracle 反向 import；offline structural audit 没有 runtime import；
- `map_nav_src/`、DUET rollout、STOP、训练、数据和 benchmark 均未修改；
- factual predicate validity、adapter capability 和 calibration 仍是 M3，而 closure/binding/causality/
  offline taxonomy 已在 M2.1 内修复。
