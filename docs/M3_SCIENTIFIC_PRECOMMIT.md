# ProofNav M3 scientific precommit

> 冻结时间：2026-08-12（UTC）  
> 冻结点：任何新增 M3 inference、threshold fitting 或 calibration 结果之前  
> 状态：revised claim 的 cheapest-killer-first precommit；不是结果报告

## 1. 注册问题与贡献 claim

**问题。** 在 false-premise VLN 中，agent 只看到逐步到达 viewpoint 的 DUET 信号；它需要在
evaluator truth 不进入 runtime 的条件下，决定哪些实体/谓词证据可以进入 FOUND/NOT_FOUND 证书，
并在证据越域、相关性未处理、coverage 或 identity 未闭合时保持 UNRESOLVED。

**本阶段中心 claim。** ProofNav M3 研究的是一种 **method/system** 机制：把真实 agent-visible
predicate signals 变成带版本化 calibration risk atoms 的 typed evidence，由 certificate 实际选择的
atoms 派生 terminal risk，并让 verifier 对不完整 residual、identity 或依赖假设 fail closed。

本项目不再主张首次提出 false-premise VLN、paired REVERIE、FOUND/NOT_FOUND、选择性预测、
conformal calibration、跨视角关联或 evidence exploration。这些 claim 已被 closest work 覆盖。

## 2. Closest-work gate

| 邻居 | 已覆盖 | ProofNav 仍待证明的最小差异 |
|---|---|---|
| VLN-NF / ROAM | REVERIE-derived false-premise pairs、FOUND/NOT_FOUND、证据探索与 coverage-aware stopping | 无 GT runtime 上的 machine-checkable true path/refutation cover；calibration-derived certificate risk；不完备 residual/identity 时 verifier 强制 UNRESOLVED |
| Selective Classification / Conformal Risk Control | 预测/拒答、risk–coverage、冻结分数的 post-hoc 风险控制 | 这些是 baseline，不是 ProofNav 新意；需验证它们如何合法进入事件源 certificate，而非把 score 当 risk |
| image-wise conformal object detection | proposal/box recall 与 FNR 校准 | detector 空输出时可能不存在可满足目标风险的参数；因此 empty proposals 不能关闭 ProofNav residual |
| confidence sequences / beyond-exchangeability conformal | optional stopping 或非交换修正 | DUET logits 不自动满足其假设；M3-A 不声称 sequential validity |
| ConceptGraphs / PAC MOT | 跨视角语义几何匹配或带风险的 tracking edge | 当前 DUET 无 RGB-D/mask/3D；M3-A identity 继续 zero-admission |

结论是 **problem/claim collision + partial method gap**，不是整条母方向的 Stop。M3-A 采用
`Revise → conditional Continue`：只实现 evidence validity boundary 与最小真实 SUPPORT slice；论文级
新意仍须由后续 certificate-level control 或 proof-obligation planning 的完整成本/风险结果证明。

## 3. 精确定义

### 3.1 Predicate 与 binding

- `entity` 的 M3-A 适用域是：给定官方 frozen annotated-slot interface，一个 instruction-conditioned
  DUET object grounding signal 是否支持 **该 object slot 是指令目标**。
- 它不是 detector existence、类别识别、开放世界发现或 residual completeness。
- attribute、relation、room-anchor 继续沿用 M2.1 typed binding 语义，但没有获准的真实 adapter 时只能
  ABSTAIN。
- relation 首阶段仍冻结为同一来源 observation 内一个 subject 和一个 anchor；至多一个 necessary
  anchored predicate。扩展前必须有 predicate-specific labels 与 calibration。

### 3.2 三值 evidence decision

- `SUPPORTS`：signal、artifact、domain、binding 和 polarity 全部合法，且 artifact 为该 evidence family
  声明一个 false-support risk atom。
- `REFUTES`：artifact 对“错误排除真实满足者”声明 false-refutation atom。M3-A 不开放此方向。
- `ABSTAIN`：没有可合法结算 obligation 的 evidence transition；原因必须记录。无 artifact、越域、
  unsupported predicate、NaN/Inf、empty proposal、低 score、STOP、图耗尽都属于此类。

### 3.3 Coverage 与 identity

- topology closure 仍由 M2.1 observation candidates 推导，与 semantic coverage 分离。
- residual coverage 的目标事件是：scope/location 内存在满足 target template 的实例或 relation anchor，
  但 proposal/universe 没有表示它。没有对该事件的 target-conditioned artifact 时 residual 保持 OPEN。
- SAME_ENTITY 的风险事件是把两个真实不同对象错误合并。object ID 相等只可作 offline label，不能作
  runtime witness；M3-A production identity admission 为 zero。

## 4. 风险事件与组合

- false-support：certificate 使用的 SUPPORT evidence 对其 typed predicate/binding 为假。
- false-refutation：REFUTES evidence 排除了一个真实满足的 typed hypothesis。
- missed-residual：仍有满足者/anchor 未被枚举，却接受了对应 coverage refutation。
- false-link：identity component 含两个不同真实实体。

M3-A baseline 是严格 union composition：

```text
R_FOUND = min(1, sum selected SUPPORT atoms + sum selected identity atoms)
R_NOT   = min(1, sum selected REFUTE atoms + residual atoms + identity atoms)
```

相关性不破坏 union bound，但会使它保守。只有 artifact 明确把一个 dependency group 校准为“组内任一
错误”的 familywise event，才可对该 group 计一次；任意相同字符串不能获得去重。SUPPORT 与 REFUTE
polarity 不可交换。calibration failure confidence 与 task-error upper bound 分开报告。

M3-A 不使用 independence/product/Sidák，不累加重复 observation 获得更小 risk，不声称 optional-
stopping validity。revisit 和同一 source observation 的 predicates 至少归入同一 dependency lineage。

## 5. Split、单位与 shift precommit

- 正式 M3 train/development/calibration/test 必须按 scan 隔离。
- `val_unseen` 与 test 不参与 threshold、方法、适用域或 artifact 选择。
- calibration 的基本 sample unit 是 scan；同 scan 的 episode/viewpoint/object 输出先按预先定义的
  familywise loss 聚合。
- 当前官方 DUET checkpoint 已见过 60 个 train scans；`val_train_seen/val_seen` 与这些 scans 重叠，
  因此当前资源不能产生 unseen-scan statistical guarantee。
- 本轮若拟合 seen-scan micro artifact，只能标成 `descriptive_seen_scan_micro`，用于接口 falsification，
  不能宣传为 held-out unseen guarantee；unseen scan 必须 ABSTAIN。
- 本轮真实 micro slice 在运行前固定为 `val_train_seen`、seed 0、至多 4 个 batch（batch size 8）。
  scan 分工由 `int(SHA256(scan_id)[:8], 16) % 3` 唯一决定：0=development、
  1=calibration、2=demonstration；不得根据输出分数或标签调换。首版 absolute-logit SUPPORT
  threshold 固定为 `3.0`，signal killer 同时保留单 proposal/target-absent 反例；该规则只验证接口，
  不形成正式模型选择或 benchmark 结果。
- 正式 guarantee 要求重新预留 scan-disjoint calibration scans，或取得不属于 val-unseen/test 的新增
  labeled scans，并保持 model fitting 与 calibration 独立。

## 6. 预注册 baseline、ablation 与指标

Baseline：raw DUET logit threshold、object softmax/top-1、set-valued/selective grounding、strict union
composition、scan/episode worst-case；后续才比较轻量 target-slot+null head、CRC 或 anytime-valid方法。

必须报告：false-support、false-refutation、selective risk–coverage、false-FOUND、false-NOT-FOUND、
abstention、calibration-bound violation、repeat/correlation stress、seen/unseen shift、residual miss、identity
false-link，以及 feature/model inference、query、certificate/verifier、artifact build、存储和离线标注成本。
ECE、AUROC 或普通 accuracy 只能作诊断，不能单独支持 certificate risk claim。

最小消融：无 calibration、caller-reported risk、忽略 dependency、重复 evidence、无 residual、无
identity risk、SUPPORT/REFUTE polarity swap、关闭 M3 profile。

## 7. 三个最可能 falsifier 与预先决策

1. **Signal killer：** target-absent/单 proposal observations 上错误 slot 获得高分，导致 frozen DUET
   score 在可用风险下零 coverage。若发生，转向冻结 DUET feature 上的轻量 binary target-slot+null
   head；不把阈值后处理包装成成功。
2. **Coverage killer：** annotated slot inventory 或 detector misses 无法支持 target-conditioned residual。
   M3-A 保持 NOT_FOUND sealed；M3-B 需要明确的 miss labels 与 target-conditioned coverage head。
3. **Novelty killer：** ROAM + standard CRC/union/episode-max 已直接覆盖最终机制。若 certificate-level
   control 或后续 planner 没有新保证、能力或完整成本优势，则停止 method claim，但保留 benchmark
   diagnosis 与正确性基础设施。

预先决策：

- **Continue：** 真实 DUET signal、code-owned artifact、derived atom 与 entity SUPPORT/ABSTAIN slice
  全链通过，且所有越域/篡改/重复攻击 fail closed。
- **Revise：** P1 logit calibration 被 signal killer 击败；转轻量 null-aware head并重置 calibration gate。
- **Pivot：** 只有改变母问题/benchmark/base 才构成 Pivot，必须由用户确认；本轮不授权。
- **Stop：** residual/identity/attribute 等具体 capability 在无合法标签或信号时单独停止 admission，
  不是停止 ProofNav 母问题。

## 8. 完整成本预账本与许可

当前允许：已有 HDF5/checkpoint 的只读 digest、已有 M0 trace 分析、CPU schema/falsification、默认关闭的
signal extractor、小型已冻结 development slice GPU inference、轻量 calibration statistics。

账本必须计入：3.14 GB panorama HDF5、259 MB object HDF5、2.18 GB DUET checkpoint、每步 DUET
forward、signal serialization、artifact builder、每条 evidence/query、risk composition、certificate/
verifier、artifact storage，以及所有 offline labels。已有 HDF5/checkpoint 是摊销资源，不能记为零成本。

本 gate 禁止正式 benchmark、完整 paired generation、大模型下载/训练、M4 policy/re-ranking、test
submission 或依据 val-unseen/test 修改 threshold。
