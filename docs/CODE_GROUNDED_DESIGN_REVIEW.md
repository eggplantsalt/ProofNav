# ProofNav 代码约束下的设计审查

> 审查日期：2026-08-12
>
> 源码基线：VLN-DUET `main@93e8b233164bc079a6db48b8a0a78d123ec8de41`
>
> 审查范围：源码只读复核、方案校准和文档更新；未实现方法、安装依赖、下载数据/权重、使用 GPU、训练或运行正式实验。

本文与[项目总纲](PROJECT_MASTER_PLAN.md)和[新手代码库说明](CODEBASE_BEGINNER_GUIDE.md)配套。相对源码路径均从仓库根目录开始。

## 1. 本轮结论：总体路线是否保留

**总体路线完整保留，并收束为一条更贴近代码的闭环。**

`[源码确认]` DUET 已经提供增量 `GraphMap`、local/global 可执行候选、导航与对象 logits、路径执行和 REVERIE grounding/evaluation 主链。这足以把它保留为导航 proposal 与低层执行基座，依据是：

- `map_nav_src/reverie/agent_obj.py::GMapObjectNavAgent.rollout`；
- `map_nav_src/models/graph_utils.py::GraphMap`；
- `map_nav_src/models/vilmodel.py::GlocalTextPathNavCMT.forward_navigation_per_step`；
- `map_nav_src/reverie/env.py::ReverieObjectNavBatch`。

`[源码确认]` DUET 不提供 ProofNav 所需的证书、谓词证据账本、校准风险或 FOUND/NOT-FOUND 语义终止；其普通 STOP、图耗尽和最大步数目前进入同一个结束分支，结束后还会在全部 visited nodes 中选择最高 STOP 分数对应的节点和对象。因此增加独立语义终止并不是重复已有行为。

`[研究设计]` 校准后的主线是：**DUET 提出真实可去的位置，ProofNav 维护剩余证明义务，轻量重排候选以获取最有价值的证据，并只在独立 verifier 接受 true-path 或 refutation-cover certificate 时输出 FOUND/NOT-FOUND。**

`[工程推断]` 一般 POMDP、belief planning、hitting set、set cover、active hypothesis testing 或 orienteering 可以成为形式化与求解参照，但不改变本项目的固定问题。需要收缩的是“全新表示”式措辞，而不是取消 false-premise VLN、风险受控终止或独立核验。

## 2. DUET 实际可提供与不可提供的信息

### 2.1 到达一个 viewpoint 后的 observation

`[源码确认]` `map_nav_src/reverie/env.py::EnvBatch.getStates` 从 HDF5 取当前 viewpoint 的预计算图像特征，再与 simulator state 配对。`ReverieObjectNavBatch._get_obs` 组装以下内容：

| 内容 | 实际字段/形态 | 代码事实与限制 |
|---|---|---|
| 当前状态 | `scan`、`viewpoint`、`position`、`viewIndex`、`heading`、`elevation` | 当前 simulator 状态；位置为离散 viewpoint 的三维坐标 |
| 36-view panorama | `feature` | 36 个预计算视觉 feature 与相对 angle feature 拼接；不是 raw RGB |
| 当前邻居候选 | `candidate[]` | `viewpointId`、`pointId`、heading/elevation、position、feature、`idx`；只表示当前点局部可导航邻居 |
| candidate direction/angle | `heading`、`elevation`、`pointId` | 方向相对当前基础朝向；代表 view bin 是 36 个离散方向之一 |
| candidate distance | 首次构造时的 `distance` | `make_candidate::_loc_distance` 计算的是 `sqrt(rel_heading²+rel_elevation²)` 的**角距离**，仅用于多个 view 中选代表；缓存 schema 不保存该字段，后续访问不保证存在。它不是 travel distance |
| object feature | `obj_img_fts` | HDF5 中每个 object proposal 的预计算特征切片 |
| object identity | `obj_ids` | proposal/object ID；不是语义类别或“目标成立”真值 |
| object direction | `obj_ang_fts` | 由 HDF5 `directions` 相对当前朝向编码而来 |
| object size/box | `obj_box_fts` | 由 HDF5 `sizes` 生成归一化高、宽、面积；在线 observation 不返回 raw bbox 坐标、raw size 或 detector score |
| local execution interface | `navigableLocations` | simulator 当前状态的局部导航位置；不授权读取整个未探索图 |
| instruction | `instruction`、`instr_encoding` | 自由文本及 token 编码 |
| 混入同一 dict 的 GT | `gt_path`、`gt_end_vps`、`gt_obj_id`、GT-derived `distance` | 供原训练/评测方便；ProofNav 在线层必须主动剔除 |

对象接口依据是 `map_nav_src/reverie/data_utils.py::ObjectFeatureDB.load_feature/get_object_feature`。该类读取 `directions`、`sizes`、`obj_ids`，只向环境返回派生 angle/box feature 与 ID。`BBoxes.json` 经 `load_obj2vps` 得到对象可见 viewpoint 映射，属于 benchmark truth，不是 object proposal 在线 metadata。

### 2.2 增量图状态

`[源码确认]` `map_nav_src/models/graph_utils.py::GraphMap.update_graph` 每步加入当前 viewpoint 及其当前可见相邻 candidates，并只把当前 viewpoint 标成 visited。可用状态包括：

- `node_positions`：目前发现过的当前/邻接节点位置；
- `FloydGraph._visited`：实际被 `update_graph` 当作当前节点更新过的集合；
- 已发现边及其 Euclidean edge length；
- 已发现图上的 shortest distance/path；
- `node_embeds`、`node_step_ids`、`node_stop_scores`。

`[源码确认]` `GMapObjectNavAgent._nav_gmap_variable` 从上述状态组成 visited/unvisited 列表，并用 unvisited 为空计算 `no_vp_left`。它不是从 `env.graphs` 拷贝完整 connectivity。

`[源码确认]` 未访问节点的 embedding 在 `rollout` 中由当前位置 panorama 的 candidate token 写入：`gmap.update_node_embed(i_cand_vp, pano_embeds[i, j])`。这只是“从当前位置看向该邻居”的 proposal 表征，不是目标节点自己的 36-view/object observation。

### 2.3 模型 score 与动作

`[源码确认]` `GlocalTextPathNavCMT.forward_navigation_per_step` 输出：

- `global_logits`：增量 GraphMap action scores，visited/padding 被 mask；
- `local_logits`：当前 panorama 的可导航 token scores；
- `fused_logits`：把 local stop/candidate/backward evidence 加入 global scores；
- `obj_logits`：当前 panorama object tokens 的 grounding scores；
- global/local embeddings 和 dynamic fusion weight 的内部结果。

这些 tensor 位于 `rollout` 内，不是 `_get_obs` 的公共字段，但 ProofNav 可在动作选择缝隙合法读取。当前 detailed output 只保存每个 visited node 的 `stop_prob`、`obj_ids` 和 `obj_logits`；虽然 `GraphMap` 声明了 `node_nav_scores`，本条 REVERIE rollout 没有填充它，不能假设现成日志已经保留每步 navigation logits。

`[源码确认]` action interface 依 fusion 模式不同：

- `local`：`vp_cand_vpids`，即当前位置相邻候选；
- `global`、`avg`、`dynamic`：`gmap_vpids`，即增量 GraphMap 中的未访问候选；
- index 0：普通 `[stop]`。

`[源码确认]` `make_equiv_action` 对远端 GraphMap action 调用已发现图的 `path`，把路径追加到 trajectory，然后直接在 endpoint 调用 simulator `newEpisode`。随后只在 endpoint 调用 `_get_obs`。因此中间路径节点会贡献 travel path/cost，却没有在当前实现中产生证据观察。

### 2.4 当前主路径不能提供或不能可靠提供的信息

`[源码确认]` 当前不能直接得到：

- raw RGB：`EnvBatch` 设置 `setRenderingEnabled(False)`，`getStates` 明确说明 RGB 为空；
- depth、dense geometry、mesh/表面 coverage 或 semantic segmentation；
- 真实 occlusion、可见表面比例和否定某对象存在所需的几何 visibility model；
- 任意连续相机位姿或主动 zoom/query action；
- detector 原始置信度、类别概率、proposal NMS 记录或现成 calibration score；
- 未探索区域的图像/对象真值；
- REVERIE 的结构化 attribute、relation、room/anchor predicate label。

`[工程推断]` DUET navigation/object logits 可以作为 proposal 与 grounding 信号，但不能未经验证当作 sensor likelihood 或风险上界。由同一预训练 feature、相邻 view 和多步重复产生的 score 也不是独立样本。

### 2.5 现有 annotation 对各类 predicate 的支持上限

| Predicate | REVERIE 当前支持 | 在线可用性 | ProofNav 第一阶段结论 |
|---|---|---|---|
| entity/object identity | annotation 有目标 `objId`；`BBoxes.json` 可导出 GT object-to-viewpoint；在线 observation 有 proposal `obj_ids` | 目标 `objId` 和可见 viewpoint 映射只属训练/评测真值；在线可用 proposal ID 和 grounding logits | 能建立 entity candidate/grounding 接口，但不能把 ID 相等或 `obj2vps` 偷渡为在线证据 |
| attribute | 属性可能出现在自由文本 instruction；loader 无结构化 attribute label | 只有文本和隐式视觉 feature，没有属性 score/truth | 需要 paired schema 与 perception adapter；否则保持 unresolved |
| relation | 关系可能出现在自由文本 instruction；loader 无结构化 relation/anchor label | 只有文本、object proposals 和粗角度/size 派生量；没有关系真值或 3D 几何 | 需要显式 relation schema、候选绑定和可校准 adapter；不能从共现直接证明 |
| room/region/anchor | REVERIE loader 无 room/region ID、边界或 room connectivity contract | 当前点坐标和局部 candidates 不等于 room label | 第一阶段 scope 采用局部 candidate oracle 定义的离散连通域；room/anchor 只在未来公开 schema 下启用 |

`[源码确认]` `map_nav_src/soon/data_utils.py::construct_instrs` 能从 SOON instruction 选择 `full/attr/relation/region/nb_region` 文本子字段，但这是 SOON 特化数据接口，不构成 REVERIE 的结构化 predicate truth，也不改变第一阶段 benchmark 固定范围。

## 3. Agent-visible、simulator execution 与 evaluator-only truth 的边界

### 3.1 边界表

| 信息 | Agent-visible | Simulator execution | Offline evaluator/auditor | 进入在线 planner 的规则 |
|---|---:|---:|---:|---|
| 已到达点的 panorama/object feature | 是 | 是 | 可记录 | 允许 |
| 当前局部 candidates、方向、位置 | 是 | 是 | 可记录 | 允许 |
| 逐步发现的 GraphMap | 是 | 执行引用 | 可记录 | 允许 |
| global/local/fused/object logits | 是，模型内部 | 否 | 可记录 | 允许，但必须标记为未校准 task score |
| 当前局部 `navigableLocations` | 是 | 是 | 可记录 | 允许局部使用；不可展开成全图 oracle |
| MatterSim 内部完整导航图 | 否 | 是 | 可用于复现/评测 | 禁止 |
| 环境 `graphs`、`shortest_paths/distances` 全对表 | 否 | 执行/训练环境持有 | 是 | 禁止；路线成本用增量 GraphMap |
| `gt_path`、`gt_end_vps`、`gt_obj_id` | 否 | 训练 teacher 可用 | 是 | 推理/证书/在线 verifier 禁止 |
| `obj2vps` / `BBoxes.json` 可见性真值 | 否 | 环境初始化持有 | 是 | 禁止 |
| paired false-premise label、结构化 GT 谓词 | 否 | 否 | 是 | 禁止 |
| scope contract 中公开给 agent 的域 | 是 | 可校验 | 是 | 仅允许合同明确公开的部分 |

### 3.2 为什么当前 observation dict 特别危险

`[源码确认]` `ReverieObjectNavBatch._get_obs` 把 agent signal 与 `gt_path`、`gt_end_vps`、`gt_obj_id`、GT-derived `distance` 放在一个普通 Python dict 中。原训练的 `_teacher_action` 和 `_teacher_object` 会用这些字段，原 evaluator 则用 `obj2vps` 和完整 shortest distances。

`[工程推断]` 如果 ProofNav 直接把整个 `ob` 交给 planner、ledger 或 online verifier，即使没有显式调用 evaluator，也已构成 leakage。最小安全方案是新建 typed/白名单 `AgentObservation`，只从允许字段复制；禁止保存对原 dict 或 env 的引用。

### 3.3 Independent verifier 的两种职责

`[研究设计]` **Online Legality Verifier** 可以访问：agent-visible event log、公开 scope contract、证书、风险/校准 artifact、动作与资源日志。它验证：

- evidence event 是否确实在决策前产生；
- event 是否在 scope 内、是否来自允许接口；
- FOUND 的每个必要谓词是否有合法支持；
- NOT-FOUND 是否覆盖全部 scope hypothesis 并结算 unresolved/frontier；
- 风险预算和依赖组合是否满足声明。

它不得访问 GT object、完整 scene graph、完整 connectivity、`obj2vps` 或 paired label。被拒绝时返回 `remaining_obligations`，形成闭环门控。

`[研究设计]` **Offline Benchmark Auditor** 可以访问 evaluator truth，验证最终决定、路径、证书 scope/coverage 声明与 benchmark 真值是否一致，并计算任务和证书指标。它验证的是“对 benchmark 真值是否正确”，而不是把真值反馈给 agent 来证明“当时决定合法”。

两者必须使用不同输入 schema、独立日志字段和无反馈边界。`[待实验验证]` 后续用故意注入 `gt_obj_id`、`obj2vps` 或全图 shortest distance 的负向单测确认隔离。

## 4. Source-to-design matrix

| ProofNav 功能 | DUET 真实来源/接入点 | 当前可用信息 | 缺失信息 | 最小改动 | 是否需要训练 |
|---|---|---|---|---|---|
| instruction compiler | `map_nav_src/reverie/data_utils.py::construct_instrs`；`map_nav_src/reverie/agent_obj.py::_language_variable` | instruction text、token IDs、`instr_id` | REVERIE 无结构化 entity/attribute/relation/room schema；无 parser uncertainty | 新建版本化 compiler，输出 predicate graph 与 unresolved parse；先允许人工/oracle schema | 第一版否；自动 compiler 后续可能需要 |
| navigation state | `map_nav_src/models/graph_utils.py::GraphMap`；`map_nav_src/reverie/agent_obj.py::_nav_gmap_variable/_nav_vp_variable` | 当前点、增量 nodes/edges、visited、unvisited、发现图距离、local/global candidate IDs | 完整环境不可在线用；远端节点未观察 | typed `NavigationState` 只复制增量图和合法 candidates | 否 |
| evidence state | `map_nav_src/reverie/env.py::_get_obs`；`map_nav_src/reverie/agent_obj.py::rollout` 的模型输出 | 到达点 36-view/object feature、ID、角度/size 派生量、task logits | 原始 detector score、结构化谓词、校准风险、不可变历史 | `ObservationAdapter` 发 event；`EvidenceLedger` 引用 event IDs | 逻辑层否；真实 predicate adapter 可能需要 |
| candidate grounding | `map_nav_src/models/vilmodel.py::forward_navigation_per_step` 的 `obj_logits`；`map_nav_src/reverie/env.py::_get_obs` 的 `obj_ids` | 当前 viewpoint 的 object proposal IDs 和 grounding logits | 类别/属性/关系 truth；原始置信度 | 作为 candidate proposal，不直接写“已支持”；经 perception/calibration adapter 后入账 | 冻结基线否；校准/新感知待定 |
| discrete proof unit | `map_nav_src/reverie/env.py::_get_obs` 的 36 views/object slots | `(viewpoint, view_bin)` 和 `(viewpoint, obj_id/slot)` 可追踪 | 连续 surface、depth、visibility completeness | 用到达事件定义 DEU；明确有限接口语义 | 否 |
| unresolved/frontier witness | `GraphMap.node_positions` + `graph.visited`；`_nav_gmap_variable::no_vp_left` | 已发现未访问节点；已访问点上未决 ledger records | 图外未知域、room boundary、感知漏检真值 | 分开 `graph_frontier` 与 `evidence_unresolved`；由 scope contract 结算 | 否 |
| FOUND/NOT-FOUND decision | `rollout` 中 `nav_outs` 后、`a_t_stop` 前 | DUET STOP score、当前对象 proposal、合法 candidates | 两类 semantic action、提议/接受分离、终止原因 | 外部 controller 或最小 rollout hook：CONTINUE/PROPOSE_FOUND/PROPOSE_NOT_FOUND | 第一版否 |
| certificate builder | 当前无；可引用 trajectory/details | 事件、路径、score、对象 ID、义务状态 | true path/refutation cover schema、hash、版本、风险组合 | 新建纯数据 builder；不读 env/GT | 否 |
| independent verifier | 当前 `map_nav_src/reverie/env.py::ReverieObjectNavBatch.eval_metrics` 只是任务 evaluator | 原 evaluator 可作 offline truth 来源 | 在线合法性 verifier、拒绝反馈、无泄漏边界 | 新建 online/offline 两套 verifier；输入 schema 隔离 | 否 |
| proof-oriented candidate selection | `map_nav_src/reverie/agent_obj.py::rollout` 中 `nav_logits/nav_vpids`；`map_nav_src/models/graph_utils.py::GraphMap.graph.distance` | global/local/fused proposals、mask、发现图 route cost | 目标点真实 evidence gain、query cost、risk reduction model | 在原 argmax 前加可开关 re-ranker；只重排合法 action | 第一版否；学习型版本待结果 |
| risk/cost ledger | `map_nav_src/reverie/agent_obj.py::make_equiv_action`；`map_nav_src/reverie/env.py::_eval_item` | high-level step、展开 path、metric path length、observation endpoint | detector calibration、query compute、依赖关系、离线成本 | 分离 travel/observation/query/compute；记录 calibration ref/dependency group | 账本否；校准可能需要 |
| evaluation/prediction schema | `map_nav_src/reverie/agent_base.py::BaseAgent.get_results`；`map_nav_src/reverie/env.py::ReverieObjectNavBatch.eval_metrics` | `instr_id`、trajectory、`pred_objid`、可选 stop/object details；原 SR/SPL/RGS/RGSPL | semantic decision、certificate、verifier/risk/cost、paired metrics | 外层 adapter 扩 schema；保持原 evaluator 兼容，新增离线 auditor | 否 |

`[工程推断]` 最自然的接法不是立即重训大模型，而是新建独立 ProofNav 数据/控制层，在 `rollout` 的 score—action 接缝做最小、可开关的集成。具体文件名和补丁直到用户授权实现阶段再冻结。

## 5. 原方案中实际不适配的部分

| 不适配 | 源码证据 | 影响层 |
|---|---|---|
| 连续 `proof cell` 假设深度、dense geometry 和 visibility | rendering 关闭；`getStates` 只读 HDF5 feature；无 depth/mesh/segmentation 接口 | 表示/接口 |
| 把 candidate 节点当成已观察空间 | unvisited embed 来自当前位置 candidate token；只在 endpoint 再 `_get_obs` | 证书正确性 |
| 用 `candidate['distance']` 当导航成本 | 该值是角距离且缓存后字段消失 | 算法/运行时 |
| 用 `no_vp_left` 或普通 STOP 代表 NOT-FOUND | rollout 把 STOP、无未访问点、步数上限合并；无谓词检查 | 终止语义 |
| 认为 global action 沿路逐点取证 | `make_equiv_action` 追加路径后直接 `newEpisode` 到 endpoint | 证据/成本 |
| 从现有 logits 直接构造 calibrated predicate risk | 当前只有 task navigation/object logits，无 detector raw confidence/calibration metadata | 感知/保证 |
| 默认 REVERIE 已有 attribute/relation/room truth | REVERIE loader 只输出自由文本/token/path/objId；结构字段不存在 | 数据 |
| 让 verifier 直接读取环境完整 truth | env 同时持有 GT、`obj2vps`、完整图和 shortest paths | 信息泄漏 |
| 把 DUET STOP 与 semantic terminal 共用一个 index | index 0 是导航 `[stop]`，结束后还会跨 visited nodes 重新选 stop/object | 接口/解释性 |
| 把 dual-scale 直接命名为两层证明控制 | local 是 panorama navigation/object scoring；global 是增量图 scoring；无 room proof action | claim 边界 |

## 6. 每个不适配项的最小修复

1. **连续 proof cell → Discrete Evidence Unit。** `[研究设计]` 第一阶段只承诺 viewpoint-view/object-slot 事件是否被合法观察，不声称表面几何全覆盖。连续 visibility 作为未来 perception/geometry adapter，非第一阶段前置。

2. **候选可见 → proposal/frontier。** `[研究设计]` 只有 agent 到达 viewpoint 并触发 `_get_obs` 才产生 evidence event；当前位置的 candidate token 只能估计将来收益。

3. **不稳定角距离 → GraphMap route cost。** `[工程推断]` 所有在线导航成本取 `GraphMap.graph.distance/path`；离线评测仍由原 evaluator 计算真实 trajectory length。禁止依赖 `candidate['distance']`。

4. **图耗尽/STOP → 分离 termination causes。** `[研究设计]` 保存 `duet_stop`、`no_frontier`、`budget`、`verifier_accept` 等原因。只有后者能形成已验证语义答案；其他原因可以结束资源执行，但证书状态必须如实标为未接受。

5. **远端执行 → 双账本。** `[研究设计]` 展开路径每条边计 travel，中间点不计 observation；endpoint `_get_obs` 生成一次证据事件。以后若逐节点取证，需要单独 executor 模式和回归测试。

6. **task logits → proposal score + perception adapter。** `[研究设计]` 当前 logits 只用于候选排序和未校准 grounding。M2 用 oracle evidence 验证证书逻辑；M3 新增能输出 predicate score、版本、适用域、依赖组的 adapter，再做 held-out calibration。

7. **缺失结构谓词 → 版本化数据合同。** `[研究设计]` REVERIE 正例第一阶段可做 object entity/grounding 主链；attribute/relation/room/anchor 由 paired extension 的人工审计 schema 或 VLN-NF 官方 artifact 提供。SOON loader 虽能选择 `full/attr/relation/region/nb_region` 文本子字段，但它是另一任务接口，不能充当 REVERIE 结构真值。

8. **verifier truth 混用 → 双 verifier。** `[研究设计]` online verifier 只读 allowlisted event；offline auditor 才读 `obj2vps`、完整 connectivity 和 paired GT。负向测试向 online 输入注入 GT，必须失败。

9. **STOP 共用 → 外部语义 controller。** `[工程推断]` 在 `nav_outs` 后、原动作选择前接 CONTINUE/FOUND/NOT-FOUND proposer 和 certificate gate；保留 DUET STOP score 为特征与 baseline，不直接修改三个模型 head 的语义。

10. **dual-scale 过度包装 → 只作为 proposal features。** `[研究设计]` re-ranker 可同时读取 global/local/fused signals，但是否存在“全局/局部义务切换”只作为消融问题，不预注册为独立机制。

## 7. 由源码导出的增强候选

### 候选 A：Proof-obligation re-ranking

`[源码确认]` 每步已经同时存在 navigation logits、合法 action IDs、mask 和增量图距离；接入点就在 `rollout` 中 `nav_outs` 与 `a_t` 之间。

`[研究设计]` 冻结 DUET 作为 proposal generator，计算：

```text
utility(v) = DUET_relevance(v)
           + expected_obligation_reduction(v)
           + expected_risk_reduction(v)
           - travel_cost(v)
           - observation/query_cost(v)
```

预计证据收益是预测量而非目标节点真值。`[待实验验证]` 用 action legality、排序可解释性、义务完成率和 matched-risk 完整成本验证。

### 候选 B：Verifier-gated terminal

`[源码确认]` 当前终止路径没有 FOUND/NOT-FOUND，也不检验证书；普通 STOP、图耗尽和预算共享结束分支。

`[研究设计]` controller 提议语义决定，builder 构证书，online verifier 接受或拒绝；拒绝时义务回到 re-ranker。它与阈值停止的区别是终止条件由可机检 schema 定义，与事后自然语言解释的区别是拒绝会改变后续动作。

### 候选 C：Dual-scale proof control

`[源码确认]` DUET 的 global/local/fused scores 天然提供两种空间尺度信号，但 local 没有独立的“观察/查询”动作，也没有 room label；global 未访问节点仍只是当前发现图。

`[工程推断]` 可以把这些 signals 输入候选 A，但当前证据不足以独立定义新 proof controller。若以后引入 room/region contract 和局部 query action，再重新评估。

### 候选 D：Scope contract 与双 verifier 边界

`[源码确认]` 完整 graph、GT fields 和在线 signals 共存于环境对象/observation，错误接线非常容易泄漏。

`[研究设计]` scope contract 声明 NOT-FOUND 的离散域、接口版本和风险模型；online/offline verifier 分工。这是证书有效性的必要机制，也能形成具体 leakage/validity 测试。

## 8. 最终采纳的增强点（最多三个）

1. **Proof-obligation re-ranking：采纳。** 它利用现有真实候选和 score 接缝，以小改动把主动证据采集落实成算法；第一版无需训练大 policy。
2. **Verifier-gated terminal：采纳。** 它直接修复当前终止原因混合和“STOP 没有证明含义”的接口缺口，并让 verifier 进入闭环。
3. **Scope contract + dual verifier boundary：采纳。** 它限定 NOT-FOUND 的语义并阻断 evaluator truth 泄漏；作为 verifier 的完整性组件，不另行包装为第三个 headline 方法。

`[研究设计]` 三者串成同一条链：scope/obligation state → candidate re-ranking → certificate → verifier gate，而不是三个松散系统。

## 9. 明确拒绝或延后的额外模块

- **不采纳独立的 dual-scale proof control。** 当前 global/local 是 DUET 已有导航结构，没有 room-level proof action 或 local sensing action。把它单独命名为新机制容易只是重包装；其 logits 仅作为 re-ranker 输入并做后续消融。
- **不在第一阶段建立连续 3D/遮挡 proof cells。** 缺少 RGB、depth、dense geometry 和 visibility model；现在实现只能制造不可核查假设。
- **不立即训练大型新 decision head 或端到端 policy。** 已有 logits/action seam 足以先验证轻量方法；大模型会把证书逻辑、感知误差和规划收益纠缠在一起，并引入当前未授权成本。
- **不把自然语言解释当 certificate。** 证书需要 event IDs、scope、predicate status、risk 和 machine-checkable cover；语言解释只能附加展示。
- **不把现有 object logits 当 detector confidence。** 源码没有暴露生成这些 HDF5 proposals 的原始 detector score或校准元数据。真实风险校准延后到明确的 perception adapter。

## 10. 校准后的中心方法故事

`[研究设计]` 现有 DUET 根据指令相关性和在线拓扑选择去哪里，并以普通 STOP/object argmax 完成 REVERIE。它擅长产生导航/grounding proposals，但 STOP、最大步数、frontier 耗尽或某个高 object score 都不能说明 false-premise 条件下 FOUND/NOT-FOUND 为什么成立。

ProofNav 不替换这一基座。它先通过白名单 adapter 把真实到达点的 panorama/object 信号写成离散 evidence events，再把 instruction predicates、候选实体、增量图 frontier 和感知不确定性组织为剩余 proof obligations。DUET 提供 local/global 可执行候选；轻量优化层按预计义务完成度、风险下降和完整成本重排。系统提出 FOUND 时构造 true path，提出 NOT-FOUND 时构造 refutation cover 并结算 frontier/unresolved witness。online verifier 只凭当时合法信息决定是否允许终止；offline auditor 独立用 benchmark truth 评价结论。

`[待实验验证]` 研究问题不是这种状态能否被一般框架表达，而是该特定闭环能否在不泄漏真值、匹配实际风险并完整计费时，比普通 STOP/threshold/budget/frontier 产生更可靠且更经济的终止。

## 11. 第一阶段最小可实现架构

### 11.1 必需模块

1. `AgentObservation` allowlist：从原 observation 复制在线合法字段，拒绝 GT/env 引用。
2. `ScopeContract`：以内涵式规则固定离散搜索域（如从起点经完整局部 candidate 接口可达的连通分量）、可达规则、观测/谓词/calibration 版本和资源限制；不向 agent 暴露完整 connectivity 表。
3. `EvidenceEvent` + `EvidenceLedger`：只为真实 `_get_obs` endpoint 生成事件，区分 task score 与 calibrated score。
4. `ObligationState`：实体—谓词状态、graph frontier、evidence unresolved、risk/cost ledger。
5. `ProofReranker`：读取 DUET proposal 与合法候选，输出下一 endpoint 和分解效用。
6. `TerminalProposer` + `CertificateBuilder`：分别提出 CONTINUE/FOUND/NOT-FOUND，并产生 true path/refutation cover。
7. `OnlineVerifier`：接受或返回 remaining obligations。
8. `OfflineAuditor` + schema adapter：使用 evaluator truth 计算任务、证书和泄漏指标。

### 11.2 第一阶段明确支持

`[研究设计]` 可先支持：离散 viewpoint scope；实际访问事件；object candidate/ID；DUET proposal score；oracle predicate evidence 下的证书/verifier correctness；无训练 re-ranking；路径/观察分账；正/负 decision schema。

### 11.3 必须延后或有条件进入

`[工程推断]` 以下内容需要 M3 或更晚：自动可靠 instruction decomposition；真实 attribute/relation/room/anchor evidence；raw detector score 或新视觉 adapter；相关风险校准；学习型 re-ranker；连续几何/遮挡/表面 coverage；途中逐节点主动观察。

延后不等于删除其语义：无法可靠判断的 predicate 必须保持 unresolved，不能用 GT、默认值或 DUET logits偷偷关闭。

## 12. 下一阶段可以直接执行的工作

用户下一步明确授权后，从总纲 M0 开始，而不是直接实现 ProofNav：

1. 核对官方 REVERIE 数据、HDF5 features、checkpoint、MatterSim 与环境版本，记录来源和 hash；需要下载、安装或 GPU 前单独报告。
2. 原封不动复现 DUET REVERIE evaluation，保存 config、命令、日志和指标。
3. 在一个 episode 上记录不含 GT 的 observation allowlist、local/global action IDs、nav/object logits、GraphMap visited/unvisited、远端路径展开、endpoint observation 和不同 termination causes。
4. 比较首次/缓存 candidate schema，确认不依赖 `candidate['distance']`；核对 local/global fusion 下 action mapping。
5. 将 trace 与原 evaluator 输出对齐，形成 M1 typed contract 的具体字段表；仍不实现 planner、certificate 或 verifier。

`[待实验验证]` M0 的成功标准是原 baseline 可复现和代码合同可观测，不是 ProofNav 指标改善。M0 完成后，再按 M1 → M2 → M3 → M4 顺序实现接口、oracle 证书/verifier、真实感知校准和闭环 re-ranking。
