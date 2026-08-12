# ProofNav M3-A falsification report and scientific gate

> **Final statistical supersession:** the structural replay remains valid, but
> the former budget-1 `TRUE_ACCEPT` is revoked. Descriptive `2/6` never
> authorizes a certificate; both budgets now return
> `M3_NO_STATISTICAL_GUARANTEE → UNRESOLVED`. See
> [M3A_FINAL_FREEZE.md](M3A_FINAL_FREEZE.md) and
> [M3B_CHAMPION_REPORT.md](M3B_CHAMPION_REPORT.md). Historical text below is
> retained as the falsification trail, not current authority.

> 冻结时间：2026-08-13（UTC）  
> 检索边界：截至冻结日可访问的 primary papers 与 official artifacts  
> 阶段结论：**M3-A fixed-slice engineering = PASS；semantic-ID/prefix P0 = REPAIRED；scientific novelty/spend gate = REVISE**
> 后续权限：只允许 M3-B cheapest-killer 工作；不授权正式 benchmark、大模型下载、GPU 训练或 M4

## 0. Executive verdict

M3-A 最终证明了一件有限的工程事实：一个真实 nested DUET signal 可以经过 code-owned aggregate
artifact、typed adapter、derived risk atom、certificate builder、online verifier 与 terminal audit，形成一个
可重放、可篡改检测、默认 fail-closed 的最小 entity `SUPPORTS/ABSTAIN` 链。

终审发现并修复了两项后置 P0：REVERIE raw `instr_id=pathId_objId_instrIdx` 的 semantic alias 已由
`(scan,start_viewpoint,instruction)` 派生的 opaque runtime identity 替代，offline annotation 通过同一
agent-visible tuple 独立 join；registry 又新增 canonical demo 五条 observation prefix seal，builder、online
verifier 与独立 offline audit 均拒绝伪造 prefix。最终 authority identities 是：signal JSONL
`43874168338d349e90c4111a21829552f68cfe4c33ba28240a832054b42c03bd`，artifact
`11caf45003b2d3f7fb5d3624f75e8b3ca964a5757a72728235e0f19d3bd58370`。下文关于旧
target-bearing `d254…` authority 的段落仅保留为 red-team 历史，不代表最终状态。

这**不是**论文 novelty 结论，也不是有效的统计风险结果。终审发现旧 signal hook 把 batch 中已经结束的
episode rows 继续写入 JSONL，违反“每条 signal 必须对应 active agent-visible decision event”的因果 admission
语义。因此旧 micro 的 signal/example/error counts、artifact digest、bound、demo 与 budget outcomes 全部撤销，
不得作为最终 M3-A 结果或 production authority。

修复后的 active-only extraction 已单独重跑并完成 trajectory audit：193 signals / 32 episodes 与预测轨迹逐条
精确对应，没有 repeated suffix。由该文件重新构建的 P1 calibration 是 6 scans / 54 examples（含 10 个 null
selections）/ 2 error scans，descriptive familywise bound 仍为 `1/3`，没有 confidence guarantee。新 artifact
digest 为 `d2548e03e38c24423f846c372d66ed0abd1dc78b672bf9f6c965566d699f830f`。这是随后撤销的
active-only 中间 identity；
随后 independent red-team 发现第二个 P0：REVERIE `episode_id` 的格式是
`pathId_objId_instrIdx`。32/32 corrected signals 都因此在普通字符串字段中暴露 target object ID；canonical demo
ordering 还直接使用 `episode_id`。allowlist sanitizer 虽删除了 `gt_obj_id` 等显式 forbidden keys，却没有消除
这个 semantic alias。因此 active-only counts/bound 可以保留为**因果正确的 descriptive diagnostic**，但新
artifact/registry/runtime chain 不能作为“无 GT runtime” authority。必须先 pseudonymize episode identity、
从 ordering/lineage 移除可逆 target token、更新 interface identity，并从零重新生成 signal/artifact/manifest/
registry。当前只能声称 adapter 不消费 offline label、schema 没有显式 forbidden-key field。

历史 authority audit 当时还确认 registry 只校验被 wrapper 选中的最终 evidence signal digest，不校验它之前进入
state 的 `OBSERVATION` transition prefix。攻击者可伪造 prefix 的 pose/event ID，同时复用一个 allowlisted final
signal，仍走到机械 CERTIFICATE/ACCEPT。因此当前能力的准确描述是“exact selected-evidence signal
membership with caller-supplied prefix”，不是 exact full replay。该反例随后由 code-owned complete-prefix
manifest 以及 runtime/offline 独立重算修复；当前 final identity 见第 3 节。

还有一个独立 provenance 限制：`model_identity/interface_identity` 等 digests 目前由 CLI 字符串提供，没有
code-checked derivation；保存的 tensor hashes 也不足以从 checkpoint 离线重算 logits。registry 能阻止冻结后
替换一个不在 allowlist 的 signal，却不能证明 checkpoint→tensor→logit 的生成过程。即使修完 ID/prefix，live
authority 仍需可复算生成链、受信 producer capability 或签名/attestation。

该 P0 说明测试通过只证明实现覆盖了已有 contracts；若 contracts 漏掉 active-row causality，测试并不能替代
真实 trace audit。它同样不证明统计 validity、数学新意、与最近邻的不可约差异或 FOUND/NOT_FOUND 科学能力。

## 1. Audit scope and evidence policy

本轮是 bounded falsification audit，不是“没有找到相同标题即算 novelty”的检索。检索按下列信息结构展开：

1. false-premise / infeasible / NOT-FOUND VLN、REVERIE pairing、coverage-aware exploration；
2. reject option、selective prediction、risk--coverage、RCPS、CRC、LTT；
3. sequential / anytime-valid / adaptive selection、repeated evidence、exchangeability violation；
4. object-detection confidence/localization/recall、proposal miss、image-wise loss；
5. multi-view association、open-vocabulary 3D instance fusion、tracking identity uncertainty。

核心判断只依据原论文正文、定理/算法和作者官方 artifact。没有用综述、新闻稿、博客或二手摘要支撑
collision 结论。该 audit 仍不是穷尽式 novelty proof；后续任何中心 claim、表示或统计保证的实质改变都必须
重置 closest-work、equivalence、cost 与 kill-test gate。

## 2. Registered claim and the surviving hypothesis

### 2.1 冻结中心 claim

M3 的注册问题是：在 false-premise VLN 中，把真实 agent-visible predicate signals 变成带版本化 calibration
risk atoms 的 typed evidence，由证书实际选择的 atoms 派生 terminal risk，并在 residual、identity、domain
或依赖假设不完备时 fail closed。

**一句中心 contribution claim（待证）：** ProofNav 试图提供一个无 GT runtime 的 certificate-control 层，
使导航策略自适应选择的 typed evidence 只有在 exact provenance、familywise statistical risk、residual 与
identity obligations 同时可结算时，才能导出机器可审计的 terminal decision。

贡献类型注册为 **method/system**。若未来声称 adaptive/sequential validity，则同时进入 **theory** gate。

### 2.2 Constructive equivalence result

当前 M3-A 可被忠实分解为：

```text
frozen DUET score
  -> confidence threshold
  -> accept / reject option
  -> aggregate calibration metadata
  -> selected evidence-family error atom
  -> Boole/union composition
  -> deterministic certificate/verifier state machine
```

前五项分别落入 selective classification、RCPS/CRC/LTT 和标准 familywise risk accounting；严格 union bound
在任意依赖下成立，本身不是新算法。最后一项的 exact hashing、event sourcing、revocation 与 fail-closed
verifier 是真实工程机制；GT firewall 是目标而非已实现事实。它们目前没有独立定理或与最近系统不可约的
实验能力，不能单独升级成论文级 method novelty。

### 2.3 最小仍可能存活的 scientific hypothesis

> 对一个由导航策略自适应选择、重复观察并最终只使用部分 typed proof obligations 的证书，ProofNav 能否
> 给出绑定 exact observation/model/template/artifact provenance 的 terminal error guarantee，并在 residual
> completeness 与 cross-view identity 未被同一保证覆盖时机器可验证地拒绝接受？

这只是待证 hypothesis。要成为贡献，它至少需要下列之一：

- 一个不能直接化约为现有 anytime-valid RCPS/LTT/CRC 的新定理或结构性结论；或
- 一个最近系统没有的、经真实 scan-disjoint 统计结果支持的 certificate-level capability；或
- 在同等信息、标签和完整成本下，相对 ROAM + 标准 risk-control baseline 的非平凡优势。

若可把全部 policy、loss、selection 与 terminal event 直接编码为现有 RCPS/LTT/anytime-RCPS，则
representation/method claim 必须撤回；schema 与变量增加不能构成 expressivity。

## 3. M3-A micro result: P0 repair and corrected active-only facts

| 项目 | 当前冻结状态 | 可支持的结论 | 不可支持的结论 |
|---|---|---|---|
| real hook | **opaque active-only frozen**：193 signals / 32 episodes；signal SHA-256 `43874168338d349e90c4111a21829552f68cfe4c33ba28240a832054b42c03bd` | signal 与 prediction trajectory 逐 episode 精确匹配；0 repeated suffix；runtime ID 不含 raw evaluator ID | 不是 live producer attestation |
| causal audit | episode lengths `{4: 2, 5: 10, 6: 8, 7: 9, 8: 3}`；partition records P0/P1/P2 = `67/54/72` | 每个 signal 是一次 active policy-visible model event；总数与 length histogram 一致 | 不证明 score 准确或 statistical validity |
| calibration | **causally corrected descriptive diagnostic**：P1 = 6 scans / 54 examples，含 10 null / 2 error scans；bound `2/6 = 1/3`，`confidence=null` | active-only scan-familywise aggregation 的 exact descriptive result | 不是 held-out、conformal、finite-confidence 或 no-GT runtime guarantee |
| artifact/registry | artifact digest `11caf45003b2d3f7fb5d3624f75e8b3ca964a5757a72728235e0f19d3bd58370`；72 signal digests + exact five-observation replay seal | artifact、selected signal、full relevant prefix 均可独立重算；伪造 prefix fail closed | 仍不是 checkpoint→logit attestation |
| demonstration | `1LXtFkjw3qL / runtime-episode-3e91a522140d42cf2330e1be2e530f5d / event_seq 4 / slot 51 / score 5.40303897857666`；signal `5730b8a877cbff8ff14d3a59c0257b620b9414be8d60d53955800d03f848a441` | selector key只来自agent-visible tuple；offline truth在terminal后进入 | 单正例不证明性能或统计保证 |
| budget diagnostics | **final:** budget 1 与 `.05` 均为 `UNRESOLVED/M3_NO_STATISTICAL_GUARANTEE` | state/evidence structural replay 可执行 | descriptive rate 不产生 certificate authority |
| capability | entity SUPPORT-only schema 仍冻结 | adapter surface 不受 numeric refreeze 影响 | REFUTE、residual、identity、attribute、relation、room 仍未开放 |

P0 的因果链是：batched episodes 在不同 step 结束；旧 hook 对整个 batch 无条件 emit；ended rows 被后续 step
重复记录；offline calibration 把这些记录当作合法 opportunities；aggregate counts/bound 与 signal allowlist 随之
污染。修复在真实 hook seam 传入 model call 前的 active mask：当前 stop step 仍是合法 observation，先前已结束
rows 跳过。active-only trajectory equality、零 repeated suffix 和长度直方图共同关闭这个 causal-admission P0；
旧 authority 仍永久撤销，不能与新结果混用。

第二个 P0 的链是：benchmark 把 target object ID 编进 `instr_id/episode_id`；sanitizer 只按字段名删除显式 GT；
signal/event lineage 与 canonical ordering 原样保留该复合 ID；schema、digest、registry 因而把泄漏忠实封存而非
消除。最小修复不是再加一个 forbidden-key alias，而是在进入 M1/M3 observation 前把 evaluator identifier 映射
成不含 target token、不可由 runtime 反解的 code-owned pseudonym，并让 offline join 使用隔离映射；所有依赖
observation/interface/signal digests 的 authority 必须重建。修复后需 adversarial test 证明任意 runtime-visible
identifier 都不能恢复 target object ID，且 canonical selection 不读取 evaluator-derived ordering key。

prefix attack 的链是：registry membership 只作用于 wrapper 内嵌 signal；state 先前接受的 observation events 不在
manifest 中；certificate recomputation 验证 final signal 却不把完整 transition prefix 与它绑定；伪造 pose/
event ID 的 prefix 因而仍可接受。最小修复是显式认证完整 relevant event prefix，或收窄证明使 terminal
semantics 与 prefix 内容无关；仅把 signal manifest 改名不能修复。

P1 signal killer 在 **descriptive micro 层面命中**：预注册 threshold 下 6 个 calibration scans 有 2 个
false-support error scans，`1/3` 明显高于 strict false-FOUND target `.05`。这足以否决“当前 frozen score +
threshold 已有 usable risk--coverage”，但由于 calibration 与 checkpoint training domain 重叠且
`confidence=null`，它不是 population risk estimate、finite-sample guarantee 或正式 benchmark 结论。

## 4. Primary-source closest-work matrix

### 4.1 False-premise VLN and evidence exploration

| Primary work | 原文已经覆盖 | 对 ProofNav 的映射 | Collision | 冻结处理 |
|---|---|---|---|---|
| [VLN-NF / ROAM paper](https://arxiv.org/html/2604.10533v2)；[official project](https://vln-nf.github.io/) | REVERIE-derived feasible/infeasible pairs；target 在指定 room 中缺失；`FOUND/NOT-FOUND` action；in-room evidence exploration；REV-SPL 同时计 room reach、decision、annotated-object coverage 与长度；ROAM = DUET room navigator + VLM/LLM explorer + FREE | 与 ProofNav 的母问题、动作语义、REVERIE context 和“先搜证据再 NOT-FOUND”直接同构 | **problem collision + task/benchmark claim collision + partial method collision** | 撤回“首次 false-premise VLN / evidence-grounded NOT-FOUND / coverage-aware exploration” |

VLN-NF 的 reference exploration 明确使用原 REVERIE target 可见 viewpoint 或 target-room annotated object set，
并声明仅用于 training/evaluation、不暴露给 agent。其 runtime ROAM 用 Grounding-DINO threshold 做 FOUND，
由 LLM/VLM history、frontier exhaustion 或 budget 触发 NOT-FOUND。作者也明确说其目标不是把 absence
形式化成 complete belief-theoretic inference；更 principled absence reasoning 是 future work。

这保留了一个**部分方法缺口**：VLN-NF/ROAM 的 evaluator coverage 与 prompt-based stopping 不是
ProofNav 所要求的 runtime machine-checkable residual proof，也没有把 exact evidence provenance 与
calibration-derived terminal risk 绑定。但“有缺口”不等于 ProofNav 已经填上缺口；M3-A 的 residual/identity
仍是 sealed。

论文还报告 ROAM-GPT-3.5 的 false-NOT-FOUND 错误中，55.7% 是 room reaching，31.0% 是
perception/grounding，13.3% 是 exploration control。这直接支持把 perception calibration 与 coverage
作为 cheapest killers，而不是先扩建 planner。冻结日官方项目仍写明 code/data links 尚未公开，所以本轮
不能把未获得的 artifact 当作已复现 baseline。

### 4.2 Selective prediction and risk control

| Primary work | 原文已经覆盖 | Collision | 对当前 claim 的含义 |
|---|---|---|---|
| [SelectiveNet, ICML 2019](https://proceedings.mlr.press/v97/geifman19a.html) | prediction/reject option、risk--coverage trade-off；并明确已有基于 pretrained confidence threshold 的拒答机制 | **method/claim collision** | `SUPPORTS/ABSTAIN` 与 score threshold 不是新意 |
| [Distribution-Free RCPS, JACM 2021](https://arxiv.org/abs/2101.02703) | 对 black-box predictor 用 holdout set 校准 set size，在 user-specified expected loss 下给 finite-sample control | **method collision** | “模型分数 + holdout risk bound”不能作为 ProofNav 独有机制 |
| [Conformal Risk Control, ICLR 2024](https://openreview.net/pdf?id=33XGfHLtZg) | 对 bounded、随参数单调的 loss 选择 post-hoc parameter，并给 unseen example 的 expected-risk control | **method collision** | frozen score 上调 threshold 并不构成新算法；需逐条满足 exchangeability/monotonicity 等假设 |
| [Learn then Test, AOAS 2025](https://doi.org/10.1214/24-AOAS1998) | 把 black-box predictive algorithm 的有限样本风险控制化为 multiple hypothesis testing，能同时控制多个风险 | **method/representation collision** | typed losses 或多个 error atoms 可能只是 LTT 的 application；必须做 faithful reduction audit |

CRC 原文要求 calibration/test losses exchangeable（常见为 i.i.d.）、predictor 独立于 calibration/test，并要求
loss 对参数单调；非单调时论文明确说不控制风险。当前 M3 artifact 只有 6 个 seen scans、无 confidence，
因此不满足“调用 conformal 名称即可获得 guarantee”的条件。

### 4.3 Sequential, repeated and dependent evidence

| Primary work | 原文已经覆盖 | Collision | ProofNav 当前边界 |
|---|---|---|---|
| [Time-uniform confidence sequences, AOS 2021](https://doi.org/10.1214/20-AOS1991) | 在 unbounded horizon 上同时有效、非渐近的 confidence sequences；基于 martingale/time-uniform concentration | **claim collision**（若声称普通 pointwise bound 可经 optional stopping） | M3-A 没有 confidence sequence/e-process，不声称 anytime validity |
| [Active, anytime-valid RCPS](https://arxiv.org/html/2406.10490) | i.i.d. stream 上的 sequential calibration、可预测的 active label querying、all-time risk validity 与 adaptive stopping；明确构造 filtration 与 e-process | **strong method/theory neighbor** | generic “adaptive stopping 下的 risk control”已被覆盖；相关 navigation trajectory 不自动满足其 i.i.d. 条件，ProofNav 必须给出合法 reduction 或新条件下的结果 |
| [Conformal Prediction Beyond Exchangeability, AOS 2023](https://projecteuclid.org/journals/annals-of-statistics/volume-51/issue-2/Conformal-prediction-beyond-exchangeability/10.1214/23-AOS2276.pdf) | 对 drift、space/time correlation 和 nonsymmetric algorithms 给 weighted conformal 与 coverage-gap bounds | **claim collision / partial method collision** | dependency string 不是 exchangeability 修正；seen-to-unseen shift 不能忽略 |
| [Conformal Object Detection by Sequential Risk Control](https://arxiv.org/html/2505.24038) | 对 confidence threshold 后的 localization/classification 两个 dependent stages 顺序选参，并在 i.i.d. 条件下给 finite-sample guarantee | **method collision**（多阶段 calibration） | 该文的 “sequential” 是 dependent parameter stages，不是任意导航时序；但已否决“多阶段 risk atom 本身新颖” |

严格 union composition 不要求各 atoms 独立；它只会保守。因此 M3-A 使用 union 是正确 baseline，但不是
novelty。真正未解决的是：每个 atom 的 bound 是否在策略看到多次 observation、选择最高分、复用 lineage
并按 data-dependent 时刻停止后仍有效。`dependency_unit` 字符串和 digest dedup 只表达程序规则；除非
artifact 的 sample unit 已把“组内任一错误”作为 familywise label 校准，它们不产生 statistical validity。

重复 observation 也不能凭数量降低 risk。任何 product/Sidák/independence 或重复投票增益都必须另行给出
依赖模型和 calibration；M3-A 正确地没有开放这些推理。

### 4.4 Object detection, proposal miss and residual coverage

| Primary work | 原文已经覆盖 | Collision | 未被覆盖的 ProofNav obligation |
|---|---|---|---|
| [Confident Object Detection via CP/CRC, COPA 2023](https://proceedings.mlr.press/v204/andeol23a.html) | box-wise 与 image-wise conformal losses、confidence/box recall/pixel recall；原文明确指出 conformalized predictor 只能反映 base predictor，base predictor 漏掉大量 GT boxes 时，对少数预测 box 的保证仍无用，under-performing predictor 甚至无法达到目标 image-wise risk | **method collision + verified limitation** | “target template 在 scope 内存在但 proposal universe 未表示”的 missed-residual event |
| [SeqCRC object detection, 2025](https://arxiv.org/html/2505.24038)；[official toolkit](https://github.com/leoandeol/cods) | unknown object count 下统一校准 confidence filtering、localization 与 class sets；提供通用 loss/toolkit | **strong method collision** | navigation trajectory 下 target-conditioned room residual、adaptive viewpoint selection、terminal certificate event |

这两项工作否决“给 detector score/box 加 conformal calibration 即是新意”。它们也给出直接 killer：如果
proposal set 没有真实目标，针对已有 proposal 的正确率或 box interval 无法证明 absence。empty proposals
不是负证据；没有 exhaustive target-conditioned miss labels 和相同 scope 定义时，ProofNav 必须保持
NOT_FOUND sealed。

进一步地，CRC/LTT 足够一般，原则上可把 target-conditioned missed-residual 写成一个 loss。若 ProofNav
只是换了 loss 名称，则没有方法 novelty；必须剩下 certificate/adaptive-control 的不可约结构或新 guarantee。

### 4.5 Cross-view identity and nearest-neighbor association

| Primary work / artifact | 原文已经覆盖 | Collision | ProofNav 当前边界 |
|---|---|---|---|
| [ConceptGraphs, ICRA 2024](https://arxiv.org/abs/2309.16650)；[official project](https://concept-graphs.github.io/)；[official code](https://github.com/concept-graphs/concept-graphs) | posed RGB-D frames、class-agnostic segmentation、semantic + geometric similarity 的 multi-view association、object-centric 3D graph 与 fused CLIP descriptors | **method/system collision** | DUET M3 signal 没有 RGB-D mask/3D point cloud；不能声称同等 identity 能力 |
| [OVIR-3D, CoRL 2023](https://proceedings.mlr.press/v229/lu23a.html)；[official code](https://github.com/shiyoung77/OVIR-3D) | text-aligned 2D region proposals 的 real-time multi-view 3D instance fusion/retrieval | **method collision** | cosine/nearest-neighbor proposal fusion 是 baseline，不是 ProofNav novelty |
| [MOT-CUP](https://arxiv.org/html/2303.14346)；[official project/code](https://coperception.github.io/MOT-CUP/) | 把 conformalized detection-location uncertainty 传播到 Kalman filtering 与 NLL/Hungarian association | **partial method collision** | 论文的 conformal guarantee 是检测位置 interval coverage；association 改进不等于 certificate-level false-link familywise bound |

因此，“object ID 相等”“cosine 最近邻”“mutual nearest neighbor”或“把 uncertainty 输入 Hungarian”均不能
作为新方法 claim。当前最诚实的状态是 identity zero-admission。若 M3-B 开放 identity，必须离线定义
false-link：两个真实不同实体被合入同一 component；并以 hard cross-view negative pairs 校准，而不是把
embedding similarity 当成概率。

### 4.6 Collision coverage-gap matrix

| 维度 | 最近邻已经覆盖 | ProofNav 当前状态 | 是否可能形成不可约 gap |
|---|---|---|---|
| real use | VLN-NF 在 REVERIE/Matterport3D 中处理指定 room 目标缺失 | 同一 false-premise indoor VLN 母问题 | 否；这是 problem collision |
| inputs / observability | ROAM 用 panorama、caption/detection、history、FREE；ConceptGraphs/OVIR 用 RGB-D/3D | M3-A score seam 不消费 offline label，但 signal `episode_id=pathId_objId_instrIdx` 暴露 target-ID alias | 当前 GT firewall **失败**；pseudonymized identity 后才可重新审计是否形成工程差异 |
| timing / information | ROAM closed-loop exploration；anytime-RCPS 处理 i.i.d. stream 的 adaptive labeling/stopping | 导航 observation 由 policy 自适应产生、相关、重复并在终局选择子集 | 是潜在 gap，但必须 formalize filtration/dependence，而非只写 lineage |
| dynamics / actions | `move/FOUND/NOT-FOUND` 已由 VLN-NF 覆盖 | M3-A 只开放 entity SUPPORT；NOT_FOUND sealed | 当前没有新 action/policy expressivity |
| objective / risk | REV-SPL 是 reach/decision/annotated coverage/length 的经验指标；CRC/LTT 控制通用 loss | 目标是 certificate-selected terminal false-FOUND/false-NOT-FOUND risk | 可能是最小 gap；若可直接写成标准 loss，则 collision |
| offline / online | VLN-NF reference paths/annotations 仅训练评测；CRC 使用 holdout calibration | aggregate artifact 不含 per-sample labels，但 runtime signal ID 泄漏 target token，prefix 又可伪造 | 当前 provenance boundary 失败；修复后才可重新比较系统差异 |
| guarantees | ROAM 没有 machine-checkable absence guarantee；CRC/RCPS/anytime-RCPS 有各自假设下的统计保证 | 当前只有局部 deterministic integrity；descriptive bound 无 confidence，semantic/prefix authority失败 | 科学 gap 尚未填上；这是 M3-B 核心 killer |
| deployment / hardware | ROAM 依赖 DUET + VLM/LLM + Grounding-DINO + depth/FREE；3D neighbors 依赖 RGB-D/3D | M3-A 复用 frozen DUET signal，后处理为 stdlib/CPU | 可能有常数成本差，但未做公平完整台账，不能 claim advantage |
| verified failures | ROAM false-NOT breakdown；conformal OD 明示 base proposal miss 限制 | active-row causality 已修并通过真实 trajectory audit；corrected P1 descriptive bound `1/3`；residual/identity 无 artifact | 当前 score 未过 usable-risk gate；先做最小 score repair/completeness killer，不支持先扩建 planner |
| stated open work | ROAM 把 principled absence reasoning 留作 future work | ProofNav 提议 certificate/residual/identity control | open-work overlap 只给研究问题，不给 novelty |

矩阵显示，可发表的候选差异只集中在 **objective/risk、adaptive timing 与 machine-checkable guarantee**；
数据集、动作、false-premise framing、阈值拒答、coverage exploration 和跨视角匹配均不能再当作差异。

## 5. Claim ledger: retained, narrowed and withdrawn

### 5.1 必须撤回或禁止的 claim

- 首次提出 false-premise/infeasible VLN、paired REVERIE 或 `FOUND/NOT-FOUND`；
- 首次提出 evidence-gathering exploration、annotated coverage 或 coverage-aware stopping；
- `SUPPORTS/ABSTAIN`、confidence threshold、risk--coverage 或 post-hoc calibration 的方法新意；
- RCPS/CRC/LTT、strict union、familywise maximum/union 的数学新意；
- 已撤销的旧 descriptive artifact 是风险保证、unseen-scan guarantee 或 conformal certificate；
- 普通 per-observation bound 在 repeated/adaptive selection 后自动 anytime-valid；
- detector empty output、已看过若干 viewpoint 或 topology exhaustion 已关闭 semantic residual；
- object slot ID、cosine/nearest neighbor 或 feature similarity 已证明 SAME_ENTITY；
- M3-A 已支持 REFUTE、NOT_FOUND、residual、identity、attribute、relation 或 room claims；
- 通过 60 个 M3 adversarial tests 等价于 no-GT semantics、novelty、统计 validity 或科学性能。

### 5.2 可以保留的工程事实

- exact observation/content/model/feature/template identity 能绑定一个真实 DUET signal，但不会自动净化其语义；
- aggregate-only artifact 可由 schema/verifier 强制；当前 runtime GT firewall 因 composite-ID alias 失败；
- caller-reported risk 可以被拒绝，terminal risk 可从 certificate 实际选择的 atoms 重算；
- malformed/domain-shift/NaN/empty/unsupported input 可以 fail closed；
- event-sourced state、revocation、staleness、duplicate reuse 与 independent audit 可以被机械测试。

这些是 M3-A engineering acceptance，不自动是 paper contribution。

### 5.3 条件保留的 scientific claim

仅保留第 2.3 节的 certificate-level adaptive control hypothesis。它的最小不可替代差异是：现有邻居
分别给出 VLN evidence exploration、通用 risk control 或 multi-view association；ProofNav 若能证明一个
**由策略自适应选择的 typed proof set 到 terminal false-FOUND/false-NOT-FOUND event 的端到端有效保证**，
并将 residual/identity completeness 作为 verifier-enforced acceptance condition，才可能形成新的 system/theory
capability。当前没有该结果。

## 6. Collision classification and minimum-change salvage

本轮对“首次提出 false-premise VLN / REVERIE `FOUND/NOT-FOUND`”这一 **broad framing** 构成 confirmed
**problem collision**，并同时构成 claim collision 与 partial method collision。对收窄后的“无 GT runtime
下，何时可以用 machine-checkable certificate 安全接受或拒绝 obligation”则只是 **partial collision**：ROAM
的 evaluator metric 没有完整解决该 guarantee objective，而 ProofNav 也尚未解决它。因此必须停止原 broad
claim，但不停止这个更窄的现实问题。

只保留以下三种最小 repair；任何 repair 成功后都必须重置完整 gate。

### Repair A — certificate-selected adaptive risk

- **改变什么：** 把风险单位从单条 observation score 改为预注册的 episode/scan-familywise terminal event，
  明确 filtration、policy selection、revisit、stopping 与 certificate atom selection；给出 time-uniform 或固定
  horizon 的有效 bound。
- **现实必要性：** agent 会看多个 viewpoint、挑最高分并提前停止；pointwise calibration 在这种选择后可失效。
- **为什么最近邻不能直接覆盖：** anytime-RCPS 已覆盖通用 adaptive calibration；因此只有 typed
  obligation/certificate structure 产生不可约更强的 guarantee、可计算性或更低完整成本时才存活。若能直接
  化约，repair 失败。
- **贡献类型：** theory + system。
- **最便宜 killer：** 两 observation/两 obligation 的 CPU counterexample；比较 pointwise CRC、episode-max
  union 与 anytime-RCPS。若标准方法逐项同构且成本相当，停止 method claim。
- **可复用资产：** M2/M3 event log、risk atoms、certificate recomputation、adversarial tamper tests。

### Repair B — target-conditioned residual coverage

- **改变什么：** 定义 scope 内“真实满足 target template 但 proposal universe 未表示”的 label，并对每 scan
  聚合 missed-residual familywise loss；没有有效 artifact 时 NOT_FOUND 永久 sealed。
- **现实必要性：** proposal miss、occlusion 与未访问区域是 absence reasoning 的必要失败模式。
- **为什么最近邻不能直接覆盖：** conformal OD 可以表达 image-level miss loss，但不直接给 navigation-policy
  下跨 viewpoint、target-template、room-scope 的 terminal residual certificate；若简单换 loss 即完成，则只有
  application，不是方法新意。
- **贡献类型：** benchmark/protocol，只有伴随不可约 terminal guarantee 时才可能是 method。
- **最便宜 killer：** 在极小、穷举标注的 room/viewpoint 子集上统计 target-conditioned proposal miss；若
  5% bound 下 coverage 为零或标签不可可靠构造，停止 NOT_FOUND admission。
- **可复用资产：** M2.1 residual obligations、scope contracts、offline oracle audit。

### Repair C — calibrated false-link identity

- **改变什么：** 用 hard positive/negative cross-view pairs 定义 set-valued association 和 false-link atom；
  component 需满足 injectivity/consistency，无法结算则不链接。
- **现实必要性：** relation/coverage 证书会因错误合并实体而被虚假闭合。
- **为什么最近邻不能直接覆盖：** ConceptGraphs/OVIR-3D 已覆盖 semantic/geometric multi-view association，
  MOT-CUP 已覆盖 uncertainty propagation；只有 terminal certificate false-link guarantee 仍可能不同。
- **贡献类型：** system/theory；nearest-neighbor 本身不是贡献。
- **最便宜 killer：** CPU hard-negative pair audit，比较 cosine、mutual-NN、Hungarian 与 calibrated set matcher。
  若在目标 false-link budget 下没有非零链接率，保持 identity zero-admission。
- **可复用资产：** typed identity obligation、lineage、revocation 与 component audit。

## 7. M3-B cheapest-killer plan

以下顺序按“最便宜地杀死中心 claim”排列，不按最容易写代码排列。P0R 是进入 M3-B 前置修复，不是研究
贡献；未通过时 K0--K5 全部不获得 no-GT 实验权限。

| Priority | Killer | 输入/成本上限 | 通过条件 | 失败动作 |
|---|---|---|---|---|
| P0R | semantic identity + prefix/provenance authority repair | CPU；32 episodes；不训练 | runtime-visible IDs 无 target token/可逆 mapping；offline join mapping 隔离；canonical ordering 不读 evaluator ID；relevant OBSERVATION prefix 被认证或证明无关；identity digests code-derived 或生成链可 attestate；全部 authority 重建 | no-GT claim 与 production M3 authority保持 Stop |
| K0 | split/label eligibility audit | 只读现有 annotation/checkpoint manifests；CPU | 找到与 model fitting、threshold development、test 都隔离的 scan units，或明确新增 label 来源 | 无合法 calibration scans：scientific gate 保持 REVISE，不做统计宣传 |
| K1 | P1 selective risk--coverage | frozen DUET outputs；scan-familywise exact binomial/RCPS/CRC baseline；CPU | 在预注册 `alpha <= .05` 与 confidence 下有非零、可复现 coverage | 转轻量 null-aware target-slot head；重置 calibration gate，不包装 threshold |
| K2 | adaptive/repeat counterexample | 两步/低维 synthetic + recorded trace replay；CPU | 得到合法 episode/familywise 或 anytime bound，且优于/不同于标准 reduction | 若 active anytime-RCPS/LTT 直接覆盖，停止 method claim |
| K3 | proposal-miss residual | 极小 exhaustive room/viewpoint labels；不生成大数据 | target-conditioned missed-residual bound 可用 | NOT_FOUND/residual admission 继续 Stop |
| K4 | cross-view false-link | 小型 hard pair set；CPU feature comparison | 目标 risk 下非零链接率、跨 scan 稳定 | identity admission 继续 Stop |
| K5 | fair closest baseline | ROAM operational spec + standard selective/CRC/union/episode-max；完整成本台账 | ProofNav 留下新的 guarantee/capability 或非平凡完整成本优势 | 若同构，停止 method claim，保留 benchmark diagnosis/engineering assets |

M3-B 必须先做 K0--K2。K3/K4 只有在相应 capability 仍是中心 claim 且标签合法时才允许。ROAM 官方
code/data 在冻结日未公开，因此 K5 可以先做 paper-spec equivalence 与接口级 baseline，不能虚构“已复现
ROAM”。

## 8. Precommitted falsifiers and decisions

三个最可能 falsifier 的本轮状态：

1. **Signal killer：descriptive hit。** 旧 numeric result 因 ended-batch rows 撤销；corrected active-only run
   独立得到 P1 `2/6 = 1/3`，高于 `.05`，所以当前 threshold 没有 usable-risk 结果。它仍不是带 confidence 的
   科学 bound；下一步只允许最小 null-aware score repair 与合法 scan-disjoint calibration killer。
2. **Completeness killer：未解除。** residual 与 identity 无合法 artifact，继续 zero-admission；M3-A 不能
   产生 NOT_FOUND。
3. **Novelty/equivalence killer：部分命中。** VLN-NF/ROAM、selective/CRC/LTT、anytime-RCPS、conformal
   OD 与 multi-view association 覆盖了 broad ingredients。只有 certificate-selected terminal guarantee 仍是
   待杀 hypothesis。

决策冻结：

- **Mechanical engineering PASS：** exact schema/seal/registry/composer/verifier behavior 可作为修复后的回归基础。
- **No-GT authority BLOCKED：** semantic identifier firewall 未通过，且 event-prefix 不受 manifest 认证；P0R
  与全量 reseal 前不允许 production M3 evidence authority，也不把 selected-signal membership 的 terminal
  outcome 称为 exact replay 或 no-GT result。
- **Scientific REVISE：** 当前没有 paper-level surviving result，也没有 full implementation permission。
- **Conditional Continue：** 仅当 K0 合法、K1 在 scan-disjoint setting 获得非零 usable coverage，且 K2
  显示 certificate structure 留下不能被标准 anytime-RCPS/LTT 直接覆盖的新保证/能力时，才可重新申请。
- **Capability Stop：** residual/identity/REFUTE 在合法 labels 与 bounds 缺失时分别停止 admission。
- **Method Stop：** 若 fair constructive mapping 保留相同 information structure、policy set、loss 与 cost，
  则停止 ProofNav method claim，但保留负结果、audit protocol 与工程基础设施。
- **Pivot：** 只有改变母问题、benchmark 或主要贡献类型才构成 Pivot，必须由用户确认。

## 9. Complete-cost ledger for the permitted next step

M3-B 的任何比较都必须计入：

- offline labels 的定义、人工/程序生成、scan aggregation 与审计；
- DUET/checkpoint/features 的既有摊销成本与每 observation forward；
- threshold/head development 与 model-selection data；
- artifact build、confidence calculation、storage 与 registry/authentication；
- 每条 query/evidence/identity/residual obligation、dedup 与 certificate recomputation；
- repeated observations、adaptive stopping、revocation 与 offline oracle audit；
- ROAM/VLM/LLM/FREE baseline 若未来可运行时的 API/model、caption/detection、depth/raycast 与 planning 成本。

当前许可首先限于 P0R pseudonymization、event-prefix authority repair、全量 authority rebuild、primary-source
reading、现有 artifacts 的只读分析、低维 CPU falsification、小型 scan-disjoint label audit 和必要的轻量
correctness tests。当前禁止 GPU、正式 benchmark、完整 paired data generation、大模型/VLM/LLM 服务、M4
planner、test submission，以及依据 val_unseen/test 调 threshold。

## 10. Primary-source ledger (direct URLs)

- VLN-NF / ROAM paper: https://arxiv.org/html/2604.10533v2
- VLN-NF official project: https://vln-nf.github.io/
- SelectiveNet: https://proceedings.mlr.press/v97/geifman19a.html
- Distribution-Free, Risk-Controlling Prediction Sets: https://arxiv.org/abs/2101.02703
- Conformal Risk Control: https://openreview.net/pdf?id=33XGfHLtZg
- Learn then Test: https://doi.org/10.1214/24-AOAS1998
- Time-uniform confidence sequences: https://doi.org/10.1214/20-AOS1991
- Active, anytime-valid RCPS: https://arxiv.org/html/2406.10490
- Conformal Prediction Beyond Exchangeability: https://doi.org/10.1214/23-AOS2276
- Confident Object Detection via CP/CRC: https://proceedings.mlr.press/v204/andeol23a.html
- Conformal Object Detection by Sequential Risk Control: https://arxiv.org/html/2505.24038
- COD/SeqCRC official toolkit: https://github.com/leoandeol/cods
- ConceptGraphs paper/project/code: https://arxiv.org/abs/2309.16650 , https://concept-graphs.github.io/ , https://github.com/concept-graphs/concept-graphs
- OVIR-3D paper/code: https://proceedings.mlr.press/v229/lu23a.html , https://github.com/shiyoung77/OVIR-3D
- MOT-CUP paper/project: https://arxiv.org/html/2303.14346 , https://coperception.github.io/MOT-CUP/
