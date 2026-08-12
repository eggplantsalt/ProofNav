# ProofNav M1 代码驱动微调记录

> 日期：2026-08-12（UTC）
>
> 原则：只记录由冻结 DUET/M0 接口事实触发的最小调整；不改变任务、benchmark、
> backbone、三项核心机制或 M0 结果。

## C1：统一动作索引改为 branch-aware action ID

- 原设计：prediction/action 合同只概括保存动作或统一索引。
- 代码事实：`local` 使用 `vp_cand_vpids`；`global/avg/dynamic` 使用 `gmap_vpids`；M0
  实跑确认三种 mapping，index 0 都是 STOP/null，但其余 index 的 ID 空间不同。
- 调整原因：相同 raw index 在不同分支不是同一动作；证书、成本和未来 reranker 不能只
  记录 index。
- 调整后：同时保存 local/global/fused 的 ID/mask，显式保存 selected branch/index/ID，
  并校验映射和 mask。
- 影响：收紧接口与后续 action legality 实验；不改变论文中心 claim、DUET 行为或 M0 数值。

## C2：evidence 从“节点/候选”收紧到 observation-event provenance

- 原设计：离散 evidence unit 以 viewpoint-view/object-slot 表示，但“何时算观察”还需要落到
  runtime 事件。
- 代码事实：未访问 candidate embedding 来自当前点；global 多跳的中间节点只加入轨迹，
  endpoint 后才 `_get_obs`；M0 捕获了真实 4-hop suffix。
- 调整原因：候选或 travel-only node 若入账，会虚增 coverage 并制造无依据证书。
- 调整后：evidence source 只能是 `observation`，必须逐项匹配 event ID/sequence/step/scan/
  viewpoint/view index；proposal 与 travel-only 均拒绝。
- 影响：强化 scope + verifier 的合法性边界；未来成本必须分 travel 与 observation；不新增
  独立研究方向。

## C3：candidate distance 从 M1 observation schema 删除

- 原设计：可能在 candidate/action 表示中携带 distance 供成本使用。
- 代码事实：该字段是代表 view 选择用角距离，cache 后消失；M0 audit 确认 agent 未读取。
- 调整原因：字段不稳定且不是 travel cost。
- 调整后：observation candidate 不允许 distance；cost ledger 保留 travel distance，M4 只能
  从已发现 GraphMap path/distance 接线。
- 影响：收紧成本定义；不影响 M0 或研究主线。

## C4：execution termination 与 semantic verdict 采用正交字段

- 原设计：已有 `semantic_decision/decision_status/termination_cause` 草案。
- 代码事实：原 rollout 将 STOP、already-ended、no frontier、max step 合并为 `None`，结束后
  还可能回到历史最高 STOP 节点。
- 调整原因：执行停止不能推导 NOT_FOUND，普通 DUET STOP 也不能绕过 verifier gate。
- 调整后：保留独立 termination cause 和 DUET flags；只有 verifier_accept 可伴随 VERIFIED
  FOUND/NOT_FOUND，其余只能是 UNRESOLVED。
- 影响：明确 future controller 的接线义务；不修改原 STOP/evaluator。

## C5：online allowlist 从 denylist 升级为 denylist + exact v1 fields

- 原设计：主要列出禁止进入 online 的 GT 字段。
- 代码事实：原 `_get_obs` 是混合普通 dict，未来模块若接受任意扩展键，真值可以通过别名或
  wrapper 重新进入。
- 调整原因：仅扫描已知 `gt_*` 名称不能构成严格 allowlist。
- 调整后：递归拒绝已知 evaluator-only 字段，并对 observation/action/evidence/scope/
  obligation/result 及 paired agent-visible v1 对象拒绝未知字段；版本升级必须显式处理。
- 影响：增强 dual-verifier boundary；可能要求未来 schema 变更升版，但不改变 claim。

## C6：legacy DUET 与 ProofNav 输出不做隐式互转

- 原设计：扩展 prediction 并保持原 evaluator 兼容。
- 代码事实：`BaseAgent.get_results` 固定输出 `instr_id/trajectory/pred_objid`，原 evaluator 只理解
  这些字段与 REVERIE truth。
- 调整原因：给 legacy output 自动填充 NOT_FOUND/UNRESOLVED 会伪造语义；直接修改原 evaluator
  会破坏 M0 baseline。
- 调整后：独立 evaluator 识别 `duet_legacy`，只做结构兼容；ProofNav versioned output 走新
  evaluator；原指标继续走冻结 evaluator。
- 影响：保持 M0 可复现与结果解释边界；无全局路线变化。

## 总结

全局总纲不需要改变。六项调整都是已有三个核心机制的工程收紧：C1/C3 服务未来
proof-obligation re-ranking，C2/C5 服务 scope + dual verifier，C4/C6 服务
verifier-gated terminal 与独立评测。没有发现需要换题、换 backbone、换 benchmark 或新增
第四项主贡献的代码障碍。

本轮没有重新进行近邻检索或 novelty verdict，因为 M1 的授权目标是冻结已选路线的工程
合同。普通 typed schema、data validation、set/refutation cover 表示、离线 evaluator 和
action canonicalization 都属于共同工程部分，不主张其自身新颖。锁定但仍待 M2–M5 验证的
差异仍是：false-premise VLN 中 scope-bounded 正/反证书、风险受控 verifier gate 和证明义务
驱动的证据采集闭环。在当前代码接缝中未发现新的直接雷同或致命 collision；这不构成新的
文献新颖性证明。
