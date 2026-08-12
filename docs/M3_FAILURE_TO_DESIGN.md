# M3-A failure-to-design record

> 日期：2026-08-12（UTC）  
> 选择原则：cheapest distinguishing falsification；固定 ProofNav 母问题，不锁死内部 evidence 方法

## 1. Predicate signal candidates

| 候选 | 统计含义与成本 | Cheapest killer | 决定 |
|---|---|---|---|
| P1 冻结 DUET object logits 的一侧 selective calibration | 无新训练，真实 instruction-conditioned signal；标准方法 baseline | target-absent、单 proposal、wrong top-logit false-support–coverage | 首先尝试；只允许 entity SUPPORT |
| P2 set-valued/conformal grounding | 保留多个 plausible slots，singleton 才 SUPPORT；需要 scan-unit calibration | marginal slot coverage 不等于 accepted-certificate risk，重复/策略选择破坏简单解释 | 作为 mandatory baseline，不先锁定 |
| P3 冻结 feature 上的 binary target-slot + null head | 显式学习 no-target；需要 labeled negatives 和轻量训练 | scan-disjoint labels是否足够；是否只是普通 head且无可用 coverage | P1 被杀后的 smallest redesign |
| P4 额外冻结视觉语言模型 | 可增加 open-vocabulary signal | 当前无 raw RGB/local checkpoint；下载和计算更大 | M3-A 淘汰 |

真实 M0 trace 的最小反例：step 9/10 只有一个错误 proposal，object softmax 必为 1；因此 softmax、
top-1 或 margin 不能未经 calibration 产生 SUPPORT。首个 sufficient statistic 必须至少绑定完整 finite
logit vector、ordered proposal IDs/mask、proposal count、absolute selected logit 与 null policy。

## 2. Residual coverage candidates

| 候选 | 结论 |
|---|---|
| empty proposals / STOP / low logit / graph exhausted | 直接淘汰；均不证明 target-conditioned miss event 为假 |
| HDF5 与 BBoxes inventory audit | 只诊断 frozen annotated interface，不能提供非-GT detector completeness |
| target-conditioned residual head | 最小语义充分方案；输入 panorama+instruction+proposal set，预测仍有遗漏满足者；需 exhaustive labels |
| scan-level simultaneous coverage set | 对 adaptive visits 最保守，但需更多 calibration scans；进入 M3-B |

M3-A 不开放 coverage。`location_residual/anchor_residual` 继续 OPEN，因此 entity SUPPORT slice只能形成
FOUND；不能形成 NOT_FOUND。

## 3. Identity candidates

| 候选 | 结论 |
|---|---|
| object ID equality | 淘汰；ID 来自 annotation-backed inventory且只能作 offline label |
| feature cosine / mutual NN | 便宜 baseline，但需要 hard negatives 和 false-link calibration |
| 轻量 re-ID metric head | 信号更强，需跨 scan pair labels与训练 |
| set-valued global matching + injectivity | 最符合 M2 binding，但成本最高；需 component-level risk |
| no-link | M3-A 采用；保持每个 viewpoint slot 为独立 hypothesis |

## 4. Risk composition candidates

| 候选 | 结论 |
|---|---|
| caller 提供 `upper_bound` | 淘汰；当前 M2 controlled legacy 只验证范围并原样复制，不能用于 M3 production |
| strict union of evidence/link/residual atoms | M3-A 采用；无独立假设，保守且可重算 |
| independence/product/Sidák | 淘汰；同 observation、revisit、共享 model 全部相关 |
| whole-certificate/sequence calibration | 需固定 M4 policy 与 paired episodes；M3-B/M4候选 |
| confidence sequence/e-process | 可处理 optional stopping，但必须新建有效 filtration/score；不是 logits 的免费性质 |

Dependency-group 字符串本身不是风险折扣。只有 artifact 明确校准“组内任一错误”时才去重；普通
per-emission bound 即使 group 相同也逐 atom union。

## 5. 缺标签的最小增强

- entity：现有 `gt_obj_id/obj2vps` 只在 offline artifact builder 使用，足够做 annotated-slot grounding。
- attribute：严格 paired calibration scans 上标注 target slot 属性满足/不满足；冻结 feature head。
- relation：首阶段只标一个共视角 subject-anchor 有向关系，保留当前一个 necessary anchor限制。
- room-anchor：需要公开、非 target-derived room/region contract与 labels；坐标或 instruction 名称不能自证。
- residual：每个 calibration location 标所有满足 template 的实例及 proposal misses；只标已提议对象不够。
- identity：跨 viewpoint component 与 hard negative pairs；ID仅做 offline label，adapter输入中删除 ID值。

SOON文本字段、VLM pseudo-label 或 HDF5 `names` 不能替代 REVERIE factual truth。

## 6. 选择结果

Smallest sufficient M3-A 是：

```text
真实 DUET full object-logit vector
→ annotated-slot entity-only selective adapter
→ versioned offline calibration artifact
→ SUPPORTS / ABSTAIN
→ evidence risk atom
→ strict union composer
→ M2.1 FOUND builder/verifier
```

它不开放 REFUTES、NOT_FOUND、coverage、identity、attribute、relation 或 room。普通 calibration、union
bound 与 ABSTAIN 本身不作为论文创新；潜在差异仍需在 certificate-level semantics 与后续 proof-guided
acquisition 上验证。

## 7. P1 cheapest killer 的实测处置

预注册的 absolute-logit threshold 3.0 在 calibration 分区产生 20 次 SUPPORT 机会，其中
2 次是 false support，分布于 2/6 scans。aggregate artifact 因而只能携带 `1/3` 描述性
scan-familywise bound，而不是 formal statistical guarantee。

这一结果将“接口是否真的”与“方法是否有用”分开：

- 机械诊断：在明示为 vacuous 的 `alpha_F=1.0` 下，真实 signal 经 registered artifact、
  M3 state、certificate、online verifier/terminal 到正式 offline Oracle 为 `TRUE_ACCEPT`；
- 科学门槛：同一证据在 `alpha_F=0.05` 下由 builder 以 `RISK_BUDGET_EXCEEDED` 拒绝，
  terminal 为 `UNRESOLVED`。

所以 P1 的处置是 **mechanism Continue, scientific Revise**，不能为它降低风险标准。
按预注册最小修复，M3-B 转向 P3：冻结 DUET representations 上的 target-slot+null 轻量
head，但必须先获得合法的 scan-disjoint development/calibration labels。当前 checkpoint 已使用所有
train scans，而 val-unseen/test 不允许参与选择；因而在没有预留 scans 或新增合法 labels 前，
不能声称 unseen-scan 保证。
