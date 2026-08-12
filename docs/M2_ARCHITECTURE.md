# ProofNav M2.1 可执行证明架构与语义

> 修订日期：2026-08-12（UTC）
> 当前文档状态：M2.1 successor 已通过 CPU adversarial gate；旧 bulk-snapshot M2 complete 声明永久撤回，M2-A/M2-B 仅按本文第 10 节的条件化含义恢复 complete
> 边界：CPU micro logic；不是实际感知、训练、DUET 正式闭环或 benchmark 结果

## 1. 为什么旧 M2 结论无效

旧 proof state 一次性接收 observations、静态 hypothesis IDs、frontier、`scope_closed`、budget
和 cost。snapshot 又只绑定 observation ID，不绑定 observation 内容。由此产生四个实际反例：

1. `vp0` 明确发现未访问 `vp1`，调用方仍能用 `frontier=[]/scope_closed=True` 取得
   NOT_FOUND；
2. 同一 hypothesis 的必要谓词可由两个不同对象分别支持，并被拼成 FOUND；
3. step/event 99 的 observation/evidence 可进入只报告 step 1 的决定；
4. online 正确拒绝 digest 损坏的证书，offline 却只因 claim 方向正确而报 `FALSE_REJECT`。

因此旧 complete 声明不能靠修 fixture 保留。M2.1 改为 event-sourced successor contracts；M1
所有 v1 wire contract 保持原字段与含义。

## 2. Failure-to-design loop

| 候选 | 优点 | 最小反例 / 淘汰原因 |
|---|---|---|
| A. 静态 hypothesis IDs，frontier 改为 candidates 派生，并要求全部 evidence 同一 unit | 改动小 | 调用方仍可漏列 hypothesis；同实体跨视角会被误杀；relation anchor 不能表达 |
| B. 每个 visible object proposal 一个 flat hypothesis | GT-free、与 DUET object slots 直接兼容 | 零 proposal/proposal miss 时 NOT_FOUND 变成 vacuous truth；不能结算未提议实体 |
| C. 直接把 DUET GraphMap 当 closure authority | 复用已有 visited/unvisited | certificate/offline 无法从输入独立重算；把证明绑死到可变内部对象；travel-only 节点语义含混 |
| D. 因果 event log + location/slot/residual 分层 universe + typed binding | closure、universe、binding、time cut 均可重算；保留 GT firewall | 当前选择；代价是显式 successor schema 和保守 residual coverage |

候选 D 是四个反例共同要求的最小充分设计。更强的 CSP/UNSAT proof 可表达复杂 existential
join，但会引入 solver、proof format 和显著基础设施，超出 M2.1，未采用。

## 3. 唯一状态权威：causal transition log

公开构造器只接收 `scope/template/risk_claims`。后续仅允许：

```text
OBSERVATION -> IDENTITY_LINK* -> QUERY -> EVIDENCE/REVOKE
            -> certificate proposal -> verifier -> CONTINUE
            -> next OBSERVATION -> ...
```

每条 `proof-transition.v2` 保存连续 `transition_seq`、父 transition digest、event type、payload
digest 和自身 digest。每次 mutation 先在副本上完整 fold，验证成功后才提交。调用方不能再传入
observations 数组、frontier 数组、closure bool、budget 或 cost。

Observation 约束：首事件必须是 scope start、`event_seq=step=0`；后续 event sequence 严格递增，
controlled M2.1 每个 step 恰有一个 observation；新 viewpoint 必须先由历史 candidate 发现；episode、
scan、producer 和 source schema 必须匹配 code-owned admission profile。Audited feature contract 进一步
要求 panorama `[36,D] float32`、view/candidate point index 属于 `[0,35]`、candidate feature 为
`[D] float32`、object IDs 唯一且与 `[N,768]/[N,4]/[N,3] float32` 三组 object feature 行数
严格一致；template 的 instruction digest 必须匹配每个 admitted observation。QUERY 必须先于其
EVIDENCE；引用某个合并 binding 的 query/evidence 必须晚于相应 identity witness；较早的旧 binding
evidence 保留为 audit record，但不再结算新 universe。certificate 绑定当前 causal head，任何新
observation、candidate、query、evidence、identity witness、revocation、CONTINUE 或 scope/template
变化都会使旧证书 stale。

`CONTINUE_SEARCH` 不是一个未记录字符串：state 只接受 exact terminal/report schema、绑定当前
cut/tip/state、accepted=false、accepted identity 为空、状态为 REJECT/DEFER、feedback 与 execution
signal 自洽的完整 record，然后 replay 才能进入下一 observation。到达任一资源上限时仍可接受在
上限内形成的证书，但不得再记录 CONTINUE。

## 4. Machine-checkable topology closure

在 decision cut \(\tau\)：

\[
V_\tau=\{\text{admitted observation 的 viewpoint}\}
\]

\[
D_\tau=\{\text{scope start}\}\cup
       \bigcup_{o\le\tau}\text{candidateEndpoints}(o),\quad
F_\tau=D_\tau-V_\tau.
\]

Candidate edge 是历史 observation 的 append-only union；同一点再次观察时，空列表不能删除过去
发现的边。只有 observation 使用 exact registered interface profile，且 \(F_\tau=\varnothing\)，
state 才内部生成 `closure-witness.v2`。production profile 固定绑定 M0 adjacency artifact：

```text
sha256 2d2cf87d402b7d6e7283bf86c5da56cacd49312359d367c8c5d6234dbe9b47b8
86 scans / 10,318 viewpoints / 41,732 directed edges / 0 mismatch
```

Witness 绑定 scope/version/digest、observation interface、interface audit、generator、decision cut、
ordered observation IDs、完整 observation digest、visited/candidate/frontier digest、universe digest
和 binding digest。online verifier 从 audit bundle 的原始 transitions 重算，GraphMap 与
`no_vp_left/searchable_frontier` 最多是执行信号，均无 closure authority。runtime 从未获得完整
connectivity 或 evaluator truth。

## 5. Dynamic hypothesis universe

M1 scope v1 仍因冻结合同而保留 `hypothesis_ids` 字段，但 M2.1 明确不把它当证明全集。M2.1
由 agent-visible template 与 cut 前 observation 自动生成：

- 每个 visible object proposal 形成 object unit；未有合法 identity witness 时，跨 viewpoint units 不合并；
- typed identity witness 可将两个跨 viewpoint observed units 合成 subject binding，并使旧
  universe/certificate stale；witness 绑定两端 source event/observation digest 与 exact controlled
  provenance，component 内每个 viewpoint 至多一个 slot，禁止直接或传递地合并同视角不同对象；
  新 binding 必须重新 query，历史 evidence 不能自动迁移；production identity admission 保持关闭；
- entity/attribute template 为每个 subject binding 生成 subject hypothesis；
- relation template 生成 co-observed subject/anchor 的有向 typed alternatives，并为每个 visible
  subject×location 生成 `anchor_residual` coverage hypothesis，防止 anchor proposal miss 让 relation
  NOT_FOUND vacuous；
- room template 生成 subject/location/agent-visible spatial anchor alternatives；
- 每个 visited viewpoint 无条件生成一个 `location_residual` hypothesis，表示“可能未进入 object
  proposals 的剩余目标”，防止零 proposal 或 proposal miss 形成 vacuous NOT_FOUND。

Hypothesis、obligation 和 binding ID 均由 scope/template/visible units 的 canonical hash 派生，
调用方不能自选或漏列。新 slot、candidate、observation 或 identity witness 自动更新 universe digest。

`location_residual/anchor_residual` 的 coverage obligation 与 object predicate 分工严格：viewpoint-level
coverage 只能结算相应 residual，不能支持对象属性；object-slot evidence 不能假装覆盖整个 viewpoint。
M2.1 只支持至多一个、且必须为 necessary 的 anchored predicate（一个 relation 或一个 room_anchor）；
多 room、relation+room 或 optional anchored template 均 fail closed，而不是错误复用第一个 anchor。

## 6. Typed binding 与证书语义

M1 evidence v1 不扩字段。M2.1 `bound-evidence.v2` 在外层绑定：query、hypothesis、obligation、
predicate kind、source observation digest，以及：

```text
subject_binding_id + subject_unit_ids
anchor_binding_id  + anchor_unit_ids
location_binding_id
spatial_anchor_id
```

机器检查规则：

- entity/attribute evidence 必须来自该 subject binding 的真实 observed slot；
- relation 必须 exact 匹配 subject 与 anchor，且两者在来源 observation 中共同可见；
- room evidence 必须 exact 匹配 subject location 与 instruction-visible spatial anchor；
- coverage 必须来自对应 viewpoint view unit；
- obligation/predicate ID 只是索引，不能替代上述 binding proof；
- source observation、query 和 evidence 必须都是 decision cut 祖先。
- nested evidence 的 scope contract、controlled adapter producer 和 dependency group 必须精确匹配
  code-owned profile；不能只伪造一个看似合法的 adapter version。

FOUND 当且仅当存在一个非 residual dynamic hypothesis，其全部 necessary predicates 在同一个
typed binding 下为 SATISFIED，且没有 conflict。NOT_FOUND 当且仅当 topology closure witness
存在，并且每个 dynamic subject/relation/room alternative 与每个 location/anchor residual 至少有一个
合法 necessary refutation。两种证书都保存 exact coverage；builder 和 verifier分别检查。

## 7. 派生 accounting

Budget/cost 不再由调用方报告：

- observation count = OBSERVATION transitions；
- predicate query count = unique QUERY transitions + admitted identity witnesses；
- ledger count = IDENTITY_LINK + EVIDENCE + REVOKE transitions；
- steps = maximum admitted observation step + 1；
- M2.1 controlled high-level action count = step maximum；
- travel = consecutive endpoint positions 的欧氏距离；
- storage = canonical transition bytes；
- online compute 目前明确记为 `0.0`，不是实测 latency。

`within_budget` 使用 `used <= limit`，允许在最后一个预算单位上出证书；`can_continue` 使用
`used < limit`。M4 若要支持一条 global action 展开多条边，必须引入 ACTION successor event 并从
真实 execution trace 重算，不能沿用这个 controlled micro convention 冒充正式成本。

## 8. Online / production 边界

Runtime verifier 接收 self-contained decision audit bundle，而不是相信 caller snapshot。它重算
transition chain、topology、universe、binding、resolution、accounting、risk、closure、state、bundle
和 certificate identity。Replay verifier只为 offline controlled profile开放；production verifier
对该 profile fail closed。

M2.1 production evidence 与 identity-link admission 继续为 zero-admission。M3 只能通过 code-owned
adapter、明确 schema/version bump 和新的 falsification gate 开放，不能靠配置 alias。

## 9. Offline taxonomy

Offline auditor 不导入或调用 runtime verifier，也不把 truth 回传 runtime。它先对 frozen audit
bundle、certificate、terminal proposal/accepted identity 做独立 structural audit，再比较 hidden
truth：

- `TRUE_ACCEPT`：online 接受，结构合法且 scope/binding/claim 与 truth 一致；
- `FALSE_ACCEPT`：online 接受，但结构或事实不成立；
- `FALSE_REJECT`：证书结构、freshness、provenance、scope、binding、claim 和 truth 全部成立，却被
  compatible online verifier 拒绝；
- `CORRECT_REJECT`：malformed/tampered/stale/future/wrong-provenance 等非法证书被拒绝；
- `WRONG_SCOPE`：一个在自身 scope 内完整合法的 artifact 与被审计 truth scope 不同；
- `UNRESOLVED`：无证书/DEFER/无法形成可审计主张。

特别地，digest 正确拒绝和 production firewall 对 controlled artifact 的拒绝都不是
`FALSE_REJECT`。Terminal v2 显式绑定 proposed 与 accepted certificate ID/full digest、decision cut、
proof-state digest；ID 仅是 digest 前缀，full digest 才是权威。

ControlledTruth v2 与 ControlledEvidenceScript v2 分离：truth 只表示一致的事实 obligation
evaluation；script 可故意产生与 truth 相反的 predicate output，用来测试 `FALSE_ACCEPT`，不再靠
构造自相矛盾 hidden truth。

## 10. 完成状态与 claim 边界

本轮四个旧反例与扩展 red-team corpus 全部通过后，M2-A（causal proof state/certificate）与 M2-B
（online gate/independent offline audit）按以下限定恢复 complete：**给定 exact audited observation
interface、完整且已验证的 proof template、合法 admitted identity witnesses，以及 factual-correct
typed predicate/coverage evidence，closure、causality、binding、coverage、accounting 和 terminal
legality均可从 raw event log 重算并 fail closed。**

这不是无条件世界事实保证。旧“online acceptance 等于事实正确”与旧 bulk-snapshot complete claim
保持撤回。Producer/profile 字符串只是进程内 contract boundary，不是密码学 attestation；identity
association、predicate/coverage factual correctness、instruction compiler completeness、room label
可获得性与 risk calibration 尚未解决。Controlled action/cost convention 也不等于正式 DUET rollout
成本，没有 benchmark 或性能增益结果。前述 factual adapter/calibration 问题才属于 M3；真实 ACTION
trace、DUET 闭环与 re-ranking 属于 M4。本轮没有把 closure、binding、causality 或 offline taxonomy
再次推迟给 M3。
