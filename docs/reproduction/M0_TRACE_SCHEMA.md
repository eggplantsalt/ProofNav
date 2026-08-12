# M0 无 GT 泄漏运行时 Trace Schema

> 状态：**已由真实 DUET episode 验证（dynamic/local/global；2026-08-12 UTC）。**
>
> 本文只定义 M0 tracing 合同，不创建 EvidenceLedger、certificate、verifier、perception adapter 或 planner。

## 1. 目的与不变量

Trace 是只读旁路，默认关闭。打开时只能复制已经用于原 DUET 决策或执行的信息，不能改变 tensor、mask、随机数调用、action selection、STOP、trajectory 或 evaluator。

必须满足：

1. tracing on/off 在同一 commit、checkpoint、input、seed、fusion 和 batch 下的原始 `trajectory`、`pred_objid` 完全一致；
2. 每次 `observation` event 对应一次真实的 `env.reset/_get_obs` 返回；
3. 远端 action 的中间 path nodes 标为 `travel_only`，只有 endpoint 产生下一条 observation event；
4. trace 不保存 evaluator-only truth、完整环境图或其可逆派生物；
5. trace 中的 logits 标为未校准 DUET task scores，不是感知概率或 ProofNav risk。

## 2. Observation 白名单

允许记录值或 schema：

| 字段 | Trace 内容 |
|---|---|
| `instr_id` | episode ID |
| `scan` | agent 已知 scene ID |
| `viewpoint` | 当前实际观察 viewpoint |
| `viewIndex`、`heading`、`elevation`、`position` | 当前位姿 |
| `feature` | 默认只记 `shape`、`dtype`；调试需要时可在单 episode 记录 checksum，不写全 tensor |
| `candidate` | 每项 `viewpointId`、`pointId`、heading/elevation、position、`idx`、feature shape/dtype；额外记录原始 key set |
| `obj_img_fts`、`obj_ang_fts`、`obj_box_fts` | shape/dtype；不默认写 feature value |
| `obj_ids` | 当前 object proposal IDs |
| `instruction`、`instr_encoding` | instruction text 可选；token 记 length/shape，避免无必要复制 |
| 当前局部导航信息 | 只通过 sanitized candidate IDs 表示，不序列化 simulator object |

候选 schema 特别记录：

```json
{
  "candidate_keys": ["..."],
  "candidate_distance_present": true,
  "candidate_distance_semantics": "angular_representative_selection_only"
}
```

`candidate_distance_present` 用于验证首次构造与缓存重建的 schema 差异。任何运行逻辑不得依赖该字段。

## 3. 严格 denylist

以下内容不得进入 trace：

- `gt_path`、`gt_end_vps`、`gt_obj_id`；
- observation 的 GT-derived `distance`；
- `env.obj2vps` 或 `BBoxes.json` 的可见性映射；
- `env.graphs`、`shortest_paths`、`shortest_distances` 或完整 connectivity；
- paired false-premise label、结构化 GT predicate 或目标 room/anchor truth；
- 能从上述内容直接重建目标或全图的派生字段。

运行后必须递归扫描 JSON keys 和 schema names，并检查 trace serializer 没有持有原 observation dict 或 env 引用。

## 4. 单 episode JSONL 结构

每行是一个 event。公共头：

```json
{
  "trace_schema_version": "m0.runtime.v1",
  "run_id": "...",
  "episode_index": 0,
  "instr_id": "...",
  "step": 0,
  "event_type": "observation | model_scores | action | execution | termination | prediction",
  "monotonic_time_ns": 0
}
```

### 4.1 `observation`

```json
{
  "event_type": "observation",
  "observation_index": 0,
  "scan": "...",
  "viewpoint": "...",
  "view_index": 0,
  "pose": {"heading": 0.0, "elevation": 0.0, "position": [0.0, 0.0, 0.0]},
  "field_schema": {
    "feature": {"shape": [36, 772], "dtype": "float32"},
    "obj_img_fts": {"shape": [0, 768], "dtype": "float32"}
  },
  "candidate_ids": [],
  "candidate_schema": [],
  "object_proposal_ids": []
}
```

Shape 示例仅表示字段位置；真实 shape 必须由运行时写入，不能把示例当实测结果。

### 4.2 `model_scores`

```json
{
  "event_type": "model_scores",
  "fusion_mode": "dynamic",
  "local": {"action_ids": [null], "valid_mask": [true], "logits": [0.0]},
  "global": {"action_ids": [null], "valid_mask": [true], "visited_mask": [false], "logits": [0.0]},
  "fused": {"action_ids": [null], "valid_mask": [true], "logits": [0.0]},
  "objects": {"proposal_ids": [], "valid_mask": [], "logits": []},
  "graph_map": {"visited_viewpoints": [], "unvisited_viewpoints": []}
}
```

即使当前 `fusion_mode` 只采用一组 logits，三个分支都按 `nav_outs` 原值旁路记录。必须把 index 0 显式映射为 `null/[stop]`，并证明 local action IDs 来自 `vp_cand_vpids`，global/dynamic action IDs 来自 `gmap_vpids`。

### 4.3 `action` 与 `execution`

```json
{
  "event_type": "action",
  "selected_branch": "fused",
  "selected_index": 1,
  "selected_high_level_action": "destination_viewpoint_or_null"
}
```

```json
{
  "event_type": "execution",
  "source_viewpoint": "...",
  "destination_viewpoint": "...",
  "expanded_path": ["..."],
  "expanded_path_includes_source": false,
  "travel_only_nodes": ["..."],
  "observation_endpoint": "...",
  "next_observation_index": 1
}
```

`expanded_path` 在 `make_equiv_action` 调用前由
`GraphMap.graph.path(current, action)` 复制，不能从 evaluator shortest path
获得。冻结的 `FloydGraph.path` 返回不含 source、包含 endpoint 的 suffix，
因此 `travel_only_nodes = expanded_path[:-1]`，而最后一个元素是唯一的下一
observation endpoint。

### 4.4 `termination`

当前源码允许多个条件同一步为真，因此既记录 flags，也记录原代码最终是否送出 `None`：

```json
{
  "event_type": "termination",
  "flags": {
    "duet_stop": false,
    "no_frontier": false,
    "max_step": false,
    "episode_already_done": false
  },
  "trigger_priority": ["duet_stop", "episode_already_done", "no_frontier", "max_step"],
  "selected_trigger": null,
  "environment_action_is_none": false
}
```

`trigger_priority` mirrors the left-to-right order of the frozen source's OR
condition. `selected_trigger` is the first true flag in that order (or `null`
when execution continues); all simultaneously true flags remain visible.

M0 trace 不引入 FOUND、NOT-FOUND、UNRESOLVED 或 verifier verdict；那些是 M1 以后的 prediction contract。M0 只忠实拆出原 DUET 终止条件。

### 4.5 `prediction`

保留原始：

```json
{
  "event_type": "prediction",
  "trajectory": [["viewpoint_id"]],
  "pred_objid": null
}
```

`runtime_trace.jsonl` 到此结束，不能包含 evaluator event、SR、SPL、oracle SR、GT distance、`obj2vps`、完整 connectivity 或任何 GT 派生值。

Evaluator 输出必须物理、逻辑分离到 `offline_metrics.json`。该文件可以包含公开的 `action_steps`、`steps`、`lengths`、`sr`、`oracle_sr`、`spl`、`rgs` 和 `rgspl`，但 trace sink、policy、运行时 observation sanitizer 和 action path 均不得读取它。

## 5. 已实现的 instrumentation 接缝

| Trace event | 源码接缝 | 只读值 |
|---|---|---|
| observation | `GMapObjectNavAgent.rollout` 的 `reset/_get_obs` 之后 | sanitized observation schema |
| model_scores | `nav_outs = self.vln_bert('navigation', nav_inputs)` 之后 | 三类 logits、IDs、masks、object logits、GraphMap visited/unvisited |
| action | 原 feedback 分支完成 `a_t` 之后 | 原 action index 与映射后的 vpid |
| execution | `make_equiv_action` 内 `newEpisode` 之前 | incremental GraphMap 展开路径 |
| termination | `cpu_a_t` 构造处 | 四个原始布尔条件和 `None` 结果 |
| prediction | rollout 返回前 | 原 trajectory、pred_objid、details |

Evaluator 不属于 trace instrumentation；`offline_metrics.json` 由 evaluation wrapper 在 rollout 全部结束后单独写出。

实现位于 `reverie/runtime_trace.py`，使用独立 sink 和默认 `None`
no-op；trace state 不进入模型输入、GraphMap 或 action score。sink 的持久字段
只有输出路径、fusion mode、episode 限额、run ID、文件句柄及 copied primitive
计数状态，不持有 observation dict、environment、simulator、evaluator 或 GraphMap
引用。

## 6. 必须通过的验证

| 验证 | 当前状态 |
|---|---|
| 未访问 candidate embedding 不被标成目标节点 observation | 通过；真实事件统一为 `unobserved_navigation_proposal` |
| 首次/cache candidate key 差异及 `distance` 不被使用 | 通过；首次有、cache 无，决策字段相同，agent 无读取 |
| local/global/dynamic action ID mapping | 通过；三个 fusion 各一个真实 episode，STOP index 均为 0/null |
| 远端 path 中间节点为 travel-only、endpoint 才观察 | 通过；真实 dynamic trace 捕获 4-hop suffix、3 个 travel-only 节点 |
| tracing on/off prediction byte-equivalent | 通过；prediction SHA-256 均为 `c2da2341...b513917d6` |
| 固定样本 action/trajectory/pred_objid 重复稳定 | 通过；样本 `6617_185_1` 两次 traced action 序列相同 |
| denylist/完整图在 trace 中零出现 | 通过；typed allowlist 后递归审计 66 events、0 failures |

真实 dynamic trace 为
`/root/autodl-tmp/ProofNav/.m0-results/traces/dynamic_runtime_trace.jsonl`，
SHA-256 `70c61e3a...8509093`。对应 evaluator 输出位于不同目录的
`offline_metrics.json`，runtime sink 没有读取路径。
