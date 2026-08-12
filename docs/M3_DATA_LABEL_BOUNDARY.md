# M3 data and label boundary

## 1. Runtime allowlist

Runtime可读取：instruction/token、实际到达viewpoint的panorama/object tensors、ordered slot IDs仅作为
当前 observation 内的slot key、angles/box features、DUET logits/embeddings/masks、incremental GraphMap
和公开scope/template。公开 proof log只保留 sufficient statistics 与content digests，不复制大tensor。

禁止进入runtime artifact/evidence/risk：`gt_path/gt_end_vps/gt_obj_id`、BBoxes内容、`obj2vps`、完整
connectivity/shortest paths、逐样本label、paired truth、object names/depths、split outcomes或能反查它们的
lookup table。artifact只能保存aggregate counts/bounds/fingerprints，不保存per-sampletruth。

## 2. Offline-only labels

- entity：REVERIE `gt_obj_id`与BBoxes/`obj2vps`用于判断typed slot SUPPORT是否事实正确。
- attribute/relation/room：当前无合法结构化label；必须从严格paired calibration protocol新增。
- residual：必须标注所有满足target template的实例以及proposal misses；只标现有slots会产生循环定义。
- identity：obj ID只可生成offlinepositive/negative pairs，adapter input必须移除ID equality信号。

## 3. Split protocol

正式协议先按scan分区，再生成任何view/object/episode记录。一个scan及其全部viewpoint、object crops、
instructions和identity pairs只能属于一个split。test与val-unseen永不用于threshold、method、domain或
ablation选择。

当前资源事实：train 60 scans；val_train_seen的27 scans与train全重合；val_seen的46 scans与train全
重合；val_unseen 10和test 16均与train不重合。冻结checkpoint已用全部train scans，因此现成资源无
checkpoint-unseen且可合法calibrate的scan。当前micro artifact必须标`descriptive_seen_scan_micro`；
unseen scan fail closed。

正式M3-B的最小资源选择：

1. 重训/轻量训练时从train scans预先留出development/calibration scans；或
2. 获得不属于官方val-unseen/test的新scan-disjointlabels；
3. 对attribute/relation/room/residual/identity按上节定义补充audit provenance。

## 4. Leakage checks

Builder必须拒绝：split overlap、calibration中出现val-unseen/test、逐样本truth map、GT字段别名、未知
artifact字段、label fingerprint与声明split不符、模型/feature/interface hash不符。Runtime包依赖图不得
import offline label builder/evaluator。

## 5. 本轮实际 offline-only 缩约

真实 micro runner 先仅根据 signal/domain 字段选定 demonstration，再加载 annotation；runtime
chain 函数不接受 truth/annotation 参数。`REVERIE_val_train_seen_enc.json` 的 `objId` 只在：

1. calibration 分区的 scan-familywise aggregate builder；
2. terminal 记录已冻结后的 `OracleOfflineVerifier`

两处读取。生产 artifact 只保留 `6 scans / 54 active examples / 2 errors`、split fingerprint、
label-definition digest 和 bound；不保留 sample ID、slot truth、target path、`obj2vps` 或查询表。
Signal hook在每轮model call前用上一轮terminal state形成active mask，只记录仍活跃episode；当前STOP
step仍是因果有效观察，已结束batch row的冻结viewpoint后缀不会进入calibration或replay authority。

预注册 hash partition 的实际数量为：

| partition | role | scans | observations | null selections | threshold SUPPORT |
|---:|---|---:|---:|---:|---:|
| 0 | development（本轮不用） | 7 | 67 | 24 | 13 |
| 1 | calibration | 6 | 54 | 10 | 13 |
| 2 | demonstration | 8 | 72 | 23 | 12 |

partition 2 中用 signal-only canonical ordering 选中
`runtime-episode-3e91a522140d42cf2330e1be2e530f5d/event_seq=4`；该 opaque ID 不含 raw
`instr_id/objId`。事后 offline
truth 确认 selected slot `51` 与 target `51` 一致。该正例用于证明管道，不用于阈值或方法选择。
